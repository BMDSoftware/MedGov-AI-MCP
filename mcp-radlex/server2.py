#!/usr/bin/env python3
import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import re

from mcp.server.fastmcp import FastMCP
from bs4 import BeautifulSoup

# --- Configuration ---
TEMPLATES_DIR = os.getenv("RAD_TEMPLATES_DIR", "./templates")

mcp = FastMCP("RadLex", dependencies=["beautifulsoup4"])

class TemplateEngine:
    """Parses IHE MRRT Templates, nesting fields within their respective sections."""
    def __init__(self, directory: str):
        self.path = Path(directory)
        self.templates = {}
        self._load_templates()

    def _load_templates(self):
        if not self.path.exists():
            os.makedirs(self.path, exist_ok=True)
            return
        
        for html_file in self.path.glob("*.html"):
            try:
                with open(html_file, 'r', encoding='utf-8') as f:
                    soup = BeautifulSoup(f.read(), 'html.parser')
                    
                t_id = html_file.stem
                title_tag = soup.find('title')
                title = title_tag.text.strip() if title_tag else t_id
                
                structured_sections = []
                all_fields = {}

                # 1. Find all sections
                sections = soup.find_all(['section', 'div'], attrs={"data-section-name": True})
                if not sections:
                    sections = soup.find_all('section')

                for section in sections:
                    s_title_tag = section.find(['h1', 'h2', 'h3', 'header', 'b'])
                    s_title = s_title_tag.text.strip() if s_title_tag else section.get('data-section-name', "General")
                    
                    if any(x in s_title.upper() for x in ["INSTRUCTION", "SAMPLE", "____", "EXAMPLE"]):
                        continue

                    section_data = {
                        "section_title": s_title,
                        "fields": []
                    }

                    # 2. Find fields inside this section
                    for inp in section.find_all(['input', 'select', 'textarea']):
                        f_id = inp.get('id') or inp.get('name')
                        if not f_id: continue
                        
                        label_tag = soup.find('label', attrs={"for": f_id})
                        label_text = label_tag.text.strip() if label_tag else ""
                        
                        if not label_text:
                            label_text = f_id.replace("TEXT_", "Field ").replace("_", " ").title()

                        field_info = {
                            "html_id": f_id,
                            "label": label_text,
                            "type": inp.get('type') or inp.name,
                            "default": inp.get('value') or (inp.text if inp.name == 'textarea' else "")
                        }
                        
                        section_data["fields"].append(field_info)
                        all_fields[f_id] = field_info

                    if section_data["fields"]:
                        structured_sections.append(section_data)

                self.templates[t_id] = {
                    "id": t_id,
                    "title": title,
                    "file_path": str(html_file),
                    "structured_sections": structured_sections,
                    "fields": all_fields
                }
            except Exception as e:
                print(f"Error loading {html_file}: {e}")

engine = TemplateEngine(TEMPLATES_DIR)

@mcp.tool()
def list_available_templates() -> List[Dict[str, str]]:
    """List all parsed HTML templates."""
    return [{"id": k, "title": v["title"]} for k, v in engine.templates.items()]

@mcp.tool()
def get_template_schema(template_id: str) -> Dict[str, Any]:
    """
    Returns the template schema with fields nested inside their sections.
    Use the 'html_id' as the key in the findings dictionary for generate_report.
    """
    template = engine.templates.get(template_id)
    if not template:
        template = next((v for k, v in engine.templates.items() if k.lower() == template_id.lower()), None)
    
    if not template:
        return {"error": f"Template '{template_id}' not found"}
    
    return {
        "template_id": template["id"],
        "template_title": template["title"],
        "schema": template["structured_sections"]
    }

@mcp.tool()
def generate_report(template_id: str, findings: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generates a brand-new, professional radiology report based on the template schema.
    This tool ignores the original HTML boilerplate and builds a clean document.
    """
    try:
        template = engine.templates.get(template_id)
        if not template:
            template = next((v for k, v in engine.templates.items() if k.lower() == template_id.lower()), None)
        
        if not template:
            return {"error": "Template not found"}

        # 1. Start Building the New HTML Document
        html_output = []
        html_output.append("<!DOCTYPE html><html><head>")
        html_output.append(f"<title>Radiology Report - {template['title']}</title>")
        
        # 2. Add Professional Medical Styling
        html_output.append("""
            <style>
                body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #222; max-width: 800px; margin: 40px auto; padding: 20px; background-color: #f4f7f6; }
                .report-container { background-color: #fff; padding: 40px; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); border: 1px solid #e0e0e0; }
                .header { text-align: center; border-bottom: 3px solid #2c3e50; margin-bottom: 30px; padding-bottom: 10px; }
                .header h1 { margin: 0; color: #2c3e50; text-transform: uppercase; font-size: 24px; }
                .header p { margin: 5px 0; color: #7f8c8d; font-size: 14px; }
                section { margin-bottom: 25px; }
                h2 { background-color: #ecf0f1; color: #2c3e50; font-size: 18px; padding: 8px 15px; border-left: 5px solid #2c3e50; text-transform: uppercase; margin-bottom: 15px; }
                .field { margin-bottom: 12px; padding-left: 15px; }
                .label { font-weight: bold; color: #34495e; display: block; font-size: 14px; }
                .value { color: #000; font-size: 15px; white-space: pre-wrap; display: block; margin-top: 4px; }
                .footer { margin-top: 50px; padding-top: 20px; border-top: 1px solid #eee; font-size: 12px; color: #95a5a6; text-align: center; }
                .timestamp { font-style: italic; }
            </style>
        """)
        html_output.append("</head><body><div class='report-container'>")
        
        # 3. Add Report Header
        html_output.append(f"<div class='header'><h1>{template['title']}</h1>")
        html_output.append(f"<p>Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p></div>")

        # 4. Iterate through the Structured Schema to build sections
        # We use the schema as the master list of what should be in the report
        for section in template.get('structured_sections', []):
            section_html = []
            section_has_data = False
            
            section_html.append(f"<section><h2>{section['section_title']}</h2>")
            
            for field in section.get('fields', []):
                f_id = field['html_id']
                f_label = field['label']
                f_type = field['type']
                
                # Get value from findings, fallback to default
                val = findings.get(f_id)
                
                # Logic for handling different field types
                if f_type == "radio":
                    # For radios, we only show the field if it was explicitly selected
                    # or if the value matches the radio's default label
                    if val == f_id or (isinstance(val, str) and val.lower() in field['default'].lower()):
                        section_html.append(f"<div class='field'><span class='label'>{section['section_title']} Type:</span>")
                        section_html.append(f"<span class='value'>● {field['default']}</span></div>")
                        section_has_data = True
                else:
                    # For text/textarea, show if provided or if there's a non-empty default
                    display_val = val if val is not None else field.get('default', "")
                    if display_val and str(display_val).strip():
                        # Clean up labels that are just IDs
                        clean_label = f_label if "Field " not in f_label else ""
                        if clean_label:
                            section_html.append(f"<div class='field'><span class='label'>{clean_label}:</span>")
                        else:
                            section_html.append("<div class='field'>")
                        
                        section_html.append(f"<span class='value'>{display_val}</span></div>")
                        section_has_data = True
            
            section_html.append("</section>")
            
            # Only add the section to the final report if it actually contains data
            if section_has_data:
                html_output.extend(section_html)

        # 5. Catch-all for any findings sent by LLM that weren't in the schema
        unmapped_data = []
        schema_ids = [f['html_id'] for s in template.get('structured_sections', []) for f in s['fields']]
        for k, v in findings.items():
            if k not in schema_ids and v:
                unmapped_data.append((k, v))
        
        if unmapped_data:
            html_output.append("<section><h2>Additional Information</h2>")
            for k, v in unmapped_data:
                html_output.append(f"<div class='field'><span class='label'>{k}:</span><span class='value'>{v}</span></div>")
            html_output.append("</section>")

        # 6. Close Tags
        html_output.append("<div class='footer'><p class='timestamp'>Electronically signed via AgenticHealth MCP</p></div>")
        html_output.append("</div></body></html>")

        # 7. Save the new file
        final_html = "".join(html_output)
        filename = f"final_report_{datetime.now().strftime('%H%M%S')}.html"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(final_html)

        return {
            "status": "success",
            "filename": filename,
            "report_html": final_html,
            "report_text": _generate_text_version(template, findings),
            "template_used": template_id,
            "message": "Report generated successfully"
        }

    except Exception as e:
        return {"error": str(e)}
    
def _generate_text_version(template, findings):
    """Generate plain text version of the report"""
    lines = [
        f"RADIOLOGY REPORT - {template['title'].upper()}",
        "=" * 60,
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        ""
    ]
    
    for section in template.get('structured_sections', []):
        section_lines = []
        for field in section.get('fields', []):
            field_value = findings.get(field['html_id'], '').strip()
            if field_value:
                section_lines.append(f"{field['label']}: {field_value}")
        
        if section_lines:
            lines.append(f"{section['section_title'].upper()}:")
            lines.extend(section_lines)
            lines.append("")
    
    return "\n".join(lines)

if __name__ == "__main__":
    mcp.run()