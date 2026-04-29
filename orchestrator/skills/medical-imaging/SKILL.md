---
name: medical-imaging
description: ALWAYS call this skill before doing anything when the user asks to work with medical images in any form — whether they mention a slide UID, a DICOM file, a CT or MRI scan, a pathology image, tumor detection, segmentation, or any image-based analysis. Do not attempt these tasks directly — read this skill first.
---

# Medical Imaging Skill

This is a workflow router. Before executing any tools, read the reference file for the appropriate workflow using `skills.read_references("medical-imaging", "<file>")`.

## Available Workflows

| Workflow | When to use | Reference |
| --- | --- | --- |
| DICOM Analysis + Report | User provides DICOM files or directories, wants inference, segmentation, or a radiology report | `references/dicom-analysis-workflow.md` |
| WSI Tumor Detection | User provides a slide UID and wants tumor detection in any whole-slide pathology image (any tissue type or organ) | `references/wsi-tumor-detection-workflow.md` |

If both workflows apply, ask the user which to run first.

New workflows can be added to this table as the skill grows.
