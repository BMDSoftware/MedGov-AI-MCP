#!/usr/bin/env python3
"""
MCP iPath Server - Tools for fetching ROIs from whole-slide images via the iPath DICOM server.

Provides four atomic tools:
  - fetch_thumbnail: Download a scaled overview of the whole slide to a local file
  - get_slide_dimensions: Retrieve full slide pixel dimensions from Dicoogle /dump
  - scale_roi_to_slide: Scale thumbnail-space bounding box to slide-space coordinates
  - fetch_roi: Fetch a high-res ROI (width/height hard-clamped to 2700px)

No vision model is run here. Visual reasoning is done by the LLM agent.
"""

import sys
from typing import Any, Dict

import httpx
from pathlib import Path
from mcp.server.fastmcp import FastMCP


IPATH_BASE = "https://ipath.bmd-software.com/dicoogle"
MAX_ROI_DIM = 2700
UID_SUFFIX = ".1.1.1.1.1.1.1"


def normalize_uid(uid: str) -> str:
    """Append the standard iPath UID suffix if not already present."""
    uid = uid.strip()
    if not uid.endswith(UID_SUFFIX):
        uid += UID_SUFFIX
    return uid


def log(msg: str):
    """Log to stderr to avoid interfering with stdio JSON-RPC protocol."""
    print(msg, file=sys.stderr, flush=True)


mcp = FastMCP("ipath")


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def fetch_thumbnail(
    slide_uid: str,
    output_path: str,
    width: int = 844,
    height: int = 588,
) -> Dict[str, Any]:
    """
    Download a scaled overview of a whole-slide iPath image to a local file.
    Returns width/height to use as thumb_img_w/thumb_img_h in scale_roi_to_slide.

    Args:
        slide_uid: DICOM UID of the slide (e.g. 2.25.338...)
        output_path: Absolute path where the image will be saved
        width: Thumbnail width in pixels (default 844, max 2700)
        height: Thumbnail height in pixels (default 588, max 2700)
    """
    slide_uid = normalize_uid(slide_uid)
    width = min(width, MAX_ROI_DIM)
    height = min(height, MAX_ROI_DIM)
    url = f"{IPATH_BASE}/roi?x=0&y=0&width={width}&height={height}&uid={slide_uid}"
    log(f"fetch_thumbnail: {url}")
    try:
        with httpx.Client(timeout=30) as client:
            r = client.get(url)
            r.raise_for_status()
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_bytes(r.content)
        return {"success": True, "path": output_path, "width": width, "height": height, "image_for_llm": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def get_slide_dimensions(slide_uid: str) -> Dict[str, Any]:
    """
    Get the full pixel dimensions of a whole-slide iPath image.

    Args:
        slide_uid: DICOM UID of the slide
    """
    slide_uid = slide_uid.strip()
    url = f"{IPATH_BASE}/dump?uid={slide_uid}"
    log(f"get_slide_dimensions: {url}")
    try:
        with httpx.Client(timeout=15) as client:
            r = client.get(url)
            r.raise_for_status()
        data = r.json()
        fields = data.get("results", {}).get("fields", {})
        width = fields.get("TotalPixelMatrixColumns")
        height = fields.get("TotalPixelMatrixRows")
        if width is None or height is None:
            return {
                "success": False,
                "error": "TotalPixelMatrix fields not found",
                "fields": list(fields.keys()),
            }
        return {"success": True, "width": int(width), "height": int(height)}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def scale_roi_to_slide(
    thumb_x: float,
    thumb_y: float,
    thumb_w: float,
    thumb_h: float,
    thumb_img_w: float,
    thumb_img_h: float,
    slide_w: int,
    slide_h: int,
) -> Dict[str, Any]:
    """
    Scale a bounding box from thumbnail coordinates to full slide coordinates.

    Args:
        thumb_x, thumb_y: Top-left of bbox in thumbnail pixels
        thumb_w, thumb_h: Size of bbox in thumbnail pixels
        thumb_img_w, thumb_img_h: Thumbnail dimensions (from fetch_thumbnail)
        slide_w, slide_h: Full slide dimensions (from get_slide_dimensions)
    """
    scale_x = slide_w / thumb_img_w
    scale_y = slide_h / thumb_img_h
    return {
        "x": round(thumb_x * scale_x),
        "y": round(thumb_y * scale_y),
        "width": round(thumb_w * scale_x),
        "height": round(thumb_h * scale_y),
    }


@mcp.tool()
def fetch_roi(
    slide_uid: str,
    x: int,
    y: int,
    width: int,
    height: int,
    output_path: str,
) -> Dict[str, Any]:
    """
    Fetch a high-res ROI from a whole-slide iPath image. Width/height clamped to 2700px.

    Workflow: fetch_thumbnail -> identify bbox -> get_slide_dimensions -> scale_roi_to_slide -> fetch_roi

    Args:
        slide_uid: DICOM UID of the slide
        x, y: Top-left of ROI in full slide pixels
        width, height: Size of ROI in full slide pixels (max 2700)
        output_path: Absolute path where the image will be saved
    """
    slide_uid = slide_uid.strip()
    clamped = width > MAX_ROI_DIM or height > MAX_ROI_DIM
    width = min(width, MAX_ROI_DIM)
    height = min(height, MAX_ROI_DIM)

    url = f"{IPATH_BASE}/roi?x={x}&y={y}&width={width}&height={height}&uid={slide_uid}"
    log(f"fetch_roi: {url} (clamped={clamped})")
    try:
        with httpx.Client(timeout=60) as client:
            r = client.get(url)
            r.raise_for_status()
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_bytes(r.content)
        return {
            "success": True,
            "path": output_path,
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "clamped": clamped,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    log("Starting iPath MCP server...")
    mcp.run(transport="stdio")
