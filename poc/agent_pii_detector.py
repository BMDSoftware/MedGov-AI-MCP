import os
from google import genai
from dotenv import load_dotenv
import json
import requests

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# server running locally
FHIR_SERVER_URL = os.getenv("FHIR_SERVER_URL", "http://localhost:8080/fhir")



# set models rules for anonymization
def anonymize_patient(patient_resource, use_ollama=False):
    """
    Anonymizes a FHIR Patient resource using AI.
    Returns the anonymized patient resource.
    """

    prompt = f"""
You are a healthcare data anonymization expert. Given this FHIR Patient resource, return the ANONYMIZED version.

Original Patient:
{json.dumps(patient_resource, indent=2)}

ANONYMIZATION RULES:
1. REMOVE these fields completely:
   - text (remove entire field)
   - name (remove all)
   - identifier (remove all)
   - telecom (remove all)
   - address.line (remove)
   - extension (remove all)

2. GENERALIZE:
   - birthDate: "1990-05-15" → "1990-01-01" (year only)
   - address.postalCode: "02101" → "021XX"

3. KEEP:
   - resourceType: "Patient"
   - gender
   - address (only city, state, country - no line/street)

Return ONLY valid FHIR R4 Patient JSON. Do not include invalid status values.
"""

    # either run locally with Ollama or via Gemini API
    if use_ollama:
        ollama_response = requests.post("http://localhost:11434/api/generate", json={
            "model": "deepseek-r1:7b",
            "prompt": prompt,
            "stream": False
        })
        response_text = ollama_response.json()["response"]
    else:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        response_text = response.text

    text = response_text.strip()

    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        json_text = text[start:end].strip()
    else:
        start = text.find("{")
        end = text.rfind("}") + 1
        json_text = text[start:end]

    anonymized_patient = json.loads(json_text)
    return anonymized_patient


if __name__ == "__main__":
    print("Choose AI Model:")
    print("1. Ollama (deepseek-r1:7b) Local")
    print("2. Gemini (gemini-2.5-flash) API")
    choice = input("\nEnter 1 or 2: ").strip()

    use_ollama = (choice == "1")

    print("Fetching real patient from FHIR server...")

    response = requests.get(f"{FHIR_SERVER_URL}/Patient?_count=1")

    if response.status_code == 200:
        bundle = response.json()
        if bundle.get("entry") and len(bundle["entry"]) > 0:
            original_patient = bundle["entry"][0]["resource"]
            patient_id = original_patient["id"]

            print(f"Original patient ID: {patient_id}")
            print(f"Anonymizing...\n")
            anonymized = anonymize_patient(original_patient, use_ollama=use_ollama)


            # i need to create a new resource so ill remove the id
            # so the server can assign a new one
            if 'id' in anonymized:
                del anonymized['id']

            # just save to the FHIR server
            create_response = requests.post(
                f"{FHIR_SERVER_URL}/Patient",
                json=anonymized,
                headers={"Content-Type": "application/fhir+json"}
            )

            if create_response.status_code in [200, 201]:
                new_patient = create_response.json()
                new_id = new_patient.get("id")
                print(f"Anonymized patient created: {new_id}")
                print(f"\nOriginal: {FHIR_SERVER_URL}/Patient/{patient_id}")
                print(f"Anonymized: {FHIR_SERVER_URL}/Patient/{new_id}")
            else:
                print(f"Error: {create_response.status_code}")
                print(create_response.text)
        else:
            # right now because we're using the upload_patients.py 
            # we need to upload due to it being synthetic data
            # but we're uploading directly to the server
            # so we're simulating it
            print("No patients found in FHIR server!")
    else:
        print(f"Error fetching from FHIR server: {response.status_code}")
        print(response.text)



# To see the anonymized result just run CURL
# curl http://localhost:8080/fhir/Patient/{new_id}
# or access via FHIR client
# or I could put a print XD or write onto a local file but it's fine