#!/usr/bin/env python3
"""
MCP Server for MONAI - Medical imaging AI models
Simple implementation exposing MONAI functionality via MCP protocol
"""
import json
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import monai
from monai.networks.nets import UNet
from monai.transforms import (
    LoadImage,
    EnsureChannelFirst,
    ScaleIntensity,
    Compose,
)
import torch
import numpy as np
from typing import Dict, Any, List, Optional
import os

app = FastAPI(title="MCP MONAI Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Available tools
TOOLS = [
    {
        "name": "get_monai_info",
        "description": "Get MONAI version and available features",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "list_models",
        "description": "List available pre-trained models from MONAI Model Zoo",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Filter by category (segmentation, classification, detection)"
                }
            },
            "required": []
        }
    },
    {
        "name": "load_image",
        "description": "Load and get info about a medical image (DICOM, NIfTI, PNG, etc.)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the medical image file"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "list_transforms",
        "description": "List available MONAI transforms for image preprocessing",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Filter by category (spatial, intensity, crop, utility)"
                }
            },
            "required": []
        }
    },
]

# Sample pre-trained models from MONAI Model Zoo
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


def handle_get_monai_info(arguments: Dict) -> Dict:
    return {
        "version": monai.__version__,
        "pytorch_version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "cuda_version": torch.version.cuda if torch.cuda.is_available() else None,
        "gpu_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
        "features": [
            "Medical image I/O (DICOM, NIfTI, PNG, etc.)",
            "Pre-trained models (Model Zoo)",
            "Transforms for preprocessing",
            "Neural network architectures (UNet, UNETR, etc.)",
            "Loss functions for medical imaging",
            "Metrics (Dice, Hausdorff, etc.)",
        ]
    }


def handle_list_models(arguments: Dict) -> Dict:
    category = arguments.get("category")
    models = MODEL_ZOO
    if category:
        models = [m for m in models if m["category"] == category]
    return {
        "total": len(models),
        "models": models
    }


def handle_load_image(arguments: Dict) -> Dict:
    path = arguments.get("path")
    if not path:
        return {"error": "Path is required"}

    if not os.path.exists(path):
        return {"error": f"File not found: {path}"}

    try:
        loader = LoadImage(image_only=True)
        image = loader(path)

        return {
            "path": path,
            "shape": list(image.shape),
            "dtype": str(image.dtype),
            "min_value": float(image.min()),
            "max_value": float(image.max()),
            "mean_value": float(image.mean()),
        }
    except Exception as e:
        return {"error": str(e)}


def handle_list_transforms(arguments: Dict) -> Dict:
    category = arguments.get("category")
    if category and category in TRANSFORMS:
        return {
            "category": category,
            "transforms": TRANSFORMS[category]
        }
    return {
        "categories": list(TRANSFORMS.keys()),
        "transforms": TRANSFORMS
    }


# Tool dispatcher
TOOL_HANDLERS = {
    "get_monai_info": handle_get_monai_info,
    "list_models": handle_list_models,
    "load_image": handle_load_image,
    "list_transforms": handle_list_transforms,
}


def make_jsonrpc_response(id: Any, result: Any = None, error: Any = None) -> Dict:
    response = {"jsonrpc": "2.0", "id": id}
    if error:
        response["error"] = error
    else:
        response["result"] = result
    return response


@app.post("/mcp/tools/list")
async def list_tools(request: Request):
    body = await request.json()
    return JSONResponse(
        content=make_jsonrpc_response(
            body.get("id", 1),
            result={"tools": TOOLS}
        ),
        media_type="application/json"
    )


@app.post("/mcp/tools/call")
async def call_tool(request: Request):
    body = await request.json()
    params = body.get("params", {})
    tool_name = params.get("name")
    arguments = params.get("arguments", {})

    if tool_name not in TOOL_HANDLERS:
        return JSONResponse(
            content=make_jsonrpc_response(
                body.get("id", 1),
                error={"code": -32601, "message": f"Unknown tool: {tool_name}"}
            ),
            media_type="application/json"
        )

    try:
        result = TOOL_HANDLERS[tool_name](arguments)
        return JSONResponse(
            content=make_jsonrpc_response(
                body.get("id", 1),
                result={"content": [{"type": "text", "text": json.dumps(result)}]}
            ),
            media_type="application/json"
        )
    except Exception as e:
        return JSONResponse(
            content=make_jsonrpc_response(
                body.get("id", 1),
                error={"code": -32000, "message": str(e)}
            ),
            media_type="application/json"
        )


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "mcp-monai"}


if __name__ == "__main__":
    import uvicorn
    print(f"Starting MCP MONAI Server on http://localhost:8001")
    print(f"MONAI version: {monai.__version__}")
    uvicorn.run(app, host="0.0.0.0", port=8001)
