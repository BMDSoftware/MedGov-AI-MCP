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
    filename = os.path.basename(file_path)

    if "hospital" in filename.lower() or "practitioner" in filename.lower():
        print(f"Skipping {filename}")
        return None

    print(f"Uploading {filename}...", end=" ")

    try:
        with open(file_path, 'r') as f:
            bundle = json.load(f)

        if bundle.get("resourceType") != "Bundle":
            print("Not a bundle, skipping")
            return None

        entries = bundle.get("entry", [])
        patient_resource = None

        for entry in entries:
            resource = entry.get("resource", {})
            if resource.get("resourceType") == "Patient":
                patient_resource = resource
                break

        if not patient_resource:
            print("No Patient resource found")
            return None

        response = requests.post(
            f"{FHIR_SERVER_URL}/Patient",
            headers={"Content-Type": "application/fhir+json"},
            json=patient_resource
        )

        if response.status_code in [200, 201]:
            result = response.json()
            patient_id = result.get("id")
            print(f"Success - ID: {patient_id}")
            return True
        else:
            print(f"Failed ({response.status_code})")
            return False

    except Exception as e:
        print(f"Error: {e}")
        return False

def main():
    print("Uploading Synthea patients to HAPI FHIR server")
    print("-" * 60)

    pattern = os.path.join(SYNTHEA_OUTPUT_DIR, "*.json")
    files = glob.glob(pattern)

    if not files:
        print(f"No files found in {SYNTHEA_OUTPUT_DIR}")
        return

    print(f"Found {len(files)} files\n")

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

    print(f"\nUploaded: {success_count}")
    print(f"Skipped: {skip_count}")
    print(f"Failed: {fail_count}")

if __name__ == "__main__":
    main()
