import os
from google import genai
from dotenv import load_dotenv
import json

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def detect_pii(patient_resource):
    """
    Uses Gemini to intelligently detect PII in a FHIR Patient resource.
    Context-aware detection, not just regex.
    """

    prompt = f"""
You are a healthcare data privacy expert. Analyze this FHIR Patient resource and identify ALL Personal Identifiable Information (PII).

FHIR Patient Resource:
{json.dumps(patient_resource, indent=2)}

Classify each field into:
1. **Direct Identifiers** (MUST remove): Names, SSN, phone, email, addresses, IDs
2. **Quasi-Identifiers** (generalize): Birth date, zip code, race, ethnicity
3. **Safe Data** (keep as-is): Gender (if common), clinical codes

Return a JSON object with:
{{
  "direct_identifiers": ["field.path.to.pii", ...],
  "quasi_identifiers": ["field.path", ...],
  "risk_level": "HIGH|MEDIUM|LOW",
  "reasoning": "brief explanation"
}}
"""

    # ---- Using Gemini ----
    # I got gemini pro from student discount for free
    # Using gemini-2.5-flash (free tier working model)
    # Change if out of tokens or use another model

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    # Debug: print raw response
    print("Raw response:")
    print(response.text)
    print("\n" + "="*60 + "\n")

    cleaned_text = response.text.strip().replace("```json", "").replace("```", "")
    result = json.loads(cleaned_text)
    return result


# mock data for testing
if __name__ == "__main__":
    test_patient = {
        "resourceType": "Patient",
        "id": "123",
        "name": [{"family": "Smith", "given": ["John"]}],
        "birthDate": "1990-05-15",
        "gender": "male",
        "address": [{"city": "Boston", "state": "MA", "postalCode": "02101"}],
        "telecom": [{"system": "phone", "value": "555-1234"}]
    }

    result = detect_pii(test_patient)
    print(json.dumps(result, indent=2))
