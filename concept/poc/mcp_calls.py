import os
import json
import requests
from dotenv import load_dotenv
from typing import Optional, Dict, Any, Callable

load_dotenv()

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8000")

_tool_call_callback: Optional[Callable] = None

def set_tool_callback(callback: Callable):
    global _tool_call_callback
    _tool_call_callback = callback

def _call_mcp_tool(tool_name: str, arguments: Dict[str, Any]) -> Optional[Dict]:
    if _tool_call_callback:
        _tool_call_callback("before", tool_name, arguments)

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
                "name": tool_name,
                "arguments": arguments
            },
            "id": 1
        }
    )

    result = None
    if response.status_code == 200:
        result_json = response.json()
        mcp_result = result_json.get("result", {})
        content = mcp_result.get("content", [])
        if content and len(content) > 0:
            text = content[0].get("text", "")
            if text:
                result = json.loads(text)

    if _tool_call_callback:
        _tool_call_callback("after", tool_name, result)

    return result


def search_patients(count=1):
    return _call_mcp_tool("search", {
        "type": "Patient",
        "searchParam": {"_count": str(count)}
    })

def create_patient(patient_resource):
    return _call_mcp_tool("create", {
        "type": "Patient",
        "payload": patient_resource
    })

def read_patient(patient_id):
    return _call_mcp_tool("read", {
        "type": "Patient",
        "id": patient_id
    })

def update_patient(patient_id, patient_resource):
    return _call_mcp_tool("update", {
        "type": "Patient",
        "id": patient_id,
        "payload": patient_resource
    })

def delete_patient(patient_id):
    return _call_mcp_tool("delete", {
        "type": "Patient",
        "id": patient_id
    })
