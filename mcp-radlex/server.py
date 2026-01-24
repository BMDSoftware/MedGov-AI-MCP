#!/usr/bin/env python3
"""
MCP Server for RadLex/RadReport - Radiology report templates and terminology
Exposes radiology reporting functionality via MCP protocol for LLM tool use.
"""
import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("RadLex")

# --- Report Templates (based on RadReport.org structure) ---

REPORT_TEMPLATES = {
    "ct_abdomen_general": {
        "name": "CT Abdomen and Pelvis",
        "modality": "CT",
        "body_part": "abdomen",
        "sections": {
            "clinical_history": "Clinical History: {clinical_history}",
            "comparison": "Comparison: {comparison}",
            "technique": "Technique: CT of the abdomen and pelvis was performed {contrast}.",
            "findings": {
                "liver": "LIVER: {liver_findings}",
                "gallbladder": "GALLBLADDER AND BILIARY: {gallbladder_findings}",
                "spleen": "SPLEEN: {spleen_findings}",
                "pancreas": "PANCREAS: {pancreas_findings}",
                "adrenals": "ADRENAL GLANDS: {adrenal_findings}",
                "kidneys": "KIDNEYS AND URETERS: {kidney_findings}",
                "bladder": "BLADDER: {bladder_findings}",
                "bowel": "BOWEL: {bowel_findings}",
                "lymph_nodes": "LYMPH NODES: {lymph_node_findings}",
                "vasculature": "VASCULATURE: {vascular_findings}",
                "bones": "OSSEOUS STRUCTURES: {bone_findings}",
                "other": "OTHER: {other_findings}"
            },
            "impression": "IMPRESSION:\n{impression}"
        },
        "default_values": {
            "clinical_history": "Not provided",
            "comparison": "None available",
            "contrast": "with intravenous contrast",
            "liver_findings": "Normal in size and attenuation. No focal lesions.",
            "gallbladder_findings": "Normal. No gallstones or wall thickening.",
            "spleen_findings": "Normal in size.",
            "pancreas_findings": "Normal in size and attenuation.",
            "adrenal_findings": "Normal bilaterally.",
            "kidney_findings": "Normal in size and enhancement bilaterally. No hydronephrosis or stones.",
            "bladder_findings": "Normal when distended.",
            "bowel_findings": "Normal caliber throughout. No obstruction.",
            "lymph_node_findings": "No pathologically enlarged lymph nodes.",
            "vascular_findings": "Aorta and major vessels are normal in caliber.",
            "bone_findings": "No aggressive osseous lesions.",
            "other_findings": "None.",
            "impression": "1. No acute abnormality."
        }
    },
    "mri_kidney_mass": {
        "name": "MRI Kidney - Renal Mass Protocol",
        "modality": "MRI",
        "body_part": "kidney",
        "sections": {
            "clinical_history": "Clinical History: {clinical_history}",
            "comparison": "Comparison: {comparison}",
            "technique": "Technique: MRI of the kidneys was performed using renal mass protocol {contrast}.",
            "findings": {
                "right_kidney": "RIGHT KIDNEY: {right_kidney_findings}",
                "left_kidney": "LEFT KIDNEY: {left_kidney_findings}",
                "mass_characteristics": "MASS CHARACTERISTICS (if applicable):\n  - Size: {mass_size}\n  - Location: {mass_location}\n  - T1 signal: {t1_signal}\n  - T2 signal: {t2_signal}\n  - Enhancement pattern: {enhancement_pattern}\n  - Bosniak classification: {bosniak_class}",
                "adrenals": "ADRENAL GLANDS: {adrenal_findings}",
                "other": "OTHER FINDINGS: {other_findings}"
            },
            "impression": "IMPRESSION:\n{impression}"
        },
        "default_values": {
            "clinical_history": "Renal mass evaluation",
            "comparison": "None available",
            "contrast": "with and without intravenous gadolinium contrast",
            "right_kidney_findings": "Normal in size and signal intensity. No masses or hydronephrosis.",
            "left_kidney_findings": "Normal in size and signal intensity. No masses or hydronephrosis.",
            "mass_size": "N/A",
            "mass_location": "N/A",
            "t1_signal": "N/A",
            "t2_signal": "N/A",
            "enhancement_pattern": "N/A",
            "bosniak_class": "N/A",
            "adrenal_findings": "Normal bilaterally.",
            "other_findings": "None.",
            "impression": "1. No renal masses identified."
        }
    },
    "ct_chest": {
        "name": "CT Chest",
        "modality": "CT",
        "body_part": "chest",
        "sections": {
            "clinical_history": "Clinical History: {clinical_history}",
            "comparison": "Comparison: {comparison}",
            "technique": "Technique: CT of the chest was performed {contrast}.",
            "findings": {
                "lungs": "LUNGS: {lung_findings}",
                "airways": "AIRWAYS: {airway_findings}",
                "pleura": "PLEURA: {pleural_findings}",
                "mediastinum": "MEDIASTINUM: {mediastinal_findings}",
                "heart": "HEART AND PERICARDIUM: {cardiac_findings}",
                "lymph_nodes": "LYMPH NODES: {lymph_node_findings}",
                "bones": "OSSEOUS STRUCTURES: {bone_findings}",
                "upper_abdomen": "UPPER ABDOMEN (visualized): {upper_abdomen_findings}"
            },
            "impression": "IMPRESSION:\n{impression}"
        },
        "default_values": {
            "clinical_history": "Not provided",
            "comparison": "None available",
            "contrast": "without intravenous contrast",
            "lung_findings": "Clear bilaterally. No nodules, masses, or consolidation.",
            "airway_findings": "Patent central airways.",
            "pleural_findings": "No pleural effusion or pneumothorax.",
            "mediastinal_findings": "Normal mediastinal contour.",
            "cardiac_findings": "Normal cardiac size. No pericardial effusion.",
            "lymph_node_findings": "No pathologically enlarged lymph nodes.",
            "bone_findings": "No aggressive osseous lesions.",
            "upper_abdomen_findings": "Visualized upper abdomen unremarkable.",
            "impression": "1. No acute cardiopulmonary abnormality."
        }
    },
    "xray_chest": {
        "name": "Chest X-Ray (PA and Lateral)",
        "modality": "X-ray",
        "body_part": "chest",
        "sections": {
            "clinical_history": "Clinical History: {clinical_history}",
            "comparison": "Comparison: {comparison}",
            "technique": "Technique: PA and lateral views of the chest.",
            "findings": {
                "lungs": "LUNGS: {lung_findings}",
                "heart": "HEART: {cardiac_findings}",
                "mediastinum": "MEDIASTINUM: {mediastinal_findings}",
                "bones": "BONES: {bone_findings}",
                "other": "OTHER: {other_findings}"
            },
            "impression": "IMPRESSION:\n{impression}"
        },
        "default_values": {
            "clinical_history": "Not provided",
            "comparison": "None available",
            "lung_findings": "Clear bilaterally. No focal consolidation, pleural effusion, or pneumothorax.",
            "cardiac_findings": "Normal cardiac silhouette.",
            "mediastinal_findings": "Normal mediastinal contour.",
            "bone_findings": "No acute osseous abnormality.",
            "other_findings": "None.",
            "impression": "1. No acute cardiopulmonary process."
        }
    }
}

# --- RadLex Terminology (subset for common terms) ---

RADLEX_TERMS = {
    # Anatomical structures
    "RID58": {"term": "liver", "definition": "Large glandular organ in the upper right abdomen"},
    "RID86": {"term": "spleen", "definition": "Lymphoid organ in the left upper quadrant"},
    "RID29662": {"term": "kidney", "definition": "Bean-shaped organs that filter blood"},
    "RID170": {"term": "pancreas", "definition": "Gland behind the stomach"},
    "RID187": {"term": "gallbladder", "definition": "Small organ that stores bile"},
    "RID1301": {"term": "lung", "definition": "Respiratory organ in the thorax"},

    # Findings
    "RID3874": {"term": "mass", "definition": "Abnormal growth or lump of tissue"},
    "RID3875": {"term": "nodule", "definition": "Small mass of tissue"},
    "RID4865": {"term": "cyst", "definition": "Fluid-filled sac"},
    "RID5196": {"term": "calcification", "definition": "Calcium deposit in tissue"},
    "RID34262": {"term": "enhancement", "definition": "Increased signal after contrast"},
    "RID28694": {"term": "effusion", "definition": "Abnormal fluid collection"},

    # Descriptors
    "RID5758": {"term": "normal", "definition": "Within expected limits"},
    "RID5759": {"term": "abnormal", "definition": "Outside expected limits"},
    "RID39050": {"term": "enlarged", "definition": "Increased in size"},
    "RID39225": {"term": "decreased", "definition": "Reduced in size or amount"},
    "RID5978": {"term": "benign", "definition": "Not cancerous"},
    "RID5979": {"term": "malignant", "definition": "Cancerous"},

    # Modalities
    "RID10312": {"term": "computed tomography", "definition": "CT imaging"},
    "RID10313": {"term": "magnetic resonance imaging", "definition": "MRI imaging"},
    "RID10345": {"term": "radiography", "definition": "X-ray imaging"},
    "RID10326": {"term": "ultrasonography", "definition": "Ultrasound imaging"}
}


# --- MCP Tools ---

@mcp.tool()
def list_templates(modality: Optional[str] = None, body_part: Optional[str] = None) -> Dict[str, Any]:
    """
    List available radiology report templates.

    :param modality: Filter by modality (CT, MRI, X-ray)
    :param body_part: Filter by body part (abdomen, chest, kidney, etc.)
    """
    templates = []
    for template_id, template in REPORT_TEMPLATES.items():
        if modality and template["modality"].lower() != modality.lower():
            continue
        if body_part and template["body_part"].lower() != body_part.lower():
            continue
        templates.append({
            "id": template_id,
            "name": template["name"],
            "modality": template["modality"],
            "body_part": template["body_part"],
            "sections": list(template["sections"].keys())
        })

    return {
        "total": len(templates),
        "filters": {"modality": modality, "body_part": body_part},
        "templates": templates
    }


@mcp.tool()
def get_template(template_id: str) -> Dict[str, Any]:
    """
    Get a specific report template with all sections and default values.

    :param template_id: Template ID from list_templates (e.g., 'ct_abdomen_general')
    """
    if template_id not in REPORT_TEMPLATES:
        return {
            "error": f"Template '{template_id}' not found",
            "available_templates": list(REPORT_TEMPLATES.keys())
        }

    template = REPORT_TEMPLATES[template_id]
    return {
        "id": template_id,
        "name": template["name"],
        "modality": template["modality"],
        "body_part": template["body_part"],
        "sections": template["sections"],
        "default_values": template["default_values"],
        "required_fields": list(template["default_values"].keys())
    }


@mcp.tool()
def generate_report(template_id: str, findings: Dict[str, str], patient_info: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """
    Generate a radiology report from a template using provided findings.

    This is the main tool for creating reports based on AI analysis results.
    Pass the findings from image analysis (e.g., from MONAI) to populate the report.

    :param template_id: Template ID to use (e.g., 'ct_abdomen_general')
    :param findings: Dictionary of findings to fill in the template. Keys should match template fields.
    :param patient_info: Optional patient information (name, mrn, dob, exam_date)
    """
    if template_id not in REPORT_TEMPLATES:
        return {
            "error": f"Template '{template_id}' not found",
            "available_templates": list(REPORT_TEMPLATES.keys())
        }

    template = REPORT_TEMPLATES[template_id]

    # Merge default values with provided findings
    values = template["default_values"].copy()
    values.update(findings)

    # Build the report
    report_lines = []

    # Header with patient info
    report_lines.append("=" * 60)
    report_lines.append(f"RADIOLOGY REPORT - {template['name'].upper()}")
    report_lines.append("=" * 60)

    if patient_info:
        report_lines.append(f"Patient: {patient_info.get('name', 'Unknown')}")
        report_lines.append(f"MRN: {patient_info.get('mrn', 'N/A')}")
        report_lines.append(f"DOB: {patient_info.get('dob', 'N/A')}")
        report_lines.append(f"Exam Date: {patient_info.get('exam_date', datetime.now().strftime('%Y-%m-%d'))}")
    else:
        report_lines.append(f"Exam Date: {datetime.now().strftime('%Y-%m-%d')}")

    report_lines.append("-" * 60)
    report_lines.append("")

    # Fill in sections
    for section_name, section_template in template["sections"].items():
        if isinstance(section_template, dict):
            # Nested sections (like findings)
            report_lines.append(f"{section_name.upper().replace('_', ' ')}:")
            for subsection_name, subsection_template in section_template.items():
                try:
                    filled = subsection_template.format(**values)
                    report_lines.append(f"  {filled}")
                except KeyError as e:
                    report_lines.append(f"  {subsection_name}: [Missing: {e}]")
            report_lines.append("")
        else:
            # Simple section
            try:
                filled = section_template.format(**values)
                report_lines.append(filled)
                report_lines.append("")
            except KeyError as e:
                report_lines.append(f"{section_name}: [Missing: {e}]")
                report_lines.append("")

    report_lines.append("-" * 60)
    report_lines.append(f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("Electronically signed")

    report_text = "\n".join(report_lines)

    return {
        "template_used": template_id,
        "report_text": report_text,
        "findings_used": findings,
        "missing_fields": [k for k in template["default_values"].keys() if k not in findings],
        "timestamp": datetime.now().isoformat()
    }


@mcp.tool()
def search_radlex(query: str) -> Dict[str, Any]:
    """
    Search RadLex terminology for radiology terms and their definitions.

    :param query: Search term (e.g., 'liver', 'mass', 'nodule')
    """
    results = []
    query_lower = query.lower()

    for radlex_id, term_info in RADLEX_TERMS.items():
        if (query_lower in term_info["term"].lower() or
            query_lower in term_info["definition"].lower()):
            results.append({
                "radlex_id": radlex_id,
                "term": term_info["term"],
                "definition": term_info["definition"]
            })

    return {
        "query": query,
        "total_results": len(results),
        "results": results
    }


@mcp.tool()
def get_impression_suggestions(findings: Dict[str, str], modality: str) -> Dict[str, Any]:
    """
    Get AI-suggested impression text based on findings.

    This helps generate the IMPRESSION section of a radiology report
    based on the detailed findings.

    :param findings: Dictionary of findings from the report
    :param modality: Imaging modality (CT, MRI, X-ray)
    """
    impressions = []
    priority = 1

    # Analyze findings for notable items
    findings_text = " ".join(str(v).lower() for v in findings.values())

    # Check for critical findings
    critical_terms = ["mass", "tumor", "malignant", "suspicious", "urgent"]
    for term in critical_terms:
        if term in findings_text:
            impressions.append({
                "priority": priority,
                "text": f"CRITICAL: Finding requiring immediate attention - {term} identified",
                "category": "critical"
            })
            priority += 1

    # Check for notable findings
    notable_terms = ["nodule", "cyst", "enlarged", "effusion", "consolidation"]
    for term in notable_terms:
        if term in findings_text:
            impressions.append({
                "priority": priority,
                "text": f"Notable finding: {term.capitalize()} identified - clinical correlation recommended",
                "category": "notable"
            })
            priority += 1

    # Default normal finding if nothing notable
    if not impressions:
        impressions.append({
            "priority": 1,
            "text": f"No acute abnormality on {modality} examination.",
            "category": "normal"
        })

    return {
        "modality": modality,
        "suggested_impressions": impressions,
        "recommendation": "Review and modify as clinically appropriate"
    }


@mcp.tool()
def convert_findings_to_report_format(ai_analysis: Dict[str, Any], template_id: str) -> Dict[str, Any]:
    """
    Convert AI analysis results (e.g., from MONAI) to report template format.

    This is a helper tool to transform structured AI output into the format
    expected by generate_report().

    :param ai_analysis: Analysis results from AI model (e.g., MONAI segmentation results)
    :param template_id: Target template ID to format findings for
    """
    if template_id not in REPORT_TEMPLATES:
        return {
            "error": f"Template '{template_id}' not found",
            "available_templates": list(REPORT_TEMPLATES.keys())
        }

    template = REPORT_TEMPLATES[template_id]
    findings = {}

    # Extract relevant information from AI analysis
    if "labels" in ai_analysis:
        # Handle MONAI segmentation results
        labels = ai_analysis.get("labels", {})

        for label_id, label_name in labels.items():
            label_lower = label_name.lower()

            # Map AI labels to template fields
            if "liver" in label_lower:
                findings["liver_findings"] = f"Segmented by AI. Volume calculated."
            elif "spleen" in label_lower:
                findings["spleen_findings"] = f"Segmented by AI. Normal appearance."
            elif "kidney" in label_lower:
                if "right" in label_lower:
                    findings["right_kidney_findings"] = f"Segmented by AI."
                elif "left" in label_lower:
                    findings["left_kidney_findings"] = f"Segmented by AI."
                else:
                    findings["kidney_findings"] = f"Bilateral kidneys segmented by AI."
            elif "pancreas" in label_lower:
                findings["pancreas_findings"] = f"Segmented by AI. Normal appearance."
            elif "gallbladder" in label_lower:
                findings["gallbladder_findings"] = f"Identified by AI segmentation."

    # Add analysis metadata
    if "detected_modalities" in ai_analysis.get("analysis", {}):
        modality = ai_analysis["analysis"]["detected_modalities"][0]
        findings["technique_note"] = f"AI-detected modality: {modality}"

    if "shape" in ai_analysis:
        findings["image_dimensions"] = f"Image dimensions: {ai_analysis['shape']}"

    return {
        "template_id": template_id,
        "converted_findings": findings,
        "original_analysis": ai_analysis,
        "note": "Findings converted from AI analysis. Review and supplement with clinical observations."
    }


# --- Entry Point ---

if __name__ == "__main__":
    # Run with stdio transport for MCP protocol
    mcp.run(transport="stdio")
