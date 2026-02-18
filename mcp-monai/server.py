#!/usr/bin/env python3
"""
MONAI MCP Server with Real Inference
Provides medical image analysis using MONAI pre-trained models
"""

import os
import sys
import json
import torch
import numpy as np
import monai
from typing import Dict, Any, List, Optional
from pathlib import Path
from mcp.server.fastmcp import FastMCP


def log(msg: str):
    """Log to stderr to avoid interfering with stdio JSON-RPC protocol"""
    print(msg, file=sys.stderr, flush=True)

from monai.transforms import (
    LoadImage, EnsureChannelFirst, ScaleIntensity, ScaleIntensityRange, Compose,
    Spacing, Orientation, CropForeground, Resize, EnsureType,
    Activations, AsDiscrete, KeepLargestConnectedComponent
)
from monai.data import PILReader
from monai.bundle import download, ConfigParser
from monai.networks.nets import UNet, SwinUNETR
from monai.inferers import sliding_window_inference

mcp = FastMCP("MONAI")

BUNDLE_ROOT = Path(__file__).parent / "bundles"
BUNDLE_ROOT.mkdir(exist_ok=True)

# Cache for loaded models
_model_cache = {}

# Available models from MONAI Model Zoo
MODEL_REGISTRY = {
    "spleen_ct_segmentation": {
        "category": "segmentation",
        "modality": "CT",
        "body_part": "abdomen",
        "description": "Spleen segmentation on CT - good for testing",
        "bundle_name": "spleen_ct_segmentation",
        "labels": {1: "spleen"},
        "input_size": [96, 96, 96],
        "num_classes": 2
    },
    "swin_unetr_btcv_segmentation": {
        "category": "segmentation",
        "modality": "CT",
        "body_part": "abdomen",
        "description": "Multi-organ segmentation (13 organs) on CT",
        "bundle_name": "swin_unetr_btcv_segmentation",
        "labels": {
            1: "spleen", 2: "right_kidney", 3: "left_kidney", 4: "gallbladder",
            5: "esophagus", 6: "liver", 7: "stomach", 8: "aorta",
            9: "inferior_vena_cava", 10: "portal_vein_and_splenic_vein",
            11: "pancreas", 12: "right_adrenal_gland", 13: "left_adrenal_gland"
        },
        "input_size": [96, 96, 96],
        "num_classes": 14
    },
    "pancreas_ct_dints_segmentation": {
        "category": "segmentation",
        "modality": "CT",
        "body_part": "abdomen",
        "description": "Pancreas and tumor segmentation on CT",
        "bundle_name": "pancreas_ct_dints_segmentation",
        "labels": {1: "pancreas", 2: "tumor"},
        "input_size": [96, 96, 96],
        "num_classes": 3
    },
    "lung_nodule_ct_detection": {
        "category": "detection",
        "modality": "CT",
        "body_part": "chest",
        "description": "Lung nodule detection on CT",
        "bundle_name": "lung_nodule_ct_detection",
        "labels": {1: "nodule"},
        "input_size": [96, 96, 96],
        "num_classes": 2
    },
    "brats_mri_segmentation": {
        "category": "segmentation",
        "modality": "MRI",
        "body_part": "head",
        "description": "Brain tumor segmentation on MRI (BraTS challenge)",
        "bundle_name": "brats_mri_segmentation",
        "labels": {1: "necrotic_core", 2: "edema", 3: "enhancing_tumor"},
        "input_size": [128, 128, 128],
        "num_classes": 4
    },
    "wholeBody_ct_segmentation": {
        "category": "segmentation",
        "modality": "CT",
        "body_part": "whole_body",
        "description": "Whole body CT segmentation (104 structures)",
        "bundle_name": "wholeBody_ct_segmentation",
        "labels": {1: "multiple_structures"},
        "input_size": [96, 96, 96],
        "num_classes": 105
    },
}

# File extension to modality hints
EXTENSION_HINTS = {
    ".dcm": {"format": "DICOM", "likely_3d": True},
    ".nii": {"format": "NIfTI", "likely_3d": True},
    ".nii.gz": {"format": "NIfTI (compressed)", "likely_3d": True},
    ".mha": {"format": "MetaImage", "likely_3d": True},
    ".mhd": {"format": "MetaImage", "likely_3d": True},
    ".nrrd": {"format": "NRRD", "likely_3d": True},
    ".png": {"format": "PNG", "likely_3d": False},
    ".jpg": {"format": "JPEG", "likely_3d": False},
    ".jpeg": {"format": "JPEG", "likely_3d": False},
}


def detect_modality_from_metadata(image_array: np.ndarray, path: str, is_dir: bool = False) -> Dict[str, Any]:
    """Detect image modality and characteristics from the image itself."""
    shape = image_array.shape
    is_3d = len(shape) >= 3 and (shape[0] > 4 if len(shape) == 3 else True)

    min_val = float(image_array.min())
    max_val = float(image_array.max())
    mean_val = float(image_array.mean())

    modality_hints = []

    # Hounsfield units range suggests CT (-1000 to +3000 typical)
    if min_val < -500 and max_val > 200:
        modality_hints.append("CT")
    # MRI typically has positive values with moderate-to-high dynamic range
    elif min_val >= 0 and max_val > 100:
        modality_hints.append("MRI")
    # X-ray/radiograph typically 2D with moderate range
    elif not is_3d and min_val >= 0:
        modality_hints.append("X-ray")

    ext = Path(path).suffix.lower()
    if path.endswith('.nii.gz'):
        ext = '.nii.gz'

    if is_dir:
        format_info = {"format": "DICOM series", "likely_3d": True}
    else:
        format_info = EXTENSION_HINTS.get(ext, {"format": "unknown", "likely_3d": None})

    return {
        "detected_modalities": modality_hints if modality_hints else ["unknown"],
        "is_3d": is_3d,
        "dimensions": len(shape),
        "file_format": format_info["format"],
        "intensity_range": {"min": min_val, "max": max_val, "mean": mean_val}
    }


def get_recommended_models(modality: str, body_part: Optional[str] = None) -> List[Dict]:
    """Get recommended models based on modality and body part."""
    recommended = []
    for name, info in MODEL_REGISTRY.items():
        if info["modality"].lower() == modality.lower():
            if body_part is None or info["body_part"].lower() == body_part.lower():
                recommended.append({
                    "name": name,
                    "description": info["description"],
                    "category": info["category"],
                    "body_part": info["body_part"]
                })
    return recommended


def load_model_from_bundle(bundle_path: Path, model_name: str, device: torch.device) -> torch.nn.Module:
    """Load a model from a MONAI bundle."""
    global _model_cache

    cache_key = f"{model_name}_{device}"
    if cache_key in _model_cache:
        return _model_cache[cache_key]

    # Try to find the model weights
    model_path = bundle_path / "models" / "model.pt"
    if not model_path.exists():
        model_path = bundle_path / "models" / "model.ts"
    if not model_path.exists():
        # Try to find any .pt file
        pt_files = list((bundle_path / "models").glob("*.pt"))
        if pt_files:
            model_path = pt_files[0]

    if not model_path.exists():
        raise FileNotFoundError(f"No model weights found in {bundle_path / 'models'}")

    # Load inference config to get model architecture
    config_path = bundle_path / "configs" / "inference.json"
    if not config_path.exists():
        config_path = bundle_path / "configs" / "inference.yaml"

    model_info = MODEL_REGISTRY.get(model_name, {})
    num_classes = model_info.get("num_classes", 2)

    # Try to load using ConfigParser first
    try:
        parser = ConfigParser()
        parser.read_config(str(config_path))

        # Get network from config
        if "network_def" in parser:
            model = parser.get_parsed_content("network_def")
        elif "network" in parser:
            model = parser.get_parsed_content("network")
        else:
            raise KeyError("No network definition found in config")

        # Load weights
        checkpoint = torch.load(str(model_path), map_location=device)
        if isinstance(checkpoint, dict) and "state_dict" in checkpoint:
            model.load_state_dict(checkpoint["state_dict"])
        elif isinstance(checkpoint, dict) and "model" in checkpoint:
            model.load_state_dict(checkpoint["model"])
        else:
            model.load_state_dict(checkpoint)

    except Exception as e:
        log(f"ConfigParser failed: {e}, trying direct load...")

        # Fallback: Load TorchScript model directly
        if model_path.suffix == ".ts":
            model = torch.jit.load(str(model_path), map_location=device)
        else:
            # Create UNet matching the bundle config (with batch norm)
            model = UNet(
                spatial_dims=3,
                in_channels=1,
                out_channels=num_classes,
                channels=(16, 32, 64, 128, 256),
                strides=(2, 2, 2, 2),
                num_res_units=2,
                norm="batch",  # Important: bundle uses batch normalization
            )
            checkpoint = torch.load(str(model_path), map_location=device)
            if isinstance(checkpoint, dict):
                if "state_dict" in checkpoint:
                    state_dict = checkpoint["state_dict"]
                elif "model" in checkpoint:
                    state_dict = checkpoint["model"]
                else:
                    state_dict = checkpoint
            else:
                state_dict = checkpoint

            # Strip "model." prefix if present (MONAI bundle format)
            if any(k.startswith("model.") for k in state_dict.keys()):
                state_dict = {k.replace("model.", "", 1): v for k, v in state_dict.items()}
                log("Stripped 'model.' prefix from state dict keys")

            model.load_state_dict(state_dict)

    model = model.to(device)
    model.eval()

    _model_cache[cache_key] = model
    return model


def preprocess_image(image_path: str, model_name: str = None) -> torch.Tensor:
    """Preprocess an image for inference using model-specific transforms."""
    is_dir = os.path.isdir(image_path)
    ext = "" if is_dir else Path(image_path).suffix.lower()
    if not is_dir and image_path.endswith('.nii.gz'):
        ext = '.nii.gz'

    # Build preprocessing pipeline
    if not is_dir and ext in ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.tif']:
        # 2D image - need special handling
        transforms = Compose([
            LoadImage(image_only=True, reader=PILReader()),
            EnsureChannelFirst(),
            ScaleIntensity(),
            Resize(spatial_size=[96, 96]),
            EnsureType(),
        ])
        image = transforms(image_path)
        # Add a dummy depth dimension for 3D models
        image = image.unsqueeze(-1).repeat(1, 1, 1, 96)
    else:
        # 3D medical image - use proper CT preprocessing
        # Based on MONAI bundle inference.json
        transforms = Compose([
            LoadImage(image_only=True),
            EnsureChannelFirst(),
            Orientation(axcodes="RAS"),
            Spacing(pixdim=(1.5, 1.5, 2.0), mode="bilinear"),
            # CT windowing for spleen/abdomen: [-57, 164] HU -> [0, 1]
            ScaleIntensityRange(a_min=-57, a_max=164, b_min=0.0, b_max=1.0, clip=True),
            EnsureType(),
        ])
        image = transforms(image_path)

    return image


def postprocess_segmentation(output: torch.Tensor, labels: Dict[int, str]) -> Dict[str, Any]:
    """Post-process segmentation output."""
    # Apply softmax and get predictions
    if output.shape[1] > 1:  # Multi-class
        probs = torch.softmax(output, dim=1)
        pred = torch.argmax(probs, dim=1)
    else:  # Binary
        probs = torch.sigmoid(output)
        pred = (probs > 0.5).float()

    pred_np = pred.cpu().numpy().squeeze()

    # Calculate statistics for each label
    detected_structures = []
    for label_id, label_name in labels.items():
        mask = (pred_np == label_id)
        voxel_count = int(mask.sum())
        if voxel_count > 0:
            volume_percentage = float(voxel_count / pred_np.size * 100)
            detected_structures.append({
                "label_id": label_id,
                "name": label_name,
                "voxel_count": voxel_count,
                "volume_percentage": round(volume_percentage, 2),
                "detected": True
            })

    return {
        "prediction_shape": list(pred_np.shape),
        "unique_labels": [int(x) for x in np.unique(pred_np)],
        "detected_structures": detected_structures,
        "total_foreground_voxels": int((pred_np > 0).sum()),
        "background_percentage": round(float((pred_np == 0).sum() / pred_np.size * 100), 2)
    }


# --- MCP Tools ---

@mcp.tool()
def get_monai_info() -> Dict[str, Any]:
    """Get MONAI system information including version, CUDA availability, and GPU details."""
    return {
        "version": monai.__version__,
        "pytorch_version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "cuda_version": torch.version.cuda if torch.cuda.is_available() else None,
        "gpu_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
        "gpu_names": [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())] if torch.cuda.is_available() else [],
        "bundle_directory": str(BUNDLE_ROOT),
        "cached_models": list(_model_cache.keys())
    }


@mcp.tool()
def analyze_image(path: str) -> Dict[str, Any]:
    """
    Analyze a medical image to detect its type, modality (CT/MRI/X-ray), and characteristics.
    This should be called FIRST to understand what kind of image you're working with.

    Returns image metadata, detected modality, and recommended models for analysis.

    :param path: Path to the medical image file or DICOM series directory
    """
    is_dir = os.path.isdir(path)
    if not os.path.exists(path) and not is_dir:
        return {"error": f"File not found: {path}", "path": path}

    try:
        load_path = path
        ext = Path(path).suffix.lower() if not is_dir else ""

        # For directories, check if it's a DICOM series or an image folder
        if is_dir:
            dir_files = sorted([f for f in Path(path).iterdir() if f.is_file() and not f.name.startswith('.')])
            if not dir_files:
                return {"error": "Directory is empty", "path": path}
            sample_ext = dir_files[0].suffix.lower()
            if sample_ext in ('.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.tif'):
                # Image folder - analyze the first image as a sample
                load_path = str(dir_files[0])
                ext = sample_ext
                is_dir = False  # treat as single file for loading

        if ext in ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.tif']:
            loader = LoadImage(image_only=False, reader=PILReader())
        else:
            loader = LoadImage(image_only=False)

        image_data = loader(load_path)

        if isinstance(image_data, tuple):
            image_array, metadata = image_data
        else:
            image_array = image_data
            metadata = {}

        if hasattr(image_array, 'numpy'):
            image_array = image_array.numpy()

        detection = detect_modality_from_metadata(image_array, path, is_dir=is_dir)
        modalities = detection.get("detected_modalities", [])
        primary_modality = modalities[0] if modalities else "unknown"
        recommended = get_recommended_models(primary_modality)

        return {
            "path": path,
            "shape": [int(s) for s in image_array.shape],
            "dtype": str(image_array.dtype),
            "analysis": detection,
            "statistics": {
                "min": float(image_array.min()),
                "max": float(image_array.max()),
                "mean": float(image_array.mean()),
                "std": float(image_array.std())
            },
            "recommended_models": recommended,
            "metadata_keys": list(metadata.keys()) if isinstance(metadata, dict) else [],
            "ready_for_inference": detection["is_3d"] or is_dir or ext in ['.nii', '.nii.gz', '.dcm']
        }
    except Exception as e:
        return {"error": f"Failed to analyze image: {str(e)}", "path": path}


@mcp.tool()
def list_models(category: Optional[str] = None, modality: Optional[str] = None, body_part: Optional[str] = None) -> Dict[str, Any]:
    """
    List available pre-trained models from the MONAI Model Zoo.

    :param category: Filter by category: segmentation, classification, or detection
    :param modality: Filter by modality: CT, MRI, or X-ray
    :param body_part: Filter by body part: abdomen, chest, head, pelvis, etc.
    """
    models = []
    for name, info in MODEL_REGISTRY.items():
        if category and info["category"].lower() != category.lower():
            continue
        if modality and info["modality"].lower() != modality.lower():
            continue
        if body_part and info["body_part"].lower() != body_part.lower():
            continue

        # Check if model is downloaded
        bundle_path = BUNDLE_ROOT / info["bundle_name"]
        is_downloaded = bundle_path.exists()

        models.append({
            "name": name,
            "category": info["category"],
            "modality": info["modality"],
            "body_part": info["body_part"],
            "description": info["description"],
            "labels": info.get("labels", {}),
            "downloaded": is_downloaded,
            "input_size": info.get("input_size", [96, 96, 96])
        })

    return {
        "total": len(models),
        "filters_applied": {"category": category, "modality": modality, "body_part": body_part},
        "models": models
    }


@mcp.tool()
def download_model(model_name: str) -> Dict[str, Any]:
    """
    Download a pre-trained model bundle from MONAI Model Zoo.
    Must be called before run_inference if the model hasn't been downloaded yet.

    :param model_name: Name of the model from list_models()
    """
    if model_name not in MODEL_REGISTRY:
        return {
            "error": f"Unknown model: {model_name}",
            "available_models": list(MODEL_REGISTRY.keys())
        }

    model_info = MODEL_REGISTRY[model_name]
    bundle_name = model_info["bundle_name"]
    bundle_path = BUNDLE_ROOT / bundle_name

    if bundle_path.exists():
        return {
            "status": "already_downloaded",
            "model_name": model_name,
            "path": str(bundle_path)
        }

    try:
        log(f"Downloading {bundle_name} from MONAI Model Zoo...")
        # Redirect all logging to stderr so it doesn't pollute stdio JSON-RPC
        import logging
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        logging.basicConfig(stream=sys.stderr, level=logging.INFO)
        download(
            name=bundle_name,
            bundle_dir=str(BUNDLE_ROOT),
            source="monaihosting"
        )
        return {
            "status": "downloaded",
            "model_name": model_name,
            "path": str(bundle_path),
            "description": model_info["description"]
        }
    except Exception as e:
        return {
            "error": f"Failed to download model: {str(e)}",
            "model_name": model_name
        }


@mcp.tool()
def run_inference(image_path: str, model_name: str) -> Dict[str, Any]:
    """
    Run REAL inference on a medical image using a MONAI pre-trained model.

    The model must be downloaded first using download_model().
    Use analyze_image() first to determine which model is appropriate.

    For best results, use 3D medical images (NIfTI, DICOM).
    2D images (JPEG, PNG) will be converted to pseudo-3D for compatibility.

    :param image_path: Path to the input medical image file or DICOM series directory
    :param model_name: Name of the model to use (from list_models)
    """
    if not os.path.exists(image_path) and not os.path.isdir(image_path):
        return {"error": f"Image not found: {image_path}"}

    if model_name not in MODEL_REGISTRY:
        return {
            "error": f"Unknown model: {model_name}",
            "available_models": list(MODEL_REGISTRY.keys())
        }

    model_info = MODEL_REGISTRY[model_name]
    bundle_name = model_info["bundle_name"]
    bundle_path = BUNDLE_ROOT / bundle_name

    if not bundle_path.exists():
        return {
            "error": f"Model not downloaded. Call download_model('{model_name}') first.",
            "model_name": model_name
        }

    try:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        log(f"Running inference on {device}...")

        # Load the model
        log(f"Loading model from {bundle_path}...")
        model = load_model_from_bundle(bundle_path, model_name, device)

        # Preprocess the image (no resize - use sliding window instead)
        log(f"Preprocessing image...")
        image = preprocess_image(image_path, model_name)

        # Add batch dimension and move to device
        image = image.unsqueeze(0).to(device)
        log(f"Input tensor shape: {image.shape}")

        # Run inference using sliding window (handles any size input)
        roi_size = model_info.get("input_size", [96, 96, 96])
        log(f"Running sliding window inference with ROI size {roi_size}...")
        with torch.no_grad():
            output = sliding_window_inference(
                image,
                roi_size=roi_size,
                sw_batch_size=4,
                predictor=model,
                overlap=0.5
            )

        log(f"Output tensor shape: {output.shape}")

        # Post-process based on model type
        if model_info["category"] == "segmentation":
            results = postprocess_segmentation(output, model_info.get("labels", {}))
        else:
            # For detection/classification, return raw predictions
            output_np = output.cpu().numpy()
            results = {
                "raw_output_shape": list(output_np.shape),
                "max_activation": float(output_np.max()),
                "mean_activation": float(output_np.mean())
            }

        return {
            "status": "success",
            "model_used": model_name,
            "model_type": model_info["category"],
            "input_image": image_path,
            "input_shape": list(image.shape),
            "device_used": str(device),
            "results": results,
            "labels": model_info.get("labels", {})
        }

    except Exception as e:
        import traceback
        log(f"Inference failed: {str(e)}\n{traceback.format_exc()}")
        return {
            "error": f"Inference failed: {str(e)}",
            "traceback": traceback.format_exc(),
            "model_name": model_name,
            "image_path": image_path
        }


@mcp.tool()
def list_transforms(category: Optional[str] = None) -> Dict[str, Any]:
    """
    List available MONAI transforms for image preprocessing.

    :param category: Filter by: spatial, intensity, crop, or utility
    """
    transforms = {
        "spatial": ["Resize", "Rotate", "Flip", "Zoom", "RandAffine", "RandRotate", "Spacing", "Orientation"],
        "intensity": ["ScaleIntensity", "NormalizeIntensity", "ThresholdIntensity", "RandGaussianNoise", "RandAdjustContrast"],
        "crop": ["CenterCrop", "RandCrop", "CropForeground", "RandSpatialCrop", "SpatialPad"],
        "utility": ["LoadImage", "EnsureChannelFirst", "ToTensor", "Compose", "Lambda", "EnsureType"],
    }

    if category and category in transforms:
        return {
            "category": category,
            "transforms": transforms[category]
        }
    return {
        "available_categories": list(transforms.keys()),
        "all_transforms": transforms
    }


# --- Entry Point ---

if __name__ == "__main__":
    mcp.run(transport="stdio")
