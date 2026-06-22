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

from typing import Annotated  # noqa: E402
from pydantic import Field  # noqa: E402
from cellpose_mcp.mcp_instance import mcp  # noqa: E402
from cellpose_mcp import tools as _tools  # noqa: E402, F401 — registers all upstream tools

# Uncomment to force cpsam regardless of what model_type the LLM passes.
# Cellpose v4 ignores model_type anyway, but the wrong value shows up in the UI.
# _upstream_segment_2d = _tools.segment_cells_2d
# mcp.remove_tool("segment_cells_2d")
#
# @mcp.tool()
# def segment_cells_2d(
#     image_path: str,
#     model_type: str = "cpsam",
#     diameter: float = 0,
#     channels: list[int] | None = None,
#     flow_threshold: float = 0.4,
#     cellprob_threshold: float = 0.0,
#     min_size: int = 15,
#     gpu: bool = True,
#     augment: bool = False,
#     normalize: bool = True,
#     invert: bool = False,
#     output_path: str | None = None,
# ) -> dict:
#     """Segment cells in a 2D microscopy image using Cellpose (cpsam model).
#
#     Args:
#         image_path: Path to input image file (TIFF, PNG, etc.)
#         model_type: Ignored - always uses cpsam (Cellpose v4 default)
#         diameter: Expected cell diameter in pixels (0 = auto-estimate)
#         channels: Channel specification [cyto, nuclei] or None for grayscale
#         flow_threshold: Flow error threshold
#         cellprob_threshold: Cell probability threshold
#         min_size: Minimum cell size in pixels
#         gpu: Whether to use GPU acceleration
#         augment: Use test-time augmentation (flip/rotate)
#         normalize: Normalize image intensities
#         invert: Invert image intensities (for bright background)
#         output_path: Optional path to save masks
#
#     Returns:
#         Dictionary with segmentation results including cells_detected, output_path, diameter, mask_shape
#     """
#     return _upstream_segment_2d(
#         image_path=image_path,
#         model_type="cpsam",
#         diameter=diameter,
#         channels=channels,
#         flow_threshold=flow_threshold,
#         cellprob_threshold=cellprob_threshold,
#         min_size=min_size,
#         gpu=gpu,
#         augment=augment,
#         normalize=normalize,
#         invert=invert,
#         output_path=output_path,
#     )


def cellpose_diagnostics(model_type: str = "cpsam") -> dict:
    """Run a step-by-step diagnostic and return results for each stage.

    Tests: GPU detection, torch CUDA availability, model loading, and a tiny
    inference pass. Call this when segment_cells_2d hangs to pinpoint which
    step is failing. Results are returned as a dict and will appear in the
    orchestrator debug log.
    """
    import time
    import numpy as np
    results = {}

    # Step 1: nvidia-smi
    t = time.time()
    results["gpu_detected"] = _gpu
    results["step1_nvidia_smi_s"] = round(time.time() - t, 2)

    # Step 2: torch CUDA / MPS
    t = time.time()
    try:
        import torch
        results["torch_cuda_available"] = torch.cuda.is_available()
        if torch.cuda.is_available():
            results["torch_cuda_device"] = torch.cuda.get_device_name(0)
        results["torch_mps_available"] = torch.backends.mps.is_available()
    except Exception as e:
        results["torch_cuda_available"] = False
        results["torch_mps_available"] = False
        results["torch_cuda_error"] = str(e)
    results["step2_torch_s"] = round(time.time() - t, 2)

    # Step 3: model load
    t = time.time()
    try:
        from cellpose import models
        model = models.CellposeModel(gpu=_gpu, model_type=model_type)
        results["model_loaded"] = True
    except Exception as e:
        results["model_loaded"] = False
        results["model_error"] = str(e)
        results["step3_model_load_s"] = round(time.time() - t, 2)
        return results
    results["step3_model_load_s"] = round(time.time() - t, 2)

    # Step 4: inference on a tiny 64x64 synthetic image
    t = time.time()
    try:
        img = np.random.randint(0, 255, (64, 64), dtype=np.uint8)
        model.eval(img, diameter=30, channels=None)
        results["inference_ok"] = True
    except Exception as e:
        results["inference_ok"] = False
        results["inference_error"] = str(e)
    results["step4_inference_s"] = round(time.time() - t, 2)

    return results


@mcp.tool()
def save_overlay(
    image_path: Annotated[str, Field(description="Path to the original image")],
    mask_path: Annotated[str, Field(description="Path to the mask file produced by segment_cells_2d")],
    output_path: Annotated[str | None, Field(description="Optional path for the overlay PNG (default: mask_path with _overlay.png suffix)")] = None,
) -> dict:
    """Draw segmentation outlines on the original image and save as PNG. Use this after segment_cells_2d to inspect where cells were detected."""
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
