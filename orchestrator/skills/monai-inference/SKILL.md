---
name: monai-inference
description: Translates MONAI inference outputs into professional clinical findings using model-specific and modality-specific mapping tables (CT/MRI). Use this skill for threshold-based severity phrasing, tissue interpretation, and confidence-tier wording.
---

# MONAI Inference Skill

This skill converts MONAI model outputs into structured, report-ready clinical findings.

## How to Use
1. Load the model reference file from `references/models/` (e.g., `spleen_ct_segmentation.md`) using `skills.read_references`.
2. Load the modality file from `references/modalities/` (`CT.md` or `MRI.md`) using `skills.read_references`.
3. **Apply the mapping tables yourself in your reasoning** — there is NO tool for this step. You (the LLM) look up the inference results (volume_cm3, intensity, confidence) in the tables and produce the clinical wording directly. For example: volume 248.43 cm³ in the spleen table → "Mild splenomegaly".
4. Use the mapped findings when calling `complete_task` with the final report.

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
