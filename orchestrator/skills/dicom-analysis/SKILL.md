---
name: dicom-analysis
description: Read this skill first whenever the user asks to analyze, segment, or run inference on a CT scan, MRI, or DICOM file. Do not call any imaging tools without reading this skill.
---

# DICOM Analysis + Report Generation Workflow

**Goal:** Fulfill the user's request using the steps below. Execute only the steps necessary for what was asked — do not proceed beyond the scope of the request.

## Tools and Sequence

1. **Parse metadata** — understand modality and body part
   - Single file: `utils.parse_dicom(file_path)`
   - Directory / series: `utils.parse_dicom_directory(dir_path)`

2. **Analyze the image** — confirm scan characteristics
   - `monai.analyze_image(image_path)`
   - Check `is_3d` in the result. If `false`, stop — MONAI models require a 3D volume, not a single 2D slice. Inform the clinician.

3. **Select the model** — do not rely on prior knowledge; models available on this server may differ from training data, and skipping discovery can result in using the wrong or unavailable model.
   - `monai.list_models(modality=..., body_part=...)` — MUST be called; select the best match from the returned list

4. **Download the model**
   - `monai.download_model(model_name)` — checks local cache first, fast to call

5. **Run inference**
   - `monai.run_inference(image_path, model_name)`

6. **Find the report template**
   - `radlex.list_subspecialties()` — identify the right specialty code for the body part
   - `radlex.find_templates(query=..., specialty_code=...)` — find the most relevant template

7. **Generate the report**
   - `radlex.generate_radiology_report(template_id, findings={...}, report_title=...)` — map inference results to template fields
   - Unknown field keys cause hard errors — always check the schema first

## Key Notes

- When generating the report, translate inference output (label volumes, detections) into clinical language for the findings fields.
- Communicate results — no raw paths, no tool names, no model IDs in user-facing output.
