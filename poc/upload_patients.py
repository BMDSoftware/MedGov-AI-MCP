#!/usr/bin/env python3
"""
Upload Synthea FHIR bundles to HAPI FHIR server
"""
import requests
import json
import os
import glob

FHIR_SERVER_URL = "http://localhost:8080/fhir"
SYNTHEA_OUTPUT_DIR = "../synthea/output/fhir"

def upload_bundle(file_path):
    """Upload a FHIR bundle to the server"""
    filename = os.path.basename(file_path)

    # Skip if already uploaded (hospital/practitioner)
    if "hospital" in filename.lower() or "practitioner" in filename.lower():
        print(f"⏭️  Skipping {filename} (already uploaded)")
        return None

    print(f"📤 Uploading {filename}...", end=" ")

    try:
        with open(file_path, 'r') as f:
            bundle = json.load(f)

        response = requests.post(
            FHIR_SERVER_URL,
            headers={"Content-Type": "application/fhir+json"},
            json=bundle
        )

        if response.status_code in [200, 201]:
            print("✅ Success")
            return True
        else:
            print(f"❌ Failed ({response.status_code})")
            print(f"   Error: {response.text[:200]}")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    print("=" * 60)
    print("Uploading Synthea patients to HAPI FHIR server")
    print("=" * 60)

    # Get all JSON files
    pattern = os.path.join(SYNTHEA_OUTPUT_DIR, "*.json")
    files = glob.glob(pattern)

    if not files:
        print(f"❌ No files found in {SYNTHEA_OUTPUT_DIR}")
        return

    print(f"\nFound {len(files)} files\n")

    success_count = 0
    fail_count = 0
    skip_count = 0

    for file_path in sorted(files):
        result = upload_bundle(file_path)
        if result is True:
            success_count += 1
        elif result is False:
            fail_count += 1
        else:
            skip_count += 1

    print("\n" + "=" * 60)
    print(f"✅ Uploaded: {success_count}")
    print(f"⏭️  Skipped: {skip_count}")
    print(f"❌ Failed: {fail_count}")
    print("=" * 60)

if __name__ == "__main__":
    main()
