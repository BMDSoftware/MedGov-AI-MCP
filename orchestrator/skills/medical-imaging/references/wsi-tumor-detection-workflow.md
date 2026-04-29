# Whole-Slide Image (WSI) Tumor Detection Workflow (iPath)

**Goal:** Given a slide UID, locate the most suspicious region visually and retrieve a high-resolution view of it for cell-level analysis.

The agent acts as the vision model — there is no AI detection tool. Visual inspection happens after thumbnail and ROI images are fetched. This workflow applies to any whole-slide pathology image regardless of tissue type or organ.

## Tools and Sequence

1. **Fetch the whole-slide thumbnail**
   - `ipath.fetch_thumbnail(slide_uid, output_path, width=844, height=588)`
   - The result includes `image_for_llm: true` — the agent can see this image directly
   - Save the returned `width` and `height` (actual values, needed in step 4)

2. **Visual inspection** *(no tool call)*
   - Examine the thumbnail and identify the **single most probable tumor location** — the region with the highest suspicion based on color, texture, and structural abnormality
   - You must commit to one bounding box before continuing. If multiple regions are suspicious, note them all but select only the most prominent for the ROI fetch
   - Estimate a bounding box in thumbnail pixel coordinates: `(thumb_x, thumb_y, thumb_w, thumb_h)`
   - **HARD LIMIT: `thumb_w` MUST NOT exceed 30 and `thumb_h` MUST NOT exceed 30. If your visual estimate is larger, clamp it to 30. Never pass a value above 30 for width or height in step 4.**
   - Describe the finding to the clinician before continuing

3. **Get full slide dimensions**
   - `ipath.get_slide_dimensions(slide_uid)`

4. **Scale the bounding box to full-slide coordinates**
   - `ipath.scale_roi_to_slide(thumb_x, thumb_y, thumb_w, thumb_h, thumb_img_w, thumb_img_h, slide_w, slide_h)`
   - Use the actual `width`/`height` returned in step 1 as `thumb_img_w`/`thumb_img_h`

5. **Fetch the high-resolution ROI**
   - `ipath.fetch_roi(slide_uid, x, y, width, height, output_path)`
   - The server clamps dimensions to 2700px max per side

6. **Count cells in the ROI**
   - Call `cellpose.segment_cells_2d(image_path=<roi_output_path>, model_type="cpsam")`
   - The result includes `output_path` (the mask file) and `cell_count` — the number of detected cells (`masks.max()`)
   - Report the cell count to the clinician as part of the findings

7. **Generate a pathology report**
   - Radlex (RadReport-Pro) is for radiology only — it is not appropriate here
   - Instead, load the pathology report structure from the clinical-reports skill: `skills.read_skill_file("clinical-reports")`
   - Use the Pathology Report section: Patient Info, Specimen Info, Clinical History, Gross Description, Microscopic Description, Diagnosis, Comments
   - Save with `utils.write_file(path=..., content=...)`

## Key Notes

- The slide UID (DICOM SOPInstanceUID) must come from the user. Ask for it if not provided.
- Describe findings in clinical language only — no file paths, coordinates, or tool names in user-facing output.
