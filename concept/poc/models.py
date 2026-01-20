import os
import json
import requests
from google import genai
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


MANDATORY_PII_FIELDS = [
    "name", "firstName", "lastName", "middleName", "fullName",
    "ssn", "socialSecurityNumber", "passport", "nationalId",
    "phone", "phoneNumber", "mobile", "telephone", "telecom",
    "email", "emailAddress",
    "identifier", "patientId", "mrn", "medicalRecordNumber",
    "address.line", "street", "streetAddress", "addressLine1",
    "ipAddress", "deviceId", "userId"
]

ANONYMIZATION_RULES = """
ANONYMIZATION RULES:

1. MANDATORY - REMOVE completely:
   - Full names, SSN, phone, email, patient IDs
   - Street addresses (keep only city, state, country)
   - IP addresses, device IDs

2. MANDATORY - GENERALIZE:
   - Dates of birth: Year only OR age ranges
   - Exact dates: Shift or reduce precision
   - Postal codes: Mask last digits

3. KEEP:
   - Gender, general location
   - Medical data, diagnoses, treatments, vitals

4. CONTEXT-AWARE:
   - Children: exact ages if medically critical
   - Adults: age ranges
   - Clinical notes: redact PII, keep medical context

Return ONLY the anonymized data in the SAME format as input.
"""


def anonymize_with_ai(patient_data, use_ollama=False):
    prompt = f"""
You are a healthcare data anonymization expert. Analyze this patient data and return the ANONYMIZED version.

Original Data:
{json.dumps(patient_data, indent=2) if isinstance(patient_data, dict) else patient_data}

{ANONYMIZATION_RULES}

Return ONLY the anonymized data in the SAME format as the input. Do not add explanations.
"""

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
    elif "```" in text:
        start = text.find("```") + 3
        end = text.rfind("```")
        json_text = text[start:end].strip()
    else:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            json_text = text[start:end]
        else:
            json_text = text

    try:
        anonymized_data = json.loads(json_text)
    except json.JSONDecodeError:
        anonymized_data = {"error": "Failed to parse AI response", "raw": text}

    return anonymized_data
