---
name: monai-inference
description: Translates MONAI inference outputs into professional clinical findings using model-specific and modality-specific mapping tables (CT/MRI). Use this skill for threshold-based severity phrasing, tissue interpretation, and confidence-tier wording.
---

# MONAI Inference Skill

This skill converts MONAI model outputs into structured, report-ready clinical findings.

## How to Use
- For a given MONAI model, load the corresponding file from `references/models/` (e.g., `spleen_ct_segmentation.md`).
- Load one modality file from `references/modalities/` when modality is known (`CT.md` or `MRI.md`).
- Use the tables to map:
  - `volume_cm3` to severity (Normal/Mild/Moderate/Severe)
  - `intensity_mean` (HU or MRI units) to tissue type
  - confidence score to clinical wording
- All mappings are table-based for clarity and automation.

## Available Model Mappings
- `references/models/spleen_ct_segmentation.md`
- `references/models/swin_unetr_btcv_segmentation.md`
- `references/models/pancreas_ct_dints_segmentation.md`
- `references/models/lung_nodule_ct_detection.md`
- `references/models/brats_mri_segmentation.md`
- `references/models/wholeBody_ct_segmentation.md`
- `references/models/renalStructures_UNEST_segmentation.md`

## Available Modality Mappings
- `references/modalities/CT.md`
- `references/modalities/MRI.md`

## Notes
- Only load the reference file(s) for the model(s) in use.
- For new models, add a new Markdown file in `references/models/` following the same format.
- For new modalities, add a Markdown file in `references/modalities/`.
