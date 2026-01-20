#!/usr/bin/env python3
import os
import time
import json
import requests
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
FHIR_SERVER_URL = os.getenv("FHIR_SERVER_URL", "http://localhost:8080/fhir")
MCP_SERVER_URL = "http://localhost:8000"

# Direct API approach
def direct_api_search_patients(count=1):
    response = requests.get(f"{FHIR_SERVER_URL}/Patient?_count={count}")
    return response.json() if response.status_code == 200 else None

def direct_api_create_patient(patient_resource):
    response = requests.post(
        f"{FHIR_SERVER_URL}/Patient",
        json=patient_resource,
        headers={"Content-Type": "application/fhir+json"}
    )
    if response.status_code in [200, 201]:
        return response.json()
    else:
        print(f"❌ Direct API create failed: {response.status_code}")
        print(f"   Response: {response.text[:200]}")
        return None

# MCP approach
def mcp_search_patients(count=1):
    response = requests.post(
        f"{MCP_SERVER_URL}/mcp/tools/call",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        },
        json={
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "search",
                "arguments": {
                    "type": "Patient",
                    "searchParam": {"_count": str(count)}
                }
            },
            "id": 1
        }
    )
    if response.status_code == 200:
        result = response.json()
        mcp_result = result.get("result", {})
        content = mcp_result.get("content", [])
        if content and len(content) > 0:
            text = content[0].get("text", "")
            if text:
                return json.loads(text)
        return None
    return None

def mcp_create_patient(patient_resource):
    response = requests.post(
        f"{MCP_SERVER_URL}/mcp/tools/call",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        },
        json={
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "create",
                "arguments": {
                    "type": "Patient",
                    "payload": patient_resource
                }
            },
            "id": 2
        }
    )
    if response.status_code == 200:
        result = response.json()
        mcp_result = result.get("result", {})
        content = mcp_result.get("content", [])
        if content and len(content) > 0:
            text = content[0].get("text", "")
            if text:
                return json.loads(text)
        return None
    return None

# Anonymization (using Ollama for speed)
def anonymize_patient(patient_resource):
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

    ollama_response = requests.post("http://localhost:11434/api/generate", json={
        "model": "deepseek-r1:7b",
        "prompt": prompt,
        "stream": False
    })
    response_text = ollama_response.json()["response"]
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

def test_direct_api():
    """Test direct API approach"""
    print("\n" + "="*60)
    print("Testing DIRECT API approach")
    print("="*60)

    start_time = time.time()

    # Fetch patient
    bundle = direct_api_search_patients(count=1)
    if not bundle or not bundle.get("entry"):
        print("No patients found!")
        return None

    original_patient = bundle["entry"][0]["resource"]
    patient_id = original_patient["id"]
    print(f"Fetched patient: {patient_id}")

    # Anonymize
    anonymized = anonymize_patient(original_patient)
    if 'id' in anonymized:
        del anonymized['id']

    # Create
    new_patient = direct_api_create_patient(anonymized)
    new_id = new_patient.get("id") if new_patient else None

    end_time = time.time()
    elapsed = end_time - start_time

    print(f"Created anonymized patient: {new_id}")
    print(f"⏱️  Time taken: {elapsed:.3f} seconds")

    return elapsed

def test_mcp():
    """Test MCP approach"""
    print("\n" + "="*60)
    print("Testing MCP approach")
    print("="*60)

    start_time = time.time()

    # Fetch patient
    bundle = mcp_search_patients(count=1)
    if not bundle or not bundle.get("entry"):
        print("No patients found!")
        return None

    original_patient = bundle["entry"][0]["resource"]
    patient_id = original_patient["id"]
    print(f"Fetched patient: {patient_id}")

    # Anonymize
    anonymized = anonymize_patient(original_patient)
    if 'id' in anonymized:
        del anonymized['id']

    # Create
    new_patient = mcp_create_patient(anonymized)
    new_id = new_patient.get("id") if new_patient else None

    end_time = time.time()
    elapsed = end_time - start_time

    print(f"Created anonymized patient: {new_id}")
    print(f"⏱️  Time taken: {elapsed:.3f} seconds")

    return elapsed

if __name__ == "__main__":
    print("\n🔬 Performance Comparison: Direct API vs MCP")

    # Run tests
    direct_time = test_direct_api()
    mcp_time = test_mcp()

    # Compare
    if direct_time and mcp_time:
        print("\n" + "="*60)
        print("RESULTS")
        print("="*60)
        print(f"Direct API: {direct_time:.3f}s")
        print(f"MCP Server: {mcp_time:.3f}s")

        if mcp_time < direct_time:
            speedup = direct_time / mcp_time
            print(f"\n✨ MCP is {speedup:.2f}x FASTER")
        else:
            slowdown = mcp_time / direct_time
            print(f"\n⚠️  MCP is {slowdown:.2f}x slower")

        print("="*60)
