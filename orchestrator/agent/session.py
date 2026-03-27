from typing import Dict, Any
from datetime import datetime

import database as db

from .prompts import PATIENT_FOCUS_PROMPT_TEMPLATE


class SessionMixin:
    """Patient focus, session context persistence, and key-data extraction."""

    def set_patient_focus(self, patient_id: str, patient_name: str):
        """Set the agent to focus on a specific patient for healthcare conversations."""
        patient_prompt = PATIENT_FOCUS_PROMPT_TEMPLATE.format(
            patient_id=patient_id,
            patient_name=patient_name,
        )
        if self.llm_client:
            self.llm_client.update_system_prompt(patient_prompt)
        self.session_context.set_patient(patient_id, patient_name)

    def reset_session_context(self):
        """Clear all accumulated session context."""
        self.session_context.clear()
        print("Session context cleared.")

    def save_context_to_db(self, session_id: str):
        """Persist current session context entries to the database."""
        db.clear_session_context(session_id)
        for entry in self.session_context.entries:
            db.save_context_entry(
                session_id,
                entry["tool"],
                entry["summary"],
                entry.get("data", {}),
                entry.get("timestamp", datetime.now().isoformat()),
            )
        print(f"Saved {len(self.session_context.entries)} context entries to DB.")

    def load_context_from_db(self, session_id: str):
        """Restore session context from the database."""
        entries = db.load_session_context(session_id)
        self.session_context.clear()
        self.session_context.entries = entries
        print(f"Loaded {len(entries)} context entries from DB.")

    def _record_and_persist(self, tool_name: str, result_summary: str, key_data: Dict, session_id: str = None):
        """Record to in-memory context AND persist to DB."""
        self.session_context.record(tool_name, result_summary, key_data)
        if session_id:
            timestamp = self.session_context.entries[-1].get("timestamp", datetime.now().isoformat())
            db.save_context_entry(session_id, tool_name, result_summary, key_data, timestamp)

    def _extract_key_data(self, tool_name: str, result: Any) -> Dict[str, Any]:
        """Extract the key facts from a tool result for session context."""
        if not isinstance(result, dict):
            return {}

        if tool_name == "utils.parse_dicom":
            tags = result.get("tags", {})
            return {
                "modality": tags.get("Modality"),
                "body_part": tags.get("BodyPartExamined"),
                "patient_name": tags.get("PatientName"),
                "patient_id": tags.get("PatientID"),
                "study_description": tags.get("StudyDescription"),
                "dimensions": result.get("dimensions"),
                "is_valid": result.get("is_valid"),
            }

        if tool_name == "utils.parse_dicom_directory":
            return {
                "total_files": result.get("total_files"),
                "num_series": result.get("num_series"),
                "modalities_found": result.get("modalities", []),
            }

        if tool_name == "monai.analyze_image":
            analysis = result.get("analysis", {})
            return {
                "detected_modalities": analysis.get("detected_modalities", []),
                "shape": result.get("shape"),
                "path": result.get("path") or result.get("file_path"),
            }

        if tool_name == "monai.list_models":
            models = result.get("models", [])
            return {
                "total_models": result.get("total", 0),
                "models": [
                    {"name": m.get("name"), "modality": m.get("modality"),
                     "body_part": m.get("body_part"), "downloaded": m.get("downloaded")}
                    for m in models
                ],
            }

        if tool_name == "monai.download_model":
            return {
                "model_name": result.get("model_name"),
                "status": result.get("status"),
            }

        if tool_name == "monai.run_inference":
            results_data = result.get("results", {})
            return {
                "status": result.get("status"),
                "model_used": result.get("model_name"),
                "detected_structures": results_data.get("detected_structures", []),
                "output_path": results_data.get("output_path"),
            }

        if tool_name.startswith("fhir."):
            resource_type = result.get("resourceType")
            if resource_type == "Bundle":
                entries = result.get("entry", [])
                return {
                    "resource_type": "Bundle",
                    "entry_count": len(entries),
                    "entry_types": list(set(
                        e.get("resource", {}).get("resourceType", "?") for e in entries
                    )),
                }
            elif resource_type:
                return {"resource_type": resource_type, "id": result.get("id")}

        if tool_name.startswith("radlex."):
            return {
                "operation": tool_name.split(".")[-1],
                "status": result.get("status", "completed"),
            }

        return {}
