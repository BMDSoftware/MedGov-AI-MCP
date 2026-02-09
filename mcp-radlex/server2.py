#!/usr/bin/env python3
import logging
import sys
from typing import Any, Dict, List, Optional
from datetime import datetime

import httpx
from bs4 import BeautifulSoup
from mcp.server.fastmcp import FastMCP

# Keep noisy library logs off stdout (MCP uses stdout for the protocol).
logging.basicConfig(stream=sys.stderr, level=logging.WARNING, force=True)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# --- Configuration ---
API_BASE = "https://api3.rsna.org/radreport/v1"
# Some RSNA endpoints prefer a real User-Agent to avoid being blocked
HEADERS = {
    "User-Agent": "AgenticHealth-RadReport-Agent/1.0",
    "Accept": "application/json"
}

mcp = FastMCP("RadReport-Pro")


def _normalize_subspecialty_payload(payload: Any) -> List[Any]:
    """Extract subspecialty list from API response."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        return payload.get("DATA", payload.get("results", []))
    return []


def _coerce_subspecialty_item(item: Any) -> Optional[Dict[str, str]]:
    """Parse a single subspecialty item."""
    if isinstance(item, str):
        return {"code": item, "name": item}
    if isinstance(item, dict):
        code = item.get("code", "")
        name = item.get("name", "")
        if code or name:
            return {"code": code, "name": name}
    return None


async def get_subspecialties() -> List[Dict[str, str]]:
    """Fetch valid subspecialty codes (NR, CH, etc.)."""
    async with httpx.AsyncClient(headers=HEADERS, timeout=10, follow_redirects=True) as client:
        try:
            response = await client.get(f"{API_BASE}/subspecialty/")
            response.raise_for_status()
            status = response.status_code
            content_type = response.headers.get("content-type", "")

            try:
                payload = response.json()
            except Exception as parse_err:
                snippet = response.text[:400]
                return [{"error": f"Failed to parse subspecialties: status={status}, content_type={content_type}, detail={parse_err}, body_snippet={snippet}"}]

            items = _normalize_subspecialty_payload(payload)
            if not items:
                return [{"error": f"No subspecialties returned: status={status}, content_type={content_type}, payload_snippet={str(payload)[:200]}"}]

            result: List[Dict[str, str]] = []
            for it in items:
                parsed = _coerce_subspecialty_item(it)
                if parsed is not None:
                    result.append(parsed)
            return result if result else [{"error": "No valid subspecialties parsed"}]
        except Exception as e:
            return [{"error": f"Failed to fetch subspecialties: {str(e)}"}]

async def search_templates(query: Optional[str] = None, specialty: Optional[str] = None) -> List[Dict[str, Any]]:
    """Search templates by keyword or specialty code."""
    async with httpx.AsyncClient(headers=HEADERS, timeout=10, follow_redirects=True) as client:
        params = {}
        if query: params["search"] = query
        if specialty: params["specialty"] = specialty
        
        try:
            response = await client.get(f"{API_BASE}/templates", params=params)
            response.raise_for_status()
            status = response.status_code
            content_type = response.headers.get("content-type", "")

            try:
                payload = response.json()
            except Exception as parse_err:
                snippet = response.text[:400]
                return [{"error": f"Failed to parse templates: status={status}, content_type={content_type}, detail={parse_err}, body_snippet={snippet}"}]

            templates = []
            if isinstance(payload, dict):
                templates = payload.get("DATA", payload.get("results", []))
            elif isinstance(payload, list):
                templates = payload

            if not templates:
                return [{"error": f"No templates found for query={query}, specialty={specialty}"}]

            return templates
        except Exception as e:
            return [{"error": f"Search failed: {str(e)}"}]

async def _fetch_and_parse_template(template_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch template HTML from API and parse into structured schema."""
    async with httpx.AsyncClient(headers=HEADERS, timeout=10) as client:
        response = await client.get(f"{API_BASE}/templates/{template_id}/details", params=params)
        status = response.status_code
        content_type = response.headers.get("content-type", "")
        try:
            response.raise_for_status()
        except Exception as e:
            snippet = response.text[:400]
            return {"error": f"details request failed: status={status}, content_type={content_type}, params={params}, detail={e}, body_snippet={snippet}"}

        try:
            data = response.json()
        except Exception as parse_err:
            snippet = response.text[:400]
            return {"error": f"details parse failed: status={status}, content_type={content_type}, params={params}, detail={parse_err}, body_snippet={snippet}"}

        html_content = data.get("DATA", "")
        html_content = html_content.get("templateData", "") if isinstance(html_content, dict) else html_content
        if not html_content:
            return {"error": f"details missing template html: status={status}, params={params}, payload_snippet={str(data)[:200]}"}

        return _parse_mrrt(html_content, template_id, data.get("title", "Untitled"))


async def fetch_template_details(template_id: str, version: Optional[str] = None) -> Dict[str, Any]:
    """Fetch MRRT content using details endpoint."""
    params = {"version": version} if version else {}
    result = await _fetch_and_parse_template(template_id, params)  # Changed
    
    if "error" not in result:
        return result
    
    # If version specified and failed, try without version as fallback
    if version:
        result = await _fetch_and_parse_template(template_id, {})  # Changed
        if "error" not in result:
            return result
    
    return {"error": f"Failed to fetch template {template_id}", "details": result.get("error")}


def _parse_mrrt(html: str, t_id: str, title: str) -> Dict[str, Any]:
    """Parses IHE MRRT HTML into a structured schema for the LLM"""
    soup = BeautifulSoup(html, 'html.parser')
    structured_sections = []
    all_fields = {}

    # Find sections (IHE MRRT standard uses <section> tags)
    sections = soup.find_all('section')
    if not sections:
        sections = soup.find_all('div', attrs={"data-section-name": True})

    for section in sections:
        s_title_tag = section.find(['h1', 'h2', 'h3', 'header', 'b'])
        s_title = s_title_tag.text.strip() if s_title_tag else section.get('data-section-name', "General")
        s_title = str(s_title) if s_title is not None else "General"
        
        if any(x in s_title.upper() for x in ["INSTRUCTION", "REVISION", "AUTHORS"]):
            continue

        section_data = {"section_title": s_title, "fields": []}

        for inp in section.find_all(['input', 'select', 'textarea']):
            f_id = inp.get('id') or inp.get('name')
            if not f_id: continue

            f_id = str(f_id)
            
            label_tag = soup.find('label', attrs={"for": f_id})
            label_text = label_tag.text.strip() if label_tag else ""
            
            if not label_text:
                label_text = f_id.replace("TEXT_", "").replace("_", " ").title()

            field_info = {
                "html_id": f_id,
                "label": label_text,
                "type": inp.get('type') or inp.name,
                "options": [opt.text.strip() for opt in inp.find_all('option')] if inp.name == 'select' else []
            }
            
            section_data["fields"].append(field_info)
            all_fields[f_id] = field_info

        if section_data["fields"]:
            structured_sections.append(section_data)

    return {
        "id": t_id,
        "title": title,
        "structured_sections": structured_sections,
        "all_fields": all_fields
    }

# --- MCP Tool Definitions ---

@mcp.tool()
async def list_subspecialties() -> List[Dict[str, str]]:
    """Get valid radiology specialty codes (e.g., NR for Neuroradiology, CH for Chest)."""
    return await get_subspecialties()

@mcp.tool()
async def find_templates(query: Optional[str] = None, specialty_code: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Search for templates. Use specialty_code from list_subspecialties for better accuracy.
    
    Args:
        query: Optional search keyword for template names
        specialty_code: Subspecialty code as a string (e.g., "AB", "NR", "CH"). 
                       Use the 'code' value from list_subspecialties, not the full object.
    """
    # Handle case where LLM passes {"code": "AB"} instead of "AB"
    if isinstance(specialty_code, dict) and "code" in specialty_code:
        specialty_code = specialty_code["code"]
    
    return await search_templates(query=query, specialty=specialty_code)

@mcp.tool()
async def get_template_schema(template_id: str, version: Optional[str] = None) -> Dict[str, Any]:
    """Fetch the structured schema for a specific template to see which fields need to be filled."""
    return await fetch_template_details(template_id, version=version)

@mcp.tool()
async def generate_report(template_id: str, findings: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generates a professional radiology report using the findings provided.
    findings: A dictionary where keys are html_id from the schema and values are the findings.
    """
    template_data = await fetch_template_details(template_id)
    
    if "error" in template_data:
        return template_data

    # 1. Build Text Version
    report_lines = [
        f"REPORT: {template_data['title'].upper()}",
        f"DATE: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "=" * 40, ""
    ]
    
    for section in template_data["structured_sections"]:
        section_content = []
        for field in section["fields"]:
            val = findings.get(field["html_id"])
            if val:
                section_content.append(f"{field['label']}: {val}")
        
        if section_content:
            report_lines.append(f"[{section['section_title'].upper()}]")
            report_lines.extend(section_content)
            report_lines.append("")

    # 2. Build HTML Version (Professional Medical Style)
    html = f"""
    <html>
    <head><style>
        body {{ font-family: sans-serif; line-height: 1.5; color: #333; max-width: 700px; margin: auto; }}
        h1 {{ border-bottom: 2px solid #2c3e50; color: #2c3e50; font-size: 20px; text-transform: uppercase; }}
        .section {{ margin-top: 20px; }}
        .section-title {{ font-weight: bold; background: #eee; padding: 5px; display: block; }}
        .field {{ margin: 5px 0 5px 15px; }}
        .label {{ font-weight: bold; color: #555; }}
    </style></head>
    <body>
        <h1>{template_data['title']}</h1>
        <p><i>Generated via AgenticHealth MCP on {datetime.now().isoformat()}</i></p>
    """
    
    for section in template_data["structured_sections"]:
        has_data = any(findings.get(f["html_id"]) for f in section["fields"])
        if has_data:
            html += f"<div class='section'><span class='section-title'>{section['section_title']}</span>"
            for field in section["fields"]:
                val = findings.get(field["html_id"])
                if val:
                    html += f"<div class='field'><span class='label'>{field['label']}:</span> {val}</div>"
            html += "</div>"
    
    html += "</body></html>"

    return {
        "text_report": "\n".join(report_lines),
        "html_report": html,
        "template_id": template_id,
        "status": "Finalized"
    }

if __name__ == "__main__":
    mcp.run()