#!/bin/sh
set -e

SAMPLE_EXAMS="/app/orchestrator/sample_data/exams"

if [ ! -d "$SAMPLE_EXAMS" ] || [ -z "$(find "$SAMPLE_EXAMS" -type f -name '*.dcm' -print -quit 2>/dev/null)" ]; then
    echo "Downloading sample CT data from TCIA..."
    /app/orchestrator/venv/bin/python /app/orchestrator/sample_data/download_sample_data.py
else
    echo "Sample CT data already present, skipping download."
fi

exec "$@"
