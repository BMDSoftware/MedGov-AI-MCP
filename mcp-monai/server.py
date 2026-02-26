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
        "num_classes": 2,
        "sw_batch_size": 4,
        "overlap": 0.5,
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
        "num_classes": 14,
        "sw_batch_size": 1,
        "overlap": 0.5,
    },
    "pancreas_ct_dints_segmentation": {
        "category": "segmentation",
        "modality": "CT",
        "body_part": "abdomen",
        "description": "Pancreas and tumor segmentation on CT",
        "bundle_name": "pancreas_ct_dints_segmentation",
        "labels": {1: "pancreas", 2: "tumor"},
        "input_size": [96, 96, 96],
        "num_classes": 3,
        "sw_batch_size": 2,
        "overlap": 0.5,
    },
    "lung_nodule_ct_detection": {
        "category": "detection",
        "modality": "CT",
        "body_part": "chest",
        "description": "Lung nodule detection on CT",
        "bundle_name": "lung_nodule_ct_detection",
        "labels": {1: "nodule"},
        "input_size": [96, 96, 96],
        "num_classes": 2,
        "sw_batch_size": 4,
        "overlap": 0.5,
    },
    "brats_mri_segmentation": {
        "category": "segmentation",
        "modality": "MRI",
        "body_part": "head",
        "description": "Brain tumor segmentation on MRI - requires 4-channel input (T1/T1ce/T2/FLAIR)",
        "bundle_name": "brats_mri_segmentation",
        "labels": {1: "necrotic_core", 2: "edema", 3: "enhancing_tumor"},
        "input_size": [128, 128, 128],
        "num_classes": 4,
        "sw_batch_size": 1,
        "overlap": 0.5,
    },
    "wholeBody_ct_segmentation": {
        "category": "segmentation",
        "modality": "CT",
        "body_part": "whole_body",
        "description": "Whole body CT segmentation (104 structures including head/neck)",
        "bundle_name": "wholeBody_ct_segmentation",
        "labels": {
            1: "spleen", 2: "kidney_right", 3: "kidney_left", 4: "gallbladder",
            5: "liver", 6: "stomach", 7: "aorta", 8: "inferior_vena_cava",
            9: "portal_vein_and_splenic_vein", 10: "pancreas",
            11: "adrenal_gland_right", 12: "adrenal_gland_left",
            13: "lung_upper_lobe_left", 14: "lung_lower_lobe_left",
            15: "lung_upper_lobe_right", 16: "lung_middle_lobe_right",
            17: "lung_lower_lobe_right",
            18: "vertebrae_L5", 19: "vertebrae_L4", 20: "vertebrae_L3",
            21: "vertebrae_L2", 22: "vertebrae_L1", 23: "vertebrae_T12",
            24: "vertebrae_T11", 25: "vertebrae_T10", 26: "vertebrae_T9",
            27: "vertebrae_T8", 28: "vertebrae_T7", 29: "vertebrae_T6",
            30: "vertebrae_T5", 31: "vertebrae_T4", 32: "vertebrae_T3",
            33: "vertebrae_T2", 34: "vertebrae_T1", 35: "vertebrae_C7",
            36: "vertebrae_C6", 37: "vertebrae_C5", 38: "vertebrae_C4",
            39: "vertebrae_C3", 40: "vertebrae_C2", 41: "vertebrae_C1",
            42: "esophagus", 43: "trachea",
            44: "heart_myocardium", 45: "heart_atrium_left",
            46: "heart_ventricle_left", 47: "heart_atrium_right",
            48: "heart_ventricle_right", 49: "pulmonary_artery",
            50: "brain",
            51: "iliac_artery_left", 52: "iliac_artery_right",
            53: "iliac_vena_left", 54: "iliac_vena_right",
            55: "small_bowel", 56: "duodenum", 57: "colon",
            58: "rib_left_1", 59: "rib_left_2", 60: "rib_left_3",
            61: "rib_left_4", 62: "rib_left_5", 63: "rib_left_6",
            64: "rib_left_7", 65: "rib_left_8", 66: "rib_left_9",
            67: "rib_left_10", 68: "rib_left_11", 69: "rib_left_12",
            70: "rib_right_1", 71: "rib_right_2", 72: "rib_right_3",
            73: "rib_right_4", 74: "rib_right_5", 75: "rib_right_6",
            76: "rib_right_7", 77: "rib_right_8", 78: "rib_right_9",
            79: "rib_right_10", 80: "rib_right_11", 81: "rib_right_12",
            82: "humerus_left", 83: "humerus_right",
            84: "scapula_left", 85: "scapula_right",
            86: "clavicula_left", 87: "clavicula_right",
            88: "femur_left", 89: "femur_right",
            90: "hip_left", 91: "hip_right", 92: "sacrum", 93: "face",
            94: "gluteus_maximus_left", 95: "gluteus_maximus_right",
            96: "gluteus_medius_left", 97: "gluteus_medius_right",
            98: "gluteus_minimus_left", 99: "gluteus_minimus_right",
            100: "autochthon_left", 101: "autochthon_right",
            102: "iliopsoas_left", 103: "iliopsoas_right",
            104: "urinary_bladder",
        },
        "input_size": [96, 96, 96],
        "num_classes": 105,
        "sw_batch_size": 1,
        "overlap": 0.25,
    },
    "renalStructures_UNEST_segmentation": {
        "category": "segmentation",
        "modality": "CT",
        "body_part": "abdomen",
        "description": "Kidney and renal structure segmentation on CT (UNEsT architecture)",
        "bundle_name": "renalStructures_UNEST_segmentation",
        "labels": {1: "right_kidney", 2: "left_kidney", 3: "right_renal_cortex",
                   4: "left_renal_cortex", 5: "right_renal_medulla", 6: "left_renal_medulla"},
        "input_size": [96, 96, 96],
        "num_classes": 7,
        "sw_batch_size": 2,
        "overlap": 0.5,
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

        # Override bundle_root to the actual path (configs default to ".")
        parser["bundle_root"] = str(bundle_path)

        # Override device to use our detected device (configs may hardcode cuda)
        parser["device"] = device

        # Override nested device refs that may hardcode cuda (e.g. DiNTS dints_space)
        if "dints_space" in parser and isinstance(parser["dints_space"], dict):
            parser["dints_space"]["device"] = device

        # Override arch_ckpt loading device if present (DiNTS bundles)
        if "arch_ckpt_path" in parser:
            arch_path = str(bundle_path / "models" / "search_code_18590.pt")
            if os.path.exists(arch_path):
                parser["arch_ckpt"] = torch.load(arch_path, map_location=device, weights_only=False)

        # Get network from config
        if "network_def" in parser:
            model = parser.get_parsed_content("network_def")
        elif "network" in parser:
            model = parser.get_parsed_content("network")
        else:
            raise KeyError("No network definition found in config")

        # Load weights
        checkpoint = torch.load(str(model_path), map_location=device, weights_only=False)
        if isinstance(checkpoint, dict) and "state_dict" in checkpoint:
            model.load_state_dict(checkpoint["state_dict"])
        elif isinstance(checkpoint, dict) and "model" in checkpoint:
            model.load_state_dict(checkpoint["model"])
        else:
            model.load_state_dict(checkpoint)

        log(f"Model loaded via ConfigParser: {type(model).__name__}")

    except Exception as e:
        log(f"ConfigParser failed: {e}, trying fallback...")

        # Fallback 1: TorchScript model
        ts_path = bundle_path / "models" / "model.ts"
        if ts_path.exists():
            log(f"Loading TorchScript model from {ts_path}")
            model = torch.jit.load(str(ts_path), map_location=device)
        else:
            # Fallback 2: Create UNet (only works for UNet-based bundles)
            log("Falling back to generic UNet architecture")
            model = UNet(
                spatial_dims=3,
                in_channels=1,
                out_channels=num_classes,
                channels=(16, 32, 64, 128, 256),
                strides=(2, 2, 2, 2),
                num_res_units=2,
                norm="batch",
            )
            checkpoint = torch.load(str(model_path), map_location=device, weights_only=False)
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


IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.tif'}


def load_image_dir_as_volume(dir_path: str, max_slices: int = 512) -> torch.Tensor:
    """
    Stack sorted 2D image slices from a directory into a 3D volume tensor.

    Samples evenly up to max_slices rather than loading all files at once.
    A typical CT/MRI has 100-500 slices; 512 covers most real scans.
    """
    from PIL import Image as PILImage
    all_files = sorted([
        f for f in Path(dir_path).iterdir()
        if f.is_file() and not f.name.startswith('.') and f.suffix.lower() in IMAGE_EXTS
    ])
    if not all_files:
        raise ValueError(f"No image files found in {dir_path}")

    # Sample evenly if there are more files than max_slices
    if len(all_files) > max_slices:
        step = len(all_files) / max_slices
        dir_files = [all_files[int(i * step)] for i in range(max_slices)]
        log(f"Sampling {max_slices} of {len(all_files)} slices (step={step:.1f})")
    else:
        dir_files = all_files

    slices = []
    target_size = None
    for f in dir_files:
        img = PILImage.open(str(f)).convert('L')  # grayscale
        if target_size is None:
            target_size = img.size  # (W, H)
        elif img.size != target_size:
            img = img.resize(target_size, PILImage.BILINEAR)
        slices.append(np.array(img, dtype=np.float32))

    # Stack: (Z, H, W) -> add channel -> (1, H, W, Z)
    volume = np.stack(slices, axis=0)            # (Z, H, W)
    volume = volume[np.newaxis, ...]              # (1, Z, H, W)
    volume = np.transpose(volume, (0, 2, 3, 1))  # (1, H, W, Z)

    # Normalize to [0, 1]
    vmin, vmax = volume.min(), volume.max()
    if vmax > vmin:
        volume = (volume - vmin) / (vmax - vmin)

    log(f"Stacked {len(slices)} slices into volume shape {volume.shape}")
    return torch.from_numpy(volume)


def preprocess_image(image_path: str, model_name: str = None) -> torch.Tensor:
    """Preprocess an image for inference using model-specific transforms."""
    is_dir = os.path.isdir(image_path)
    ext = "" if is_dir else Path(image_path).suffix.lower()
    if not is_dir and image_path.endswith('.nii.gz'):
        ext = '.nii.gz'

    # Directory of 2D image slices: stack into 3D volume
    if is_dir:
        dir_files = [f for f in Path(image_path).iterdir() if f.is_file() and not f.name.startswith('.')]
        if dir_files and dir_files[0].suffix.lower() in IMAGE_EXTS:
            return load_image_dir_as_volume(image_path)

    # Build preprocessing pipeline
    if not is_dir and ext in IMAGE_EXTS:
        # Single 2D image - expand to pseudo-3D
        transforms = Compose([
            LoadImage(image_only=True, reader=PILReader()),
            EnsureChannelFirst(),
            ScaleIntensity(),
            Resize(spatial_size=[96, 96]),
            EnsureType(),
        ])
        image = transforms(image_path)
        # Repeat along depth to create a 3D volume (1, H, W, D)
        image = image.unsqueeze(-1).repeat(1, 1, 1, 96)
    else:
        # 3D medical image - standard CT preprocessing
        transforms = Compose([
            LoadImage(image_only=True),
            EnsureChannelFirst(),
            Orientation(axcodes="RAS"),
            Spacing(pixdim=(1.5, 1.5, 2.0), mode="bilinear"),
            ScaleIntensityRange(a_min=-57, a_max=164, b_min=0.0, b_max=1.0, clip=True),
            EnsureType(),
        ])
        image = transforms(image_path)

    return image


def postprocess_segmentation(
    output: torch.Tensor,
    labels: Dict[int, str],
    voxel_spacing_mm: Optional[tuple] = None,
) -> Dict[str, Any]:
    """Post-process segmentation output in depth slices to avoid large memory allocation.

    voxel_spacing_mm: (x, y, z) spacing in mm after resampling, e.g. (1.5, 1.5, 2.0).
    When provided, volume_cm3 is computed for each structure.
    """
    is_binary = output.shape[1] == 1
    depth = output.shape[-1]
    total_voxels = output.shape[2] * output.shape[3] * depth
    chunk_size = 16  # slices per chunk - keeps peak memory ~chunk_size/depth of full tensor

    # Voxel volume in cm³ (1 cm³ = 1000 mm³)
    voxel_vol_cm3: Optional[float] = None
    if voxel_spacing_mm is not None:
        mm3_per_voxel = voxel_spacing_mm[0] * voxel_spacing_mm[1] * voxel_spacing_mm[2]
        voxel_vol_cm3 = mm3_per_voxel / 1000.0

    # Accumulate voxel counts per label across all chunks
    label_counts: Dict[int, int] = {}
    foreground_count = 0
    output_shape = list(output.shape[2:])  # [H, W, D]

    for z in range(0, depth, chunk_size):
        chunk = output[..., z:z + chunk_size]  # [1, C, H, W, chunk]

        if is_binary:
            pred_chunk = (chunk.squeeze(1) > 0).long()  # [1, H, W, chunk]
        else:
            pred_chunk = torch.argmax(chunk, dim=1)  # [1, H, W, chunk]

        del chunk
        pred_np = pred_chunk.cpu().numpy().squeeze(0)  # [H, W, chunk]
        del pred_chunk

        foreground_count += int((pred_np > 0).sum())
        for label_id in labels:
            label_counts[label_id] = label_counts.get(label_id, 0) + int((pred_np == label_id).sum())

        del pred_np

    del output

    detected_structures = []
    for label_id, label_name in labels.items():
        voxel_count = label_counts.get(label_id, 0)
        if voxel_count > 0:
            entry: Dict[str, Any] = {
                "label_id": label_id,
                "name": label_name,
                "voxel_count": voxel_count,
                "volume_percentage": round(voxel_count / total_voxels * 100, 2),
                "detected": True,
            }
            if voxel_vol_cm3 is not None:
                entry["volume_cm3"] = round(voxel_count * voxel_vol_cm3, 2)
            detected_structures.append(entry)

    return {
        "prediction_shape": output_shape,
        "detected_structures": detected_structures,
        "total_foreground_voxels": foreground_count,
        "background_percentage": round((total_voxels - foreground_count) / total_voxels * 100, 2)
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

        # For directories, check if it's an image slice directory or DICOM series
        is_image_dir = False
        num_dir_files = 0
        if is_dir:
            dir_files = sorted([f for f in Path(path).iterdir() if f.is_file() and not f.name.startswith('.')])
            if not dir_files:
                return {"error": "Directory is empty", "path": path}
            num_dir_files = len(dir_files)
            sample_ext = dir_files[0].suffix.lower()
            if sample_ext in IMAGE_EXTS:
                # Sample a small subset of slices for analysis (not all files)
                is_image_dir = True
                image_array = load_image_dir_as_volume(path, max_slices=20).numpy()
                detection = detect_modality_from_metadata(image_array, path, is_dir=False)
                detection["file_format"] = f"Image slice directory ({num_dir_files} slices)"
                detection["is_3d"] = True
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
                    "metadata_keys": [],
                    "ready_for_inference": True
                }

        if ext in IMAGE_EXTS:
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

        # Aggressively redirect stdout to stderr for the duration of the download.
        # MONAI's download adds its own logging handlers after basicConfig, so we
        # must swap sys.stdout itself to prevent any output from reaching the
        # stdio JSON-RPC channel.
        import logging
        import io

        # Flush anything pending before swapping
        sys.stdout.flush()
        original_stdout = sys.stdout
        sys.stdout = sys.stderr

        try:
            # Also redirect all logging handlers to stderr
            logging.root.handlers.clear()
            logging.basicConfig(stream=sys.stderr, level=logging.INFO, force=True)

            download(
                name=bundle_name,
                bundle_dir=str(BUNDLE_ROOT),
                source="monaihosting"
            )
        finally:
            sys.stdout.flush()
            sys.stdout = original_stdout

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
        sw_batch_size = model_info.get("sw_batch_size", 2)
        overlap = model_info.get("overlap", 0.5)
        log(f"Running sliding window inference with ROI={roi_size}, sw_batch={sw_batch_size}, overlap={overlap}...")

        # Verify that the image spatial dimensions match the model's ROI.
        # image shape after unsqueeze: [batch, channel, *spatial_dims]
        num_spatial_dims = image.ndim - 2
        roi_ndim = len(roi_size)
        if num_spatial_dims != roi_ndim:
            return {
                "error": (
                    f"Image has {num_spatial_dims} spatial dimension(s) (shape {list(image.shape)}) "
                    f"but {model_name} requires {roi_ndim}D input (ROI {roi_size}). "
                    f"A single 2D slice cannot be processed by a 3D volumetric model."
                ),
                "image_shape": list(image.shape),
                "required_roi": roi_size,
            }

        def _run_sliding_window(img, mdl, dev):
            with torch.no_grad():
                return sliding_window_inference(
                    img,
                    roi_size=roi_size,
                    sw_batch_size=sw_batch_size,
                    predictor=mdl,
                    overlap=overlap,
                )

        try:
            output = _run_sliding_window(image, model, device)
        except torch.OutOfMemoryError:
            log("CUDA out of memory - retrying on CPU (this will be slower)...")
            torch.cuda.empty_cache()
            # Evict from cache so it reloads on CPU
            cache_key = f"{model_name}_{device}"
            _model_cache.pop(cache_key, None)
            device = torch.device("cpu")
            model = model.cpu()
            image = image.cpu()
            output = _run_sliding_window(image, model, device)

        log(f"Output tensor shape: {output.shape}")

        # Move output to CPU before postprocessing to free GPU memory.
        # Softmax over 105 classes on a large volume (e.g. 258x258x126) needs
        # ~3 GiB extra VRAM which exceeds most consumer GPUs.
        if output.device.type == 'cuda':
            torch.cuda.empty_cache()
            output = output.cpu()

        # Determine voxel spacing: set for 3D medical images (NIfTI, DICOM), None for 2D inputs
        _is_dir = os.path.isdir(image_path)
        _ext = "" if _is_dir else Path(image_path).suffix.lower()
        if not _is_dir and image_path.endswith('.nii.gz'):
            _ext = '.nii.gz'
        if not _is_dir and _ext in IMAGE_EXTS:
            # 2D pseudo-3D: no physical voxel spacing
            _voxel_spacing: Optional[tuple] = None
        elif _is_dir:
            _dir_files = [f for f in Path(image_path).iterdir() if f.is_file() and not f.name.startswith('.')]
            if _dir_files and _dir_files[0].suffix.lower() in IMAGE_EXTS:
                # 2D image directory: no physical spacing
                _voxel_spacing = None
            else:
                # DICOM series directory: resampled to (1.5, 1.5, 2.0) mm
                _voxel_spacing = (1.5, 1.5, 2.0)
        else:
            # NIfTI or single DICOM: resampled to (1.5, 1.5, 2.0) mm
            _voxel_spacing = (1.5, 1.5, 2.0)

        # Post-process based on model type
        if model_info["category"] == "segmentation":
            results = postprocess_segmentation(output, model_info.get("labels", {}), voxel_spacing_mm=_voxel_spacing)
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
