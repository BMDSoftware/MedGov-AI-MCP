"""
ROI Simulator Server

Receives a source pathology image and drops N random crops into a watched workspace
folder, simulating an external imaging system sending ROI studies.

Usage:
    python server.py --watch-dir /path/to/workspace/incoming --port 7100

POST /send-roi
    Form fields:
        image       - image file upload
        roi_id      - study/ROI identifier (default: auto uuid)
        n           - number of crops to generate (default: 20, max: 100)

POST /send-sample
    Uses the bundled sample image (set via --sample or SAMPLE_IMAGE env var).
    Query params: roi_id, n
"""

import argparse
import os
import random
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image
import uvicorn
import io

app = FastAPI(title="ROI Simulator", version="1.0.0")

# Configured at startup
_watch_dir: Path = Path(".")
_sample_image: Path | None = None


def _generate_crops(img: Image.Image, roi_id: str, n: int, out_dir: Path) -> list[str]:
    """
    Generate n random crops of varying sizes and positions from img.
    Each crop covers between 20% and 100% of each dimension.
    Saved as ROI_{roi_id}_{i:03d}.png
    """
    w, h = img.size
    out_dir.mkdir(parents=True, exist_ok=True)
    created = []

    for i in range(1, n + 1):
        # Random crop size: 20%-100% of width and height independently
        crop_w = random.randint(max(1, w // 5), w)
        crop_h = random.randint(max(1, h // 5), h)

        # Random top-left origin that keeps the crop inside the image
        x0 = random.randint(0, w - crop_w)
        y0 = random.randint(0, h - crop_h)

        crop = img.crop((x0, y0, x0 + crop_w, y0 + crop_h))
        filename = f"ROI_{roi_id}_{i:03d}.png"
        out_path = out_dir / filename
        crop.save(out_path, format="PNG")
        created.append(str(out_path))

    return created


@app.post("/send-roi")
async def send_roi(
    image: UploadFile = File(...),
    roi_id: str = Form(default=""),
    n: int = Form(default=20),
):
    n = max(1, min(n, 100))
    roi_id = roi_id.strip() or uuid.uuid4().hex[:8]

    data = await image.read()
    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not open image: {e}")

    created = _generate_crops(img, roi_id, n, _watch_dir)
    return JSONResponse({"roi_id": roi_id, "n": len(created), "files": created})


@app.post("/send-sample")
async def send_sample(roi_id: str = "", n: int = 20):
    if _sample_image is None or not _sample_image.exists():
        raise HTTPException(status_code=404, detail="No sample image configured (use --sample or SAMPLE_IMAGE env var)")

    n = max(1, min(n, 100))
    roi_id = roi_id.strip() or uuid.uuid4().hex[:8]

    try:
        img = Image.open(_sample_image).convert("RGB")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not open sample image: {e}")

    created = _generate_crops(img, roi_id, n, _watch_dir)
    return JSONResponse({"roi_id": roi_id, "n": len(created), "files": created})


@app.get("/health")
def health():
    return {"status": "ok", "watch_dir": str(_watch_dir), "sample_image": str(_sample_image)}


def main():
    global _watch_dir, _sample_image

    parser = argparse.ArgumentParser(description="ROI Simulator Server")
    parser.add_argument("--watch-dir", required=True, help="Workspace incoming folder to drop crops into")
    parser.add_argument("--port", type=int, default=7100)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--sample", default=os.environ.get("SAMPLE_IMAGE", ""), help="Path to a sample image for /send-sample")
    args = parser.parse_args()

    _watch_dir = Path(args.watch_dir)
    _watch_dir.mkdir(parents=True, exist_ok=True)

    if args.sample:
        _sample_image = Path(args.sample)

    print(f"ROI Simulator running on {args.host}:{args.port}")
    print(f"Dropping crops into: {_watch_dir}")
    if _sample_image:
        print(f"Sample image: {_sample_image}")

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
