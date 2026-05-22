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
DICOMWEB_BASE = "https://ipath.bmd-software.com/dicoogle/ext/dicom-web"
WSI_BASE = "https://ipath.bmd-software.com/dicoogle/wsi"
MAX_ROI_DIM = 2700
UID_SUFFIX = ".1.1.1.1.1.1.1"


def normalize_uid(uid: str) -> str:
    """Append the standard iPath UID suffix if not already present."""
    uid = uid.strip()
    if not uid.endswith(UID_SUFFIX):
        uid += UID_SUFFIX
    return uid


def _validate_uid(uid: str) -> bool:
    """Return True if uid is a valid DICOM UID (digits and dots only, max 64 chars)."""
    uid = uid.strip()
    if not uid or len(uid) > 64:
        return False
    return all(c.isdigit() or c == "." for c in uid)


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
        thumb_w, thumb_h: Size of bbox in thumbnail pixels. HARD LIMIT: MUST NOT exceed 30 each. If your visual estimate is larger, clamp it to 30. Never pass a value above 30.
        thumb_img_w, thumb_img_h: Thumbnail dimensions (from fetch_thumbnail)
        slide_w, slide_h: Full slide dimensions (from get_slide_dimensions)
    """
    scale_x = slide_w / thumb_img_w
    scale_y = slide_h / thumb_img_h

    cx = round((thumb_x + thumb_w / 2) * scale_x)
    cy = round((thumb_y + thumb_h / 2) * scale_y)

    w = min(round(thumb_w * scale_x), MAX_ROI_DIM)
    h = min(round(thumb_h * scale_y), MAX_ROI_DIM)

    x = max(0, min(cx - w // 2, slide_w - w))
    y = max(0, min(cy - h // 2, slide_h - h))

    return {"x": x, "y": y, "width": w, "height": h}


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


@mcp.tool()
def get_series_instances(series_uid: str) -> Dict[str, Any]:
    """
    List all pyramid-level instances in a WSI series with their SOP Instance UIDs and pixel dimensions.
    Use this to identify which instance to use at each resolution level.
    The response includes a 'smallest' field with the lowest-resolution instance - sufficient to report its UID and dimensions without downloading anything.
    Only call fetch_dicom_instance if you need the actual file content for further processing.

    Args:
        series_uid: Series Instance UID to query (digits and dots only)
    """
    series_uid = normalize_uid(series_uid)
    if not _validate_uid(series_uid):
        return {"success": False, "error": "invalid arguments"}

    url = f"{WSI_BASE}/pinfo"
    log(f"get_series_instances: {url}?SeriesInstanceUID={series_uid}")
    try:
        with httpx.Client(timeout=15) as client:
            r = client.get(url, params={"SeriesInstanceUID": series_uid})
            r.raise_for_status()
        data = r.json()

        # Build flat list: top-level entry first, then subresolutions (already ordered large->small)
        instances = [
            {
                "sop_instance_uid": data["SOPInstanceUID"],
                "width": data["width"],
                "height": data["height"],
                "ntiles": data.get("ntiles"),
                "level": 0,
            }
        ]
        for i, sub in enumerate(data.get("subresolution_images", []), start=1):
            instances.append(
                {
                    "sop_instance_uid": sub["SOPInstanceUID"],
                    "width": sub["width"],
                    "height": sub["height"],
                    "ntiles": sub.get("ntiles"),
                    "level": i,
                }
            )

        smallest = instances[-1] if instances else None
        return {"success": True, "instances": instances, "smallest": smallest}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def fetch_dicom_instance(
    study_uid: str,
    series_uid: str,
    instance_uid: str,
    output_path: str,
) -> Dict[str, Any]:
    """
    Download a DICOM instance file from the DICOMweb server for further processing (e.g. parsing metadata, running inference).
    Only call this when you need the actual file content - NOT just to identify an instance or report its dimensions.
    Use get_series_instances to discover instance UIDs and dimensions without downloading anything.

    Args:
        study_uid: Study Instance UID (digits and dots only)
        series_uid: Series Instance UID (digits and dots only)
        instance_uid: SOP Instance UID (digits and dots only)
        output_path: Absolute path where the .dcm file will be saved
    """
    for name, uid in [("study_uid", study_uid), ("series_uid", series_uid), ("instance_uid", instance_uid)]:
        if not _validate_uid(uid):
            return {"success": False, "error": f"invalid arguments: {name}"}

    url = f"{DICOMWEB_BASE}/studies/{study_uid.strip()}/series/{series_uid.strip()}/instances/{instance_uid.strip()}"
    log(f"fetch_dicom_instance: {url}")
    try:
        with httpx.Client(timeout=60, follow_redirects=True) as client:
            r = client.get(url, headers={"Accept": "application/dicom"})
            r.raise_for_status()
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_bytes(r.content)
        return {
            "success": True,
            "path": output_path,
            "size_bytes": len(r.content),
            "study_uid": study_uid.strip(),
            "series_uid": series_uid.strip(),
            "instance_uid": instance_uid.strip(),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    log("Starting iPath MCP server...")
    mcp.run(transport="stdio")
