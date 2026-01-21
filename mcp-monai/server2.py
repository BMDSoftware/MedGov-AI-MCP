#!/usr/bin/env python3
import os
import json
import torch
import numpy as np
import monai
from typing import Dict, Any, List, Optional
from mcp.server.fastmcp import FastMCP
from monai.transforms import LoadImage
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Initialize FastMCP server
mcp = FastMCP("MONAI")

# --- Constants & Data ---

MODEL_ZOO = [
    {"name": "swin_unetr_btcv_segmentation", "category": "segmentation", "description": "Multi-organ segmentation on CT"},
    {"name": "pancreas_ct_dints_segmentation", "category": "segmentation", "description": "Pancreas and tumor segmentation"},
    {"name": "spleen_ct_segmentation", "category": "segmentation", "description": "Spleen segmentation on CT"},
    {"name": "prostate_mri_anatomy", "category": "segmentation", "description": "Prostate anatomy segmentation on MRI"},
    {"name": "lung_nodule_ct_detection", "category": "detection", "description": "Lung nodule detection on CT"},
    {"name": "pathology_nuclei_segmentation", "category": "segmentation", "description": "Nuclei segmentation in pathology"},
    {"name": "breast_density_classification", "category": "classification", "description": "Breast density classification"},
    {"name": "covid19_ct_classification", "category": "classification", "description": "COVID-19 detection on chest CT"},
]

TRANSFORMS = {
    "spatial": ["Resize", "Rotate", "Flip", "Zoom", "RandAffine", "RandRotate", "Spacing"],
    "intensity": ["ScaleIntensity", "NormalizeIntensity", "ThresholdIntensity", "RandGaussianNoise"],
    "crop": ["CenterCrop", "RandCrop", "CropForeground", "RandSpatialCrop"],
    "utility": ["LoadImage", "EnsureChannelFirst", "ToTensor", "Compose", "Lambda"],
}

# --- Tools Implementation ---

@mcp.tool()
def get_monai_info() -> Dict[str, Any]:
    """Get MONAI version, PyTorch status, and available hardware/features."""
    return {
        "version": monai.__version__,
        "pytorch_version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "gpu_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
        "features": [
            "Medical image I/O",
            "Model Zoo",
            "Dictionary & Array Transforms",
            "Neural Network Architectures (UNet, UNETR)",
            "Medical Metrics (Dice, Hausdorff)"
        ]
    }

@mcp.tool()
def list_models(category: Optional[str] = None) -> Dict[str, Any]:
    """
    List available pre-trained models from the MONAI Model Zoo.
    
    :param category: Optional filter (segmentation, classification, detection)
    """
    models = MODEL_ZOO
    if category:
        models = [m for m in models if m["category"].lower() == category.lower()]
    
    return {
        "total": len(models),
        "models": models
    }

@mcp.tool()
def load_image_metadata(path: str) -> Dict[str, Any]:
    """
    Load a medical image (DICOM, NIfTI, etc.) and return its metadata and statistics.
    
    :param path: Local file system path to the image.
    """
    if not os.path.exists(path):
        return {"error": f"File not found: {path}"}

    try:
        loader = LoadImage(image_only=True)
        image = loader(path)

        # Convert numpy types to native Python types for JSON compatibility
        return {
            "path": path,
            "shape": [int(s) for s in image.shape],
            "dtype": str(image.dtype),
            "statistics": {
                "min": float(image.min()),
                "max": float(image.max()),
                "mean": float(image.mean()),
                "std": float(image.std())
            }
        }
    except Exception as e:
        return {"error": f"Failed to load image: {str(e)}"}

@mcp.tool()
def list_transforms(category: Optional[str] = None) -> Dict[str, Any]:
    """
    List available MONAI transforms for image preprocessing.
    
    :param category: Filter by spatial, intensity, crop, or utility.
    """
    if category and category in TRANSFORMS:
        return {
            "category": category,
            "transforms": TRANSFORMS[category]
        }
    return {
        "available_categories": list(TRANSFORMS.keys()),
        "all_transforms": TRANSFORMS
    }

if __name__ == "__main__":
    mcp.run(transport="stdio")