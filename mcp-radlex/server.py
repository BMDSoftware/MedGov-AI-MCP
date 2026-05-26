#!/usr/bin/env python3
import json
import logging
import re
import sys
from pathlib import Path
from typing import Annotated, Any, Dict, List, Optional
from pydantic import Field

import httpx
from mcp import types as mcp_types
from mcp.server.fastmcp import Context, FastMCP

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

            approved = [t for t in templates if t.get("TLAP_Approved") == "1"]
            english = [t for t in approved if (t.get("lang") or "English").lower() == "english"]
            filtered = english if english else approved
            return filtered if filtered else [{"error": f"No TLAP-approved templates found for query={query}, specialty={specialty}"}]
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


_GROUNDING_RULE = (
    " Only use measurements and findings explicitly present in the provided inference results — "
    "do not invent structures, values, or findings that are not in the data. "
    "You may apply established clinical reference knowledge (normal ranges, grading criteria, "
    "clinical significance thresholds) to interpret the given measurements and populate "
    "assessment, impression, and recommendation fields accordingly."
)

SPECIALTY_SYSTEM_PROMPTS = {
    "general": (
        "You are a board-certified radiologist. Map the provided AI inference results to "
        "the given template fields." + _GROUNDING_RULE
    ),
    "oncology": (
        "You are a board-certified radiologist subspecialised in oncologic imaging. "
        "Prioritize lesion size, enhancement pattern, TNM staging, and treatment response (RECIST 1.1). "
        "Use formal ACR RADS language." + _GROUNDING_RULE
    ),
    "cardiology": (
        "You are a board-certified radiologist subspecialised in cardiac imaging. "
        "Prioritize ejection fraction, wall motion, pericardial effusion, and valve morphology. "
        "Use AHA/ACC terminology." + _GROUNDING_RULE
    ),
    "emergency": (
        "You are a board-certified emergency radiologist. "
        "Lead with time-critical findings (pneumothorax, hemorrhage, PE, dissection). "
        "Be concise. Use STAT-level conventions." + _GROUNDING_RULE
    ),
    "neuroradiology": (
        "You are a board-certified neuroradiologist. "
        "Prioritize lesion location, signal characteristics, mass effect, midline shift, "
        "and enhancement pattern. Use ACR brain reporting guidelines." + _GROUNDING_RULE
    ),
    "musculoskeletal": (
        "You are a board-certified musculoskeletal radiologist. "
        "Prioritize joint space, cortical integrity, bone marrow signal, and tendon/ligament continuity."
        + _GROUNDING_RULE
    ),
}


# --- MCP Tool Definitions ---

_SUBSPECIALTIES_WITH_TEMPLATES = [
    {"code": "CA", "name": "Cardiac Radiology"},
    {"code": "CH", "name": "Chest Radiology"},
    {"code": "CT", "name": "Computed Tomography"},
    {"code": "ER", "name": "Emergency Radiology"},
    {"code": "GI", "name": "Gastrointestinal Radiology"},
    {"code": "GU", "name": "Genitourinary Radiology"},
    {"code": "HN", "name": "Head and Neck"},
    {"code": "IR", "name": "Interventional Radiology"},
    {"code": "MK", "name": "Musculoskeletal Radiology"},
    {"code": "MR", "name": "Magnetic Resonance Imaging"},
    {"code": "NM", "name": "Nuclear Medicine"},
    {"code": "NR", "name": "Neuroradiology"},
    {"code": "OB", "name": "OB/GYN Radiology"},
    {"code": "OI", "name": "Oncologic Imaging"},
    {"code": "PD", "name": "Pediatric Radiology"},
    {"code": "QI", "name": "Quality Improvement"},
    {"code": "RS", "name": "Research"},
    {"code": "US", "name": "Ultrasound"},
    {"code": "VI", "name": "Vascular Imaging"},
]


@mcp.tool()
async def list_subspecialties() -> List[Dict[str, str]]:
    """Get valid radiology specialty codes (e.g., NR for Neuroradiology, CH for Chest).
    Only includes subspecialties confirmed to have TLAP-approved templates available."""
    return _SUBSPECIALTIES_WITH_TEMPLATES


@mcp.tool()
async def find_templates(
    query: Annotated[Optional[str], Field(description="Optional search keyword for template names")] = None,
    specialty_code: Annotated[Optional[str], Field(description='Subspecialty code string (e.g., "AB", "NR", "CH"). Use list_subspecialties for valid codes.')] = None,
) -> List[Dict[str, Any]]:
    """Search for RadReport templates. Use specialty_code from list_subspecialties for better accuracy."""
    # Handle case where LLM passes {"code": "AB"} instead of "AB"
    if isinstance(specialty_code, dict) and "code" in specialty_code:
        specialty_code = specialty_code["code"]

    return await search_templates(query=query, specialty=specialty_code)



@mcp.tool()
async def generate_radiology_report(
    template_id: Annotated[str, Field(description="RadReport template ID (from find_templates)")],
    output_path: Annotated[str, Field(description="File path to save the HTML report. The report is not returned inline — it must be saved to disk.")],
    ctx: Context,
    findings: Annotated[Optional[Dict[str, Any]], Field(description="Pre-mapped field key/value dict (legacy path). Exact template keys required.")] = None,
    inference_results: Annotated[Optional[List[Dict]], Field(description="Raw inference results list, each with 'description', 'model', 'structures' keys (structures have 'name', 'volume_cm3', 'voxel_count').")] = None,
    patient_context: Annotated[Optional[Dict], Field(description="Optional patient demographics / clinical context dict")] = None,
    specialty: Annotated[str, Field(description="Reporting specialty for the sampling prompt. One of: general, oncology, cardiology, emergency, neuroradiology, musculoskeletal.")] = "general",
) -> Dict[str, Any]:
    """Fill a RadReport template using MCP sampling. Provide inference_results for LLM-driven narrative generation, or findings for legacy rigid mapping. At least one must be supplied."""
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

    mapped_findings: Dict[str, Any] = {}
    sampling_narrative: Optional[Dict] = None

    if inference_results is not None:
        system_prompt = SPECIALTY_SYSTEM_PROMPTS.get(specialty, SPECIALTY_SYSTEM_PROMPTS["general"])
        field_descriptions = []
        for key, f in schema["all_fields"].items():
            ctrl = f.get("control_type", "text")
            desc = (
                f"{key} (type={ctrl}, "
                f"section={f.get('section', '')}, aliases={f.get('aliases', [])})"
            )
            if ctrl in {"select", "radio"} and f.get("options"):
                opts = ", ".join(
                    f'"{o["value"]}" ({o["label"]})'
                    for o in f["options"]
                    if o.get("value") is not None
                )
                desc += f" — allowed values: {opts}"
            field_descriptions.append(desc)
        user_message = (
            f"Template: {schema['title']}\n\n"
            f"Available template fields:\n"
            + "\n".join(f"  - {d}" for d in field_descriptions)
            + f"\n\nPatient context: {json.dumps(patient_context) if patient_context else 'Not provided'}\n\n"
            f"Raw inference results:\n{json.dumps(inference_results, indent=2)}\n\n"
            "Map each relevant inference finding to the most appropriate template field key "
            "from the list above. Use exact key names.\n"
            "IMPORTANT: For select/radio fields, the value MUST be the exact quoted value string "
            "listed after 'allowed values' — do not use labels, grades, or free text.\n"
            "Respond with valid JSON only, with exactly these keys:\n"
            '{"field_mappings": {"<field_key>": "<value>", ...}, '
            '"findings_narrative": "<string>", "impression": "<string>", "recommendations": "<string>"}'
        )
        try:
            sample_result = await ctx.session.create_message(
                messages=[
                    mcp_types.SamplingMessage(
                        role="user",
                        content=mcp_types.TextContent(type="text", text=user_message),
                    )
                ],
                system_prompt=system_prompt,
                max_tokens=1024,
            )
            raw_text = ""
            if hasattr(sample_result.content, "text"):
                raw_text = sample_result.content.text
            elif isinstance(sample_result.content, list):
                for block in sample_result.content:
                    if hasattr(block, "text"):
                        raw_text += block.text

            match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            if match:
                parsed = json.loads(match.group())
                mapped_findings = parsed.get("field_mappings") or {}
                sampling_narrative = {
                    "findings_narrative": parsed.get("findings_narrative"),
                    "impression": parsed.get("impression"),
                    "recommendations": parsed.get("recommendations"),
                }
        except Exception as exc:
            return {"error": f"Sampling failed: {exc}", "error_type": "sampling_error"}

    elif findings is not None:
        mapped_findings = findings
    else:
        return {"error": "Either 'findings' or 'inference_results' must be provided.", "error_type": "missing_input"}

    validation_result = validate_findings(findings=mapped_findings, all_fields=schema["all_fields"])
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

    result: Dict[str, Any] = {
        "status": "Finalized",
        "template_id": template_id,
        "template_title": schema["title"],
        "html_report": fill_result["html_report"],
        "applied_fields": applied_fields,
        "preserved_defaults_count": max(total_fields - len(applied_fields), 0),
        "validation": validation_result["validation"],
        "specialty": specialty,
    }
    if sampling_narrative:
        result["narrative"] = sampling_narrative

    if output_path:
        try:
            import os as _os
            from datetime import datetime as _dt
            resolved = Path(output_path)
            # In local dev APP_ROOT differs from the Docker /app mount; remap if needed.
            app_root = _os.getenv("APP_ROOT", "")
            if app_root and str(resolved).startswith("/app/"):
                resolved = Path(app_root) / str(resolved)[len("/app/"):]
            base = resolved.with_suffix("")
            ts = _dt.now().strftime("%Y%m%d_%H%M%S")
            dest = Path(f"{base}_{ts}.html")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(fill_result["html_report"], encoding="utf-8")
            result["saved_to"] = str(dest.resolve())
        except Exception as exc:
            result["save_error"] = f"Failed to save report: {exc}"

    return result


if __name__ == "__main__":
    mcp.run()
