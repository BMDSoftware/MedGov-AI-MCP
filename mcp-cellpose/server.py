"""Cellpose MCP server.

Auto-detects GPU availability at startup:
- If an NVIDIA GPU is detected (nvidia-smi exits 0), runs with GPU acceleration.
- Otherwise falls back to CPU-only mode by hiding CUDA devices.
"""

import os
import subprocess

def _has_gpu() -> bool:
    try:
        result = subprocess.run(
            ["nvidia-smi"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False

_gpu = _has_gpu()
if not _gpu:
    os.environ["CUDA_VISIBLE_DEVICES"] = ""

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
# On CPU, allow PyTorch to use all cores — cpsam (SAM/ViT) is compute-heavy and
# benefits greatly from multi-threading. OMP_NUM_THREADS=1 was set to prevent
# OpenMP deadlocks with GPU; on CPU-only that restriction is unnecessary.
if not _gpu:
    os.environ.pop("OMP_NUM_THREADS", None)  # let PyTorch pick the right default
else:
    os.environ.setdefault("OMP_NUM_THREADS", "1")

from cellpose_mcp.mcp_instance import mcp  # noqa: E402
from cellpose_mcp import tools as _tools  # noqa: E402, F401 — registers all upstream tools

# ── Model descriptions ─────────────────────────────────────────────────────────

_MODEL_DESCRIPTIONS = {
    # Segmentation
    "cyto3": "Latest cytoplasm model (v3). Best general-purpose choice for most cell types. Use for whole-cell segmentation.",
    "cyto2": "Cytoplasm model v2. Good for round cells with clear cytoplasm. Slightly less accurate than cyto3 on diverse images.",
    "cyto": "Original cytoplasm model (v1). Legacy — prefer cyto3 unless you need reproducibility with older results.",
    "nuclei": "Nucleus-only segmentation. Use when you only want to detect nuclei, not whole cells.",
    "bact": "Bacteria segmentation. Optimized for elongated, small bacterial cells in fluorescence or phase-contrast images.",
    "tissuenet": "Tissue segmentation. Trained on TissueNet; best for cells imaged in tissue sections.",
    "livecell": "Live-cell imaging model. Trained on LIVECell dataset; best for phase-contrast microscopy of live cells.",
    "yeast": "Yeast cell segmentation. Specialized for budding yeast (S. cerevisiae) brightfield or fluorescence images.",
    # Restoration — denoise
    "denoise_cyto3": "Denoise cytoplasm images (v3). Removes noise before segmentation or for clean visualization.",
    "denoise_cyto2": "Denoise cytoplasm images (v2).",
    "denoise_nuclei": "Denoise nucleus images.",
    # Restoration — deblur
    "deblur_cyto3": "Deblur cytoplasm images (v3). Sharpens out-of-focus fluorescence images.",
    "deblur_cyto2": "Deblur cytoplasm images (v2).",
    # Restoration — upsample
    "upsample_cyto3": "Upsample cytoplasm images 2x (v3). Increases resolution for low-magnification acquisitions.",
    "upsample_cyto2": "Upsample cytoplasm images 2x (v2).",
    # One-click combined pipelines
    "oneclick_cyto3": "One-click pipeline: denoise + segment cytoplasm (v3). Best quality in a single step.",
    "oneclick_cyto2": "One-click pipeline: denoise + segment cytoplasm (v2).",
}


# @mcp.tool()  # only cpsam is used in v4 — no need to expose model listing
def list_models_with_descriptions() -> dict:
    """List all available Cellpose models with a short description of each.

    Returns models grouped by category. Each entry includes a brief description
    of what the model is best used for. Use this to pick the right model before
    calling segment_cells_2d, segment_cells_3d, or any restoration tool.
    """
    return {
        "segmentation": {
            name: _MODEL_DESCRIPTIONS[name]
            for name in ["cyto3", "cyto2", "cyto", "nuclei", "bact", "tissuenet", "livecell", "yeast"]
        },
        "restoration": {
            "denoise": {name: _MODEL_DESCRIPTIONS[name] for name in ["denoise_cyto3", "denoise_cyto2", "denoise_nuclei"]},
            "deblur":  {name: _MODEL_DESCRIPTIONS[name] for name in ["deblur_cyto3", "deblur_cyto2"]},
            "upsample": {name: _MODEL_DESCRIPTIONS[name] for name in ["upsample_cyto3", "upsample_cyto2"]},
            "oneclick": {name: _MODEL_DESCRIPTIONS[name] for name in ["oneclick_cyto3", "oneclick_cyto2"]},
        },
    }


# @mcp.tool()  # only cpsam is used in v4 — no need to expose model listing
def describe_models(model_names: list[str]) -> dict:
    """Get detailed descriptions for a specific subset of Cellpose models.

    Use this when you need to compare a few candidate models before choosing one.
    Call list_models_with_descriptions first to see all available model names.

    Args:
        model_names: List of model names to describe (e.g. ["cyto3", "nuclei", "bact"])

    Returns:
        Dictionary mapping each model name to its description.
    """
    return {
        name: _MODEL_DESCRIPTIONS.get(name, f"No description available for '{name}'.")
        for name in model_names
    }


@mcp.tool()
def save_overlay(image_path: str, mask_path: str, output_path: str | None = None) -> dict:
    """Draw segmentation outlines on the original image and save as PNG.

    Creates a visualization where cell boundaries are drawn in red on top of the
    original image. Use this after segment_cells_2d to inspect where cells were detected.

    Args:
        image_path: Path to the original image
        mask_path: Path to the mask file produced by segment_cells_2d
        output_path: Optional path for the overlay PNG (default: mask_path with _overlay.png suffix)

    Returns:
        Dictionary with overlay_path, or error key on failure
    """
    import numpy as np
    import imageio.v2 as imageio
    from pathlib import Path
    from cellpose import utils, io

    try:
        img = io.imread(image_path)
        masks = io.imread(mask_path)

        # Convert to uint8 RGB
        if img.ndim == 2:
            img_rgb = np.stack([img, img, img], axis=-1)
        elif img.ndim == 3 and img.shape[-1] >= 3:
            img_rgb = img[:, :, :3].copy()
        else:
            img_rgb = np.stack([img[..., 0]] * 3, axis=-1)

        if img_rgb.dtype != np.uint8:
            vmax = img_rgb.max()
            if vmax > 0:
                img_rgb = (img_rgb / vmax * 255).astype(np.uint8)
            else:
                img_rgb = img_rgb.astype(np.uint8)

        # Draw outlines using cellpose's built-in boundary detection
        from cellpose import utils
        boundary = utils.masks_to_outlines(masks)
        # Thicken by 2px via two rounds of dilation
        for _ in range(2):
            boundary = (
                boundary
                | np.pad(boundary, ((1,0),(0,0)), mode='constant')[:-1,:]
                | np.pad(boundary, ((0,1),(0,0)), mode='constant')[1:,:]
                | np.pad(boundary, ((0,0),(1,0)), mode='constant')[:,:-1]
                | np.pad(boundary, ((0,0),(0,1)), mode='constant')[:,1:]
            )
        overlay = img_rgb.copy()
        overlay[boundary] = [57, 255, 20]  # neon green

        if output_path is None:
            p = Path(mask_path)
            output_path = str(p.parent / f"{p.stem}_overlay.png")

        imageio.imwrite(output_path, overlay)

        # Save a display-friendly binary mask: cells white, background black
        p = Path(mask_path)
        display_mask_path = str(p.parent / f"{p.stem}_display.png")
        binary = ((masks > 0) * 255).astype(np.uint8)
        imageio.imwrite(display_mask_path, binary)

        return {"overlay_path": output_path, "display_mask_path": display_mask_path}
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    mcp.run()
