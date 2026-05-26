#!/usr/bin/env python3
"""Download TCIA sample CT series for the DICOM analysis use case."""
import sys
from pathlib import Path

from tcia_utils import nbia

MANIFEST = Path(__file__).parent / "pancreas-ct.tcia"
OUTPUT_DIR = Path(__file__).parent / "exams"

if OUTPUT_DIR.exists() and any(d.is_dir() and any(d.glob("*.dcm")) for d in OUTPUT_DIR.iterdir()):
    print("Sample CT data already present, skipping download.")
    sys.exit(0)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
nbia.downloadSeries(str(MANIFEST), input_type="manifest", path=str(OUTPUT_DIR))
print(f"Download complete. Exams saved under {OUTPUT_DIR}")
