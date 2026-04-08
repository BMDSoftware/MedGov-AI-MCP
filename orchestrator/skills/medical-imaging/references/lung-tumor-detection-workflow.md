# Lung Tumor Detection Workflow (iPath / Whole-Slide Image)

**Goal:** Given a slide UID, locate the tumor region visually and retrieve a high-resolution view of it.

The agent acts as the vision model — there is no AI detection tool. Visual inspection happens after thumbnail and ROI images are fetched.

## Tools and Sequence

1. **Fetch the whole-slide thumbnail**
   - `ipath.fetch_thumbnail(slide_uid, output_path, width=844, height=588)`
   - The result includes `image_for_llm: true` — the agent can see this image directly
   - Save the returned `width` and `height` (actual values, needed in step 4)

2. **Visual inspection** *(no tool call)*
   - Examine the thumbnail and identify the most suspicious region
   - Estimate a bounding box in thumbnail pixel coordinates: `(thumb_x, thumb_y, thumb_w, thumb_h)`
   - Describe the finding to the clinician before continuing

3. **Get full slide dimensions**
   - `ipath.get_slide_dimensions(slide_uid)`

4. **Scale the bounding box to full-slide coordinates**
   - `ipath.scale_roi_to_slide(thumb_x, thumb_y, thumb_w, thumb_h, thumb_img_w, thumb_img_h, slide_w, slide_h)`
   - Use the actual `width`/`height` returned in step 1 as `thumb_img_w`/`thumb_img_h`

5. **Fetch the high-resolution ROI**
   - `ipath.fetch_roi(slide_uid, x, y, width, height, output_path)`
   - The server clamps dimensions to 2700px max per side
   - Result includes `image_for_llm: true` — examine this image for the detailed findings

6. **Generate a pathology report**
   - Radlex (RadReport-Pro) is for radiology only — it is not appropriate here
   - Instead, load the pathology report structure from the clinical-reports skill: `skills.read_skill_file("clinical-reports")`
   - Use the Pathology Report section: Patient Info, Specimen Info, Clinical History, Gross Description, Microscopic Description, Diagnosis, Comments
   - Save with `utils.write_file(path=..., content=...)`

## Key Notes

- The slide UID (DICOM SOPInstanceUID) must come from the user. Ask for it if not provided.
- Describe findings in clinical language only — no file paths, coordinates, or tool names in user-facing output.
- If multiple suspicious regions are visible in the thumbnail, note them all but retrieve the ROI for the most prominent one first.
