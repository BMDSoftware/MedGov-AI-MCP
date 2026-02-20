from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple
import re

from bs4 import BeautifulSoup, Tag


CONTROL_TAGS = ["input", "select", "textarea"]
IGNORE_SECTION_TOKENS = ("INSTRUCTION", "REVISION", "AUTHORS")


def _error(error_type: str, message: str, details: Any) -> Dict[str, Any]:
    return {"error": message, "error_type": error_type, "details": details}


def _clean(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _section_title(section: Optional[Tag]) -> str:
    if section is None:
        return "General"

    title_tag = section.find(["h1", "h2", "h3", "header", "b"])
    if title_tag:
        text = _normalize_whitespace(title_tag.get_text(" ", strip=True))
        if text:
            return text

    data_name = _clean(section.get("data-section-name"))
    return data_name or "General"


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip().lower())
    return slug.strip("_") or "section"


def _resolve_unique_key(base: str, section_title: str, used: set[str]) -> str:
    if base not in used:
        return base

    section_key = f"{_slug(section_title)}.{base}"
    if section_key not in used:
        return section_key

    counter = 2
    while True:
        candidate = f"{section_key}_{counter}"
        if candidate not in used:
            return candidate
        counter += 1


def _first_non_empty_label_from_parent(control: Tag) -> Optional[str]:
    parent = control.parent
    if not isinstance(parent, Tag):
        return None

    labels = parent.find_all("label")
    for label in labels:
        text = _normalize_whitespace(label.get_text(" ", strip=True))
        if text:
            return text
    return None


def _resolve_control_label(
    soup: BeautifulSoup,
    control: Tag,
    html_id: Optional[str],
    name: Optional[str],
    fallback: str,
) -> str:
    if html_id:
        by_id = soup.find("label", attrs={"for": html_id})
        if by_id:
            text = _normalize_whitespace(by_id.get_text(" ", strip=True))
            if text:
                return text

    if name:
        by_name = soup.find("label", attrs={"for": name})
        if by_name:
            text = _normalize_whitespace(by_name.get_text(" ", strip=True))
            if text:
                return text

    parent_label = _first_non_empty_label_from_parent(control)
    if parent_label:
        return parent_label

    return fallback


def _control_type(control: Tag) -> str:
    if control.name == "input":
        return (_clean(control.get("type")) or "text").lower()
    return control.name


def _unique_aliases(values: List[Optional[str]]) -> List[str]:
    seen = set()
    aliases: List[str] = []
    for value in values:
        if not value or value in seen:
            continue
        aliases.append(value)
        seen.add(value)
    return aliases


def _select_options(control: Tag) -> List[Dict[str, str]]:
    options: List[Dict[str, str]] = []
    for option in control.find_all("option"):
        options.append(
            {
                "value": str(option.get("value", "")),
                "label": _normalize_whitespace(option.get_text(" ", strip=True)),
                "id": str(option.get("id", "") or ""),
            }
        )
    return options


def _radio_option_label(control: Tag) -> str:
    label_text = ""
    sibling = control.next_sibling
    while sibling is not None:
        if isinstance(sibling, Tag):
            if sibling.name == "br":
                break
            text = _normalize_whitespace(sibling.get_text(" ", strip=True))
            if text:
                label_text = text
                break
        else:
            text = _normalize_whitespace(str(sibling))
            if text:
                label_text = text
                break
        sibling = sibling.next_sibling

    if label_text:
        return label_text
    return _clean(control.get("value")) or _clean(control.get("id")) or "option"


def _build_alias_index(all_fields: Dict[str, Dict[str, Any]]) -> Dict[str, List[str]]:
    alias_index: Dict[str, List[str]] = defaultdict(list)
    for key, field in all_fields.items():
        for alias in [key, *field.get("aliases", [])]:
            if key not in alias_index[alias]:
                alias_index[alias].append(key)
    return dict(alias_index)


def build_template_schema(template_html: str, template_id: str, template_title: str) -> Dict[str, Any]:
    if not _clean(template_html):
        return _error(
            "template_parse_error",
            "Template HTML is empty.",
            {"template_id": template_id},
        )

    soup = BeautifulSoup(template_html, "html.parser")
    controls = soup.find_all(CONTROL_TAGS)
    if not controls:
        return _error(
            "template_parse_error",
            "No report controls found in template HTML.",
            {"template_id": template_id},
        )

    structured_sections: List[Dict[str, Any]] = []
    section_index: Dict[int, int] = {}
    all_fields: Dict[str, Dict[str, Any]] = {}
    used_keys: set[str] = set()
    radio_groups: Dict[Tuple[int, str], Dict[str, Any]] = {}

    def ensure_section(section_tag: Optional[Tag]) -> Tuple[int, str]:
        section_key = id(section_tag) if section_tag is not None else -1
        if section_key in section_index:
            section = structured_sections[section_index[section_key]]
            return section_index[section_key], section["section_title"]

        title = _section_title(section_tag)
        section_index[section_key] = len(structured_sections)
        structured_sections.append({"section_title": title, "fields": []})
        return section_index[section_key], title

    for control in controls:
        nearest_section = control.find_parent("section")
        section_pos, section_title = ensure_section(nearest_section)

        if any(token in section_title.upper() for token in IGNORE_SECTION_TOKENS):
            continue

        control_html_id = _clean(control.get("id"))
        control_name = _clean(control.get("name"))
        ctype = _control_type(control)

        if ctype == "radio":
            radio_group_name = control_name or control_html_id
            if not radio_group_name:
                continue

            group_key = (section_pos, radio_group_name)
            radio_entry = radio_groups.get(group_key)
            if radio_entry is None:
                canonical_key = _resolve_unique_key(radio_group_name, section_title, used_keys)
                used_keys.add(canonical_key)
                group_label = _resolve_control_label(
                    soup=soup,
                    control=control,
                    html_id=control_html_id,
                    name=radio_group_name,
                    fallback=canonical_key,
                )
                radio_entry = {
                    "key": canonical_key,
                    "html_id": control_html_id,
                    "name": radio_group_name,
                    "aliases": [],
                    "label": group_label,
                    "section_context": section_title,
                    "control_type": "radio",
                    "html_tag": "input",
                    "options": [],
                }
                radio_groups[group_key] = radio_entry
                structured_sections[section_pos]["fields"].append(radio_entry)
                all_fields[canonical_key] = radio_entry

            radio_entry["aliases"] = _unique_aliases(
                [*radio_entry["aliases"], control_html_id, radio_group_name]
            )
            radio_entry["options"].append(
                {
                    "value": str(control.get("value", "")),
                    "label": _radio_option_label(control),
                    "id": str(control.get("id", "") or ""),
                }
            )
            continue

        base_key = control_html_id or control_name
        if not base_key:
            continue

        canonical_key = _resolve_unique_key(base_key, section_title, used_keys)
        used_keys.add(canonical_key)

        label = _resolve_control_label(
            soup=soup,
            control=control,
            html_id=control_html_id,
            name=control_name,
            fallback=canonical_key,
        )

        field_info = {
            "key": canonical_key,
            "html_id": control_html_id,
            "name": control_name,
            "aliases": _unique_aliases([control_html_id, control_name]),
            "label": label,
            "section_context": section_title,
            "control_type": ctype,
            "html_tag": control.name,
            "options": _select_options(control) if ctype == "select" else [],
        }
        structured_sections[section_pos]["fields"].append(field_info)
        all_fields[canonical_key] = field_info

    # Drop sections with no fields
    structured_sections = [section for section in structured_sections if section["fields"]]
    if not all_fields:
        return _error(
            "template_parse_error",
            "Template has no writable controls after parsing.",
            {"template_id": template_id},
        )

    alias_index = _build_alias_index(all_fields)
    return {
        "id": template_id,
        "title": template_title,
        "source": "radreport_api",
        "structured_sections": structured_sections,
        "all_fields": all_fields,
        "allowed_findings_keys": sorted(alias_index.keys()),
    }


def _match_choice(raw_value: Any, options: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
    candidate = "" if raw_value is None else str(raw_value).strip()

    for key in ("value", "label", "id"):
        for option in options:
            value = str(option.get(key, "")).strip()
            if value == candidate:
                return option
    return None


def validate_findings(findings: Dict[str, Any], all_fields: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(findings, dict):
        return _error(
            "unknown_fields",
            "Findings must be a JSON object.",
            {"provided_type": type(findings).__name__},
        )

    alias_index = _build_alias_index(all_fields)
    unknown_keys: List[str] = []
    ambiguous_keys: Dict[str, List[str]] = {}
    conflicting_values: List[Dict[str, Any]] = []
    field_values: Dict[str, Any] = {}

    for raw_key, raw_value in findings.items():
        key = str(raw_key)
        matches = alias_index.get(key, [])

        if not matches:
            unknown_keys.append(key)
            continue
        if len(matches) > 1:
            ambiguous_keys[key] = matches
            continue

        field_key = matches[0]
        if field_key in field_values and field_values[field_key] != raw_value:
            conflicting_values.append(
                {
                    "input_key": key,
                    "field_key": field_key,
                    "existing_value": field_values[field_key],
                    "new_value": raw_value,
                }
            )
            continue
        field_values[field_key] = raw_value

    if unknown_keys or ambiguous_keys or conflicting_values:
        return _error(
            "unknown_fields",
            "Unknown or ambiguous findings keys provided.",
            {
                "unknown_keys": sorted(set(unknown_keys)),
                "ambiguous_keys": ambiguous_keys,
                "conflicting_values": conflicting_values,
                "allowed_keys": sorted(alias_index.keys()),
            },
        )

    normalized: Dict[str, Dict[str, Any]] = {}
    invalid_choices: List[Dict[str, Any]] = []

    for field_key, raw_value in field_values.items():
        field = all_fields[field_key]
        control_type = field.get("control_type")

        if control_type in {"select", "radio"}:
            choice = _match_choice(raw_value, field.get("options", []))
            if choice is None:
                invalid_choices.append(
                    {
                        "field_key": field_key,
                        "provided_value": raw_value,
                        "allowed_options": field.get("options", []),
                    }
                )
                continue
            normalized[field_key] = {
                "kind": "choice",
                "value": choice.get("value", ""),
                "label": choice.get("label", ""),
                "id": choice.get("id", ""),
            }
            continue

        normalized[field_key] = {
            "kind": "text",
            "value": "" if raw_value is None else str(raw_value),
        }

    if invalid_choices:
        return _error(
            "invalid_choice",
            "Invalid select/radio value provided.",
            {"invalid_choices": invalid_choices},
        )

    applied_fields = sorted(normalized.keys())
    return {
        "normalized": normalized,
        "applied_fields": applied_fields,
        "validation": {
            "total_fields": len(all_fields),
            "provided_keys": len(findings),
            "applied_count": len(applied_fields),
            "unknown_keys": [],
            "invalid_choices": [],
        },
    }


def _find_control(soup: BeautifulSoup, field: Dict[str, Any]) -> Optional[Tag]:
    html_tag = field.get("html_tag")
    html_id = field.get("html_id")
    name = field.get("name")

    if html_id:
        found = soup.find(html_tag, attrs={"id": html_id})
        if found:
            return found
    if name:
        found = soup.find(html_tag, attrs={"name": name})
        if found:
            return found
    return None


def _find_radio_controls(soup: BeautifulSoup, field: Dict[str, Any]) -> List[Tag]:
    controls: List[Tag] = []
    name = field.get("name")
    if name:
        controls = soup.find_all(
            "input",
            attrs={"name": name, "type": lambda value: str(value or "").lower() == "radio"},
        )
        if controls:
            return controls

    for option in field.get("options", []):
        option_id = option.get("id")
        if not option_id:
            continue
        control = soup.find("input", attrs={"id": option_id})
        if control:
            controls.append(control)
    return controls


def fill_template_html(
    template_html: str,
    all_fields: Dict[str, Dict[str, Any]],
    normalized_findings: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    soup = BeautifulSoup(template_html, "html.parser")
    missing_controls: List[str] = []

    for field_key, normalized_value in normalized_findings.items():
        field = all_fields[field_key]
        control_type = field.get("control_type")

        if control_type == "radio":
            radios = _find_radio_controls(soup, field)
            if not radios:
                missing_controls.append(field_key)
                continue

            desired = normalized_value
            target_id = str(desired.get("id", ""))
            target_value = str(desired.get("value", ""))
            target_label = str(desired.get("label", ""))

            selected_any = False
            for radio in radios:
                radio.attrs.pop("checked", None)
                radio_id = str(radio.get("id", "") or "")
                radio_value = str(radio.get("value", "") or "")
                option_label = _radio_option_label(radio)
                if (
                    (target_id and radio_id == target_id)
                    or (radio_value == target_value)
                    or (target_label and option_label == target_label)
                ):
                    radio["checked"] = ""
                    selected_any = True

            if not selected_any:
                missing_controls.append(field_key)
            continue

        if control_type == "select":
            select = _find_control(soup, field)
            if select is None:
                missing_controls.append(field_key)
                continue

            desired = normalized_value
            target_id = str(desired.get("id", ""))
            target_value = str(desired.get("value", ""))
            target_label = str(desired.get("label", ""))
            selected_any = False

            for option in select.find_all("option"):
                option.attrs.pop("selected", None)
                option_id = str(option.get("id", "") or "")
                option_value = str(option.get("value", "") or "")
                option_label = _normalize_whitespace(option.get_text(" ", strip=True))
                if (
                    (target_id and option_id == target_id)
                    or (option_value == target_value)
                    or (target_label and option_label == target_label)
                ):
                    option["selected"] = ""
                    selected_any = True

            if not selected_any:
                missing_controls.append(field_key)
            continue

        control = _find_control(soup, field)
        if control is None:
            missing_controls.append(field_key)
            continue

        text_value = str(normalized_value.get("value", ""))
        if control_type == "textarea":
            control.clear()
            control.append(text_value)
            continue

        if control_type == "checkbox":
            if text_value.lower() in {"true", "1", "yes", "on"}:
                control["checked"] = ""
            else:
                control.attrs.pop("checked", None)
            continue

        # Covers text/number/hidden/date/... input-like controls.
        control["value"] = text_value

    if missing_controls:
        return _error(
            "template_parse_error",
            "Template controls could not be updated reliably.",
            {"missing_controls": sorted(set(missing_controls))},
        )

    return {"html_report": str(soup)}
