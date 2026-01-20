import json
from typing import List, Dict, Any
from models import client, MANDATORY_PII_FIELDS

def detect_pii_fields_with_ai(data: Any) -> List[str]:
    prompt = f"""
Analyze this data and identify ALL fields that contain Personal Identifiable Information (PII).

Data:
{json.dumps(data, indent=2) if isinstance(data, dict) else data}

Return ONLY a JSON array of field names that contain PII.
Look for:
- Names, identifiers, contact info
- Addresses, coordinates
- Dates that could identify individuals
- Any other sensitive personal data

Example output: ["patientName", "contactPhone", "homeAddress", "birthDate"]

Return ONLY the JSON array, nothing else.
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    text = response.text.strip()

    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        json_text = text[start:end].strip()
    elif "```" in text:
        start = text.find("```") + 3
        end = text.rfind("```")
        json_text = text[start:end].strip()
    elif "[" in text:
        start = text.find("[")
        end = text.rfind("]") + 1
        json_text = text[start:end]
    else:
        return []

    try:
        detected_fields = json.loads(json_text)
        return detected_fields if isinstance(detected_fields, list) else []
    except:
        return []


def get_all_pii_fields(data: Any) -> tuple[List[str], List[str]]:
    hardcoded = []
    ai_detected = []

    if isinstance(data, dict):
        for field in MANDATORY_PII_FIELDS:
            if field in data or field.replace(".", "_") in str(data):
                hardcoded.append(field)

        ai_detected = detect_pii_fields_with_ai(data)

    combined = list(set(hardcoded + ai_detected))

    return hardcoded, ai_detected
