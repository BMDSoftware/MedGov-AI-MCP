#!/usr/bin/env python3
import logging
import sys
from typing import Any, Dict, List, Optional

import httpx
from mcp.server.fastmcp import FastMCP

from template_filler import build_template_schema, fill_template_html, validate_findings

# Keep noisy library logs off stdout (MCP uses stdout for the protocol).
logging.basicConfig(stream=sys.stderr, level=logging.WARNING, force=True)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# --- Configuration ---
API_BASE = "https://api3.rsna.org/radreport/v1"
HEADERS = {
    "User-Agent": "AgenticHealth-RadReport-Agent/1.0",
    "Accept": "application/json",
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


def _template_fetch_error(
    template_id: str,
    message: str,
    details: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "error": message,
        "error_type": "template_fetch_error",
        "details": {"template_id": template_id, **details},
    }


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
                return [
                    {
                        "error": (
                            "Failed to parse subspecialties: "
                            f"status={status}, content_type={content_type}, "
                            f"detail={parse_err}, body_snippet={snippet}"
                        )
                    }
                ]

            items = _normalize_subspecialty_payload(payload)
            if not items:
                return [
                    {
                        "error": (
                            "No subspecialties returned: "
                            f"status={status}, content_type={content_type}, "
                            f"payload_snippet={str(payload)[:200]}"
                        )
                    }
                ]

            result: List[Dict[str, str]] = []
            for item in items:
                parsed = _coerce_subspecialty_item(item)
                if parsed is not None:
                    result.append(parsed)
            return result if result else [{"error": "No valid subspecialties parsed"}]
        except Exception as exc:
            return [{"error": f"Failed to fetch subspecialties: {exc}"}]


async def search_templates(
    query: Optional[str] = None,
    specialty: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Search templates by keyword or specialty code."""
    async with httpx.AsyncClient(headers=HEADERS, timeout=10, follow_redirects=True) as client:
        params: Dict[str, str] = {}
        if query:
            params["search"] = query
        if specialty:
            params["specialty"] = specialty

        try:
            response = await client.get(f"{API_BASE}/templates", params=params)
            response.raise_for_status()
            status = response.status_code
            content_type = response.headers.get("content-type", "")

            try:
                payload = response.json()
            except Exception as parse_err:
                snippet = response.text[:400]
                return [
                    {
                        "error": (
                            "Failed to parse templates: "
                            f"status={status}, content_type={content_type}, "
                            f"detail={parse_err}, body_snippet={snippet}"
                        )
                    }
                ]

            templates: List[Dict[str, Any]] = []
            if isinstance(payload, dict):
                templates = payload.get("DATA", payload.get("results", []))
            elif isinstance(payload, list):
                templates = payload

            if not templates:
                return [{"error": f"No templates found for query={query}, specialty={specialty}"}]

            return templates
        except Exception as exc:
            return [{"error": f"Search failed: {exc}"}]


async def fetch_template_html(template_id: str) -> Dict[str, Any]:
    """Fetch template HTML from the RadReport API (latest revision)."""
    async with httpx.AsyncClient(headers=HEADERS, timeout=10, follow_redirects=True) as client:
        try:
            response = await client.get(f"{API_BASE}/templates/{template_id}/details")
        except Exception as exc:
            return _template_fetch_error(
                template_id,
                "Failed to fetch template from RadReport API.",
                {"detail": str(exc)},
            )

        status = response.status_code
        content_type = response.headers.get("content-type", "")
        if status >= 400:
            snippet = response.text[:400]
            return _template_fetch_error(
                template_id,
                "RadReport API returned an error for template details.",
                {
                    "status": status,
                    "content_type": content_type,
                    "body_snippet": snippet,
                },
            )

        try:
            payload = response.json()
        except Exception as parse_err:
            snippet = response.text[:400]
            return _template_fetch_error(
                template_id,
                "Failed to parse RadReport template details response.",
                {
                    "status": status,
                    "content_type": content_type,
                    "detail": str(parse_err),
                    "body_snippet": snippet,
                },
            )

        data_block = payload.get("DATA", "")
        template_html = (
            data_block.get("templateData", "") if isinstance(data_block, dict) else data_block
        )
        template_title = (
            data_block.get("title")
            if isinstance(data_block, dict)
            else None
        ) or payload.get("title", "Untitled")

        if not template_html:
            return _template_fetch_error(
                template_id,
                "Template HTML is missing in RadReport API response.",
                {
                    "status": status,
                    "payload_snippet": str(payload)[:300],
                },
            )

        return {
            "template_id": template_id,
            "template_title": str(template_title),
            "html_template": str(template_html),
        }


# --- MCP Tool Definitions ---

@mcp.tool()
async def list_subspecialties() -> List[Dict[str, str]]:
    """Get valid radiology specialty codes (e.g., NR for Neuroradiology, CH for Chest)."""
    return await get_subspecialties()


@mcp.tool()
async def find_templates(
    query: Optional[str] = None,
    specialty_code: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Search for templates. Use specialty_code from list_subspecialties for better accuracy.

    Args:
        query: Optional search keyword for template names.
        specialty_code: Subspecialty code string (e.g., "AB", "NR", "CH").
    """
    # Handle case where LLM passes {"code": "AB"} instead of "AB"
    if isinstance(specialty_code, dict) and "code" in specialty_code:
        specialty_code = specialty_code["code"]

    return await search_templates(query=query, specialty=specialty_code)


@mcp.tool()
async def get_template_schema(template_id: str) -> Dict[str, Any]:
    """
    Fetch a template schema from RadReport API HTML (latest revision).

    Returns normalized field metadata including key, aliases, control_type,
    options, and section grouping to guide exact field mapping.
    """
    template_payload = await fetch_template_html(template_id)
    if "error" in template_payload:
        return template_payload

    return build_template_schema(
        template_html=template_payload["html_template"],
        template_id=template_payload["template_id"],
        template_title=template_payload["template_title"],
    )


@mcp.tool()
async def generate_report(
    template_id: str,
    findings: Dict[str, Any],
    report_title: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Fill an exact RadReport template DOM in-place using findings.

    Rules:
    - Template source is always RadReport API HTML.
    - Unknown findings keys return hard error (unknown_fields).
    - Invalid select/radio values return hard error (invalid_choice).
    - Unspecified fields keep original template defaults.
    """
    template_payload = await fetch_template_html(template_id)
    if "error" in template_payload:
        return template_payload

    schema = build_template_schema(
        template_html=template_payload["html_template"],
        template_id=template_payload["template_id"],
        template_title=template_payload["template_title"],
    )
    if "error" in schema:
        return schema

    validation_result = validate_findings(findings=findings, all_fields=schema["all_fields"])
    if "error" in validation_result:
        return validation_result

    fill_result = fill_template_html(
        template_html=template_payload["html_template"],
        all_fields=schema["all_fields"],
        normalized_findings=validation_result["normalized"],
    )
    if "error" in fill_result:
        return fill_result

    applied_fields = validation_result["applied_fields"]
    total_fields = len(schema["all_fields"])

    return {
        "status": "Finalized",
        "template_id": template_id,
        "template_title": schema["title"],
        "report_title": report_title or schema["title"],
        "html_report": fill_result["html_report"],
        "applied_fields": applied_fields,
        "preserved_defaults_count": max(total_fields - len(applied_fields), 0),
        "validation": validation_result["validation"],
    }


if __name__ == "__main__":
    mcp.run()
