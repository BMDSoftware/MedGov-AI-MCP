# DICOM Analysis + Report Generation Workflow

**Goal:** Parse the DICOM input → run MONAI inference → generate a structured radiology report.

## Tools and Sequence

1. **Parse metadata** — understand modality and body part
   - Single file: `utils.parse_dicom(file_path)`
   - Directory / series: `utils.parse_dicom_directory(dir_path)`

2. **Analyze the image** — confirm scan characteristics
   - `monai.analyze_image(image_path)`
   - Check `is_3d` in the result. If `false`, stop — MONAI models require a 3D volume, not a single 2D slice. Inform the clinician.

3. **Select and download the model**
   - `monai.list_models(modality=..., body_part=...)` — pick the model that best matches the detected modality and body part
   - `monai.download_model(model_name)` — checks local cache first, fast to call

4. **Run inference**
   - `monai.run_inference(image_path, model_name)`

5. **Find the report template**
   - `radlex.list_subspecialties()` — identify the right specialty code for the body part
   - `radlex.find_templates(query=..., specialty_code=...)` — find the most relevant template

6. **Generate the report**
   - `radlex.get_template_schema(template_id)` — inspect valid field keys before filling
   - `radlex.generate_report(template_id, findings={...}, report_title=...)` — map inference results to template fields
   - Unknown field keys cause hard errors — always check the schema first

7. **Save the report**
   - `utils.write_file(path=..., content=html_report)`

## Key Notes

- When generating the report, translate inference output (label volumes, detections) into clinical language for the findings fields.
- Communicate results following NORMAL_MODE_COMMUNICATION_RULES — no raw paths, no tool names, no model IDs in user-facing output.
