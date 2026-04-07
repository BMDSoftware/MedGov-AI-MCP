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
    Download a scaled overview of a whole-slide image from iPath.

    Calls the ROI endpoint with x=0, y=0 to get a full-slide overview image
    downsampled to the requested dimensions. The server scales the entire slide
    to fit — this is NOT a crop. Default size is 844x588. Both dimensions are
    clamped to 2700 max.

    Use the returned width and height as thumb_img_w / thumb_img_h in
    scale_roi_to_slide.

    Args:
        slide_uid: The DICOM UID of the slide
                   (e.g. 2.25.338247016696998394111485786182386609869)
        output_path: Absolute path where the thumbnail image will be saved
        width: Requested thumbnail width in pixels (default 844, max 2700)
        height: Requested thumbnail height in pixels (default 588, max 2700)

    Returns:
        {success: true, path, width, height} on success,
        {success: false, error} on failure.
    """
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
    Retrieve the full pixel dimensions of a whole-slide image from iPath.

    Uses Dicoogle's /dump endpoint to read TotalPixelMatrixColumns and
    TotalPixelMatrixRows directly from the indexed DICOM tags. Call this before
    scale_roi_to_slide to get the slide_w and slide_h values needed for scaling.

    Args:
        slide_uid: The DICOM UID of the slide (SOPInstanceUID)

    Returns:
        {success: true, width, height} on success,
        {success: false, error} on failure.
    """
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
    Scale a bounding box from thumbnail pixel coordinates to full slide coordinates.

    Use this after visually identifying the tumor region in the thumbnail image.
    thumb_img_w and thumb_img_h should match the width/height returned by
    fetch_thumbnail. Slide dimensions come from get_slide_dimensions.

    Args:
        thumb_x: Left edge of bounding box in thumbnail pixels
        thumb_y: Top edge of bounding box in thumbnail pixels
        thumb_w: Width of bounding box in thumbnail pixels
        thumb_h: Height of bounding box in thumbnail pixels
        thumb_img_w: Total width of the thumbnail image (from fetch_thumbnail)
        thumb_img_h: Total height of the thumbnail image (from fetch_thumbnail)
        slide_w: Full slide width in pixels (from get_slide_dimensions)
        slide_h: Full slide height in pixels (from get_slide_dimensions)

    Returns:
        {x, y, width, height} in full slide pixel coordinates, ready for fetch_roi.
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
    Fetch a high-resolution region of interest from a whole-slide iPath image.

    IMPORTANT: width and height are hard-clamped to a maximum of 2700 pixels each
    before the HTTP request is made. This is enforced unconditionally regardless of
    the values supplied. If clamping occurs, the response includes clamped=true so
    the agent can note it.

    Typical workflow:
      1. fetch_thumbnail -> save thumbnail locally
      2. LLM visually identifies tumor bbox in thumbnail pixels
      3. get_slide_dimensions -> get full slide size
      4. scale_roi_to_slide -> convert to slide-space coordinates
      5. fetch_roi -> download the high-res ROI (this tool)

    Args:
        slide_uid: The DICOM UID of the slide
        x: Left edge of ROI in full slide pixels
        y: Top edge of ROI in full slide pixels
        width: Width of ROI in full slide pixels (clamped to 2700 max)
        height: Height of ROI in full slide pixels (clamped to 2700 max)
        output_path: Absolute path where the ROI image will be saved

    Returns:
        {success: true, path, x, y, width, height, clamped} on success,
        {success: false, error} on failure.
    """
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
            "image_for_llm": True,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    log("Starting iPath MCP server...")
    mcp.run(transport="stdio")
