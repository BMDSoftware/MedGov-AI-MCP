# Skills

## What skills are

A skill is a plain-text workflow protocol loaded by the agent on demand. Skills guide the agent through clinical sequences where tool descriptions alone are not enough to produce correct behaviour — decision forks where a plausible choice exists but is wrong.

For example, without the `wsi-tumor-detection` skill the agent calls `radlex.generate_radiology_report` on a pathology image, which is clinically incorrect. With the skill active, the correct pathology report path is taken instead.

Skills are different from STM (short-term memory): STM manages what the agent remembers across iterations; skills prescribe what the agent should *do*.

---

## Directory structure

```
orchestrator/skills/
└── <skill-name>/
    ├── SKILL.md          # required — frontmatter + workflow instructions
    ├── references/       # optional — detailed reference files the agent can read on demand
    ├── scripts/          # optional — scripts the agent can execute via execute_script
    └── assets/           # optional — templates and static files
```

The agent loads skill metadata (name and description) from all `SKILL.md` files at startup. The full content is fetched on demand via `skills.read_skill_file(skill_name)` when the agent decides a skill is relevant.

---

## SKILL.md format

```markdown
---
name: my-skill
description: One sentence describing when to use this skill. This is what the agent reads to decide relevance.
---

# Skill Title

## Overview
...

## When to Use This Skill
...

## Tools and Sequence
1. Step one — `server.tool_name(args)`
2. Step two — ...

## Key Notes
- Constraints and edge cases the agent must follow
```

The frontmatter `description` is the most important field — it is what the agent reads to decide whether to load the full skill. Make it specific and trigger-oriented.

---

## Built-in skills

### `dicom-analysis`

**When to use:** any request to analyze, segment, or run inference on a CT scan, MRI, or DICOM file.

**Workflow:** parse DICOM metadata → analyze the image → discover available models (always call `list_models`, do not guess) → download the model → run inference → find the right RadLex template → generate a structured radiology report.

**Key constraint enforced:** if `analyze_image` returns `is_3d: false`, the agent stops and informs the user — MONAI models require a 3D volume.

---

### `wsi-tumor-detection`

**When to use:** the user wants to find tumors or suspicious regions in a tissue sample or organ image identified by a slide UID, and wants tumor detection, localization, cell counting, or a pathology report.

**Workflow:** fetch slide thumbnail → agent performs visual inspection and selects a bounding box → get full slide dimensions → scale bounding box to full-slide coordinates → fetch high-resolution ROI → run Cellpose cell segmentation → generate a pathology report using `clinical-reports`.

**Key constraints enforced:**
- `radlex.generate_radiology_report` is not used here — it is for radiology, not pathology
- Report is written via `clinical-reports`, not via the radlex server

---

### `clinical-reports`

**When to use:** writing any structured clinical document — case reports (CARE guidelines), diagnostic reports, clinical trial reports (ICH-E3, SAE, CSR), or patient documentation (SOAP, H&P, discharge summaries).

Provides templates, regulatory compliance guidance (HIPAA, FDA, ICH-GCP), and validation scripts. Also used by `wsi-tumor-detection` for the pathology report step.

---

### `pydicom`

**When to use:** reading, writing, or modifying DICOM files directly using the pydicom library — extracting pixel data, anonymizing files, modifying tags, converting formats, or handling compressed DICOM data.

---

## Adding a skill

1. Create a folder under `orchestrator/skills/<your-skill-name>/`
2. Add a `SKILL.md` with YAML frontmatter and markdown workflow instructions
3. Restart the backend — `SkillsMixin` scans the skills directory at startup

No code changes are required. The agent will include the new skill's description in its context and load the full content when it decides the skill is relevant.
