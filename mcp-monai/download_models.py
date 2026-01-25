#!/usr/bin/env python3
"""
Download all MONAI models for the MCP server.
Run this script once to download all pre-trained models.
"""

from monai.bundle import download
from pathlib import Path

BUNDLE_DIR = Path(__file__).parent / "bundles"
BUNDLE_DIR.mkdir(exist_ok=True)

MODELS = [
    {
        "name": "spleen_ct_segmentation",
        "description": "Spleen segmentation on CT - good for testing"
    },
    {
        "name": "swin_unetr_btcv_segmentation",
        "description": "Multi-organ segmentation (13 organs) on CT"
    },
    {
        "name": "pancreas_ct_dints_segmentation",
        "description": "Pancreas and tumor segmentation on CT"
    },
    {
        "name": "lung_nodule_ct_detection",
        "description": "Lung nodule detection on CT"
    },
]


def main():
    print(f"Downloading models to: {BUNDLE_DIR}")
    print("=" * 50)

    for model in MODELS:
        name = model["name"]
        desc = model["description"]
        bundle_path = BUNDLE_DIR / name

        if bundle_path.exists():
            print(f"[SKIP] {name} - already downloaded")
            continue

        print(f"\n[DOWNLOAD] {name}")
        print(f"  {desc}")

        try:
            download(
                name=name,
                bundle_dir=str(BUNDLE_DIR),
                source="monaihosting"
            )
            print(f"  Done!")
        except Exception as e:
            print(f"  ERROR: {e}")

    print("\n" + "=" * 50)
    print("Download complete!")

    # List downloaded models
    print("\nDownloaded models:")
    for p in BUNDLE_DIR.iterdir():
        if p.is_dir():
            print(f"  - {p.name}")


if __name__ == "__main__":
    main()
