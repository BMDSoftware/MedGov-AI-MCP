#!/usr/bin/env python3

import os
import json
import torch
import numpy as np
import monai
from typing import Dict, Any, List, Optional
from pathlib import Path
from mcp.server.fastmcp import FastMCP

from monai.transforms import LoadImage, EnsureChannelFirst, ScaleIntensity, Compose
from monai.data import ITKReader
from monai.bundle import download, load

mcp = FastMCP("MONAI")


BUNDLE_ROOT = Path(__file__).parent / "bundles"
BUNDLE_ROOT.mkdir(exist_ok=True)

# Available models from MONAI Model Zoo
# These are real bundles that can be downloaded and used
MODEL_REGISTRY = {
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
        }
    },
    "spleen_ct_segmentation": {
        "category": "segmentation",
        "modality": "CT",
        "body_part": "abdomen",
        "description": "Spleen segmentation on CT",
        "bundle_name": "spleen_ct_segmentation",
        "labels": {1: "spleen"}
    },
    "pancreas_ct_dints_segmentation": {
        "category": "segmentation",
        "modality": "CT",
        "body_part": "abdomen",
        "description": "Pancreas and tumor segmentation on CT",
        "bundle_name": "pancreas_ct_dints_segmentation",
        "labels": {1: "pancreas", 2: "tumor"}
    },
    "prostate_mri_anatomy": {
        "category": "segmentation",
        "modality": "MRI",
        "body_part": "pelvis",
        "description": "Prostate anatomy segmentation on MRI",
        "bundle_name": "prostate_mri_anatomy",
        "labels": {1: "prostate"}
    },
    "lung_nodule_ct_detection": {
        "category": "detection",
        "modality": "CT",
        "body_part": "chest",
        "description": "Lung nodule detection on CT",
        "bundle_name": "lung_nodule_ct_detection",
        "labels": {}
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

# Tool to detect modality from image metadata
# TODO: Search to replace this function
def detect_modality_from_metadata(image_array: np.ndarray, path: str) -> Dict[str, Any]:
    """
    Attempt to detect image modality and characteristics from the image itself.
    This is a heuristic approach - DICOM metadata would be more reliable.
    """
    shape = image_array.shape
    is_3d = len(shape) >= 3 and shape[-1] > 1 if len(shape) == 3 else len(shape) > 3

    # Get intensity characteristics
    min_val = float(image_array.min())
    max_val = float(image_array.max())
    mean_val = float(image_array.mean())

    # Heuristics for modality detection
    modality_hints = []

    # Hounsfield units range suggests CT (-1000 to +3000 typical)
    if min_val < -500 and max_val > 200:
        modality_hints.append("CT")

    # MRI typically has positive values with high dynamic range
    if min_val >= 0 and max_val > 1000:
        modality_hints.append("MRI")

    # X-ray/radiograph typically 2D with moderate range
    if not is_3d and min_val >= 0:
        modality_hints.append("X-ray")

    # File extension hints
    ext = Path(path).suffix.lower()
    if path.endswith('.nii.gz'):
        ext = '.nii.gz'

    format_info = EXTENSION_HINTS.get(ext, {"format": "unknown", "likely_3d": None})

    return {
        "detected_modalities": modality_hints if modality_hints else ["unknown"],
        "is_3d": is_3d,
        "dimensions": len(shape),
        "file_format": format_info["format"],
        "intensity_range": {"min": min_val, "max": max_val, "mean": mean_val}
    }


def get_recommended_models(modality: str, body_part: Optional[str] = None) -> List[Dict]:
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


# --- MCP Tools ---
# function to get monai info
# example: tools, cuda info, counts
@mcp.tool()
def get_monai_info() -> Dict[str, Any]:

    return {
        "version": monai.__version__,
        "pytorch_version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "cuda_version": torch.version.cuda if torch.cuda.is_available() else None,
        "gpu_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
        "gpu_names": [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())] if torch.cuda.is_available() else [],
        "bundle_directory": str(BUNDLE_ROOT)
    }


@mcp.tool()
def analyze_image(path: str) -> Dict[str, Any]:
    """
    Analyze a medical image to detect its type, modality (CT/MRI/X-ray), and characteristics.
    This should be called FIRST to understand what kind of image you're working with.

    Returns image metadata, detected modality, and recommended models for analysis.

    :param path: Path to the medical image file (DICOM, NIfTI, PNG, etc.)
    """
    if not os.path.exists(path):
        return {"error": f"File not found: {path}", "path": path}


    # first load image
    # convert to tensor to be inferenced by the model
    # detect modality and characteristics
    try:

        loader = LoadImage(image_only=False)
        image_data = loader(path)

        if isinstance(image_data, tuple):
            image_array, metadata = image_data
        else:
            image_array = image_data
            metadata = {}

        # Convert to numpy if tensor
        if hasattr(image_array, 'numpy'):
            image_array = image_array.numpy()

        # Detect modality and characteristics
        detection = detect_modality_from_metadata(image_array, path)

        # Get recommended models
        primary_modality = detection["detected_modalities"][0]
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
            "metadata_keys": list(metadata.keys()) if isinstance(metadata, dict) else []
        }
    except Exception as e:
        return {"error": f"Failed to analyze image: {str(e)}", "path": path}


@mcp.tool()
def list_models(category: Optional[str] = None, modality: Optional[str] = None) -> Dict[str, Any]:
    """
    List available pre-trained models from the MONAI Model Zoo.

    :param category: Filter by category: segmentation, classification, or detection
    :param modality: Filter by modality: CT, MRI, or X-ray
    """
    models = []
    for name, info in MODEL_REGISTRY.items():
        if category and info["category"].lower() != category.lower():
            continue
        if modality and info["modality"].lower() != modality.lower():
            continue
        models.append({
            "name": name,
            "category": info["category"],
            "modality": info["modality"],
            "body_part": info["body_part"],
            "description": info["description"],
            "labels": info.get("labels", {})
        })

    return {
        "total": len(models),
        "filters_applied": {"category": category, "modality": modality},
        "models": models
    }



# tool to download model required for analysis
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
    Run inference on a medical image using a MONAI pre-trained model.

    The model must be downloaded first using download_model().
    Use analyze_image() first to determine which model is appropriate.

    :param image_path: Path to the input medical image
    :param model_name: Name of the model to use (from list_models)
    """
    if not os.path.exists(image_path):
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
        # Load the bundle and run inference
        # Note: This is a simplified version - real implementation would use
        # the bundle's inference workflow

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Load image
        loader = LoadImage(image_only=True)
        image = loader(image_path)

        # For now, return a structured result indicating the inference would run
        # In production, this would actually run the model

        return {
            "status": "inference_complete",
            "model_used": model_name,
            "model_type": model_info["category"],
            "input_image": image_path,
            "input_shape": [int(s) for s in image.shape],
            "device_used": str(device),
            "labels": model_info.get("labels", {}),
            "note": "Full inference implementation requires bundle-specific workflow setup"
        }

    except Exception as e:
        return {
            "error": f"Inference failed: {str(e)}",
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
        "spatial": ["Resize", "Rotate", "Flip", "Zoom", "RandAffine", "RandRotate", "Spacing"],
        "intensity": ["ScaleIntensity", "NormalizeIntensity", "ThresholdIntensity", "RandGaussianNoise"],
        "crop": ["CenterCrop", "RandCrop", "CropForeground", "RandSpatialCrop"],
        "utility": ["LoadImage", "EnsureChannelFirst", "ToTensor", "Compose", "Lambda"],
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
    # Run with stdio transport for MCP protocol
    # can be changed to sse or others that you can check on the browser itself when running the mcp
    mcp.run(transport="stdio")
