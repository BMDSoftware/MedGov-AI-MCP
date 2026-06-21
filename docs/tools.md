# Tools Reference

## Overview

The agent interacts with specialized MCP (Model Context Protocol) servers over stdio or HTTP. Each server exposes a set of tools the agent can invoke. In addition to MCP tools, several built-in tools are always available directly to the agent.

Tool names are prefixed with the server name at runtime (e.g., `monai.run_inference`, `utils.write_file`).

---

## MCP Servers

### mcp-monai

Medical image analysis using MONAI pre-trained model bundles. Supports volumetric segmentation (CT, MRI) and detection tasks. GPU recommended; CPU fallback is automatic.

| Tool | Description |
|---|---|
| `get_monai_info()` | Returns MONAI and PyTorch version, CUDA availability, GPU details, and loaded models |
| `analyze_image(image_path)` | Detects image type, modality, and dimensions; recommends suitable models |
| `list_models(category?, modality?, body_part?)` | Lists available MONAI Model Zoo bundles with optional filters |
| `download_model(model_name)` | Downloads a model bundle from the MONAI Model Zoo |
| `run_inference(image_path, model_name)` | Runs inference on a medical image; returns segmentation or detection results |
| `list_transforms(category?)` | Lists available MONAI preprocessing transforms |

---

### mcp-radlex

Structured radiology report generation using RSNA RadReport templates. Uses MCP sampling to call the LLM for narrative generation.

| Tool | Description |
|---|---|
| `list_subspecialties()` | Returns valid radiology specialty codes (NR, CH, CA, etc.) |
| `find_templates(query?, specialty_code?)` | Searches RadReport templates by keyword or specialty |
| `generate_radiology_report(template_id, output_path, findings?, inference_results?, patient_context?, specialty?)` | Fills a RadReport template via LLM sampling; saves HTML report to disk |

`specialty` options: `general`, `oncology`, `cardiology`, `emergency`, `neuroradiology`, `musculoskeletal`.

---

### mcp-cellpose

Cell and nucleus segmentation for 2D/3D microscopy images using Cellpose v4 (cpsam/SAM models). GPU is auto-detected; falls back to CPU if unavailable.

| Tool | Description |
|---|---|
| `segment_cells_2d(image_path, model_type?, diameter?, ...)` | Segments cells in a 2D microscopy image |
| `segment_cells_3d(image_path, model_type?, ...)` | Segments cells in a 3D volumetric image |
| `segment_cells_batch(input_dir, output_dir, ...)` | Batch segmentation across multiple images |
| `denoise_image(image_path, ...)` | Denoises a microscopy image using Cellpose restoration models |
| `deblur_image(image_path, ...)` | Deblurs a microscopy image |
| `upsample_image(image_path, ...)` | Upsamples a low-resolution microscopy image |
| `restore_and_segment(image_path, ...)` | Restores and then segments in one pass |
| `train_segmentation_model(...)` | Fine-tunes a Cellpose model on custom data |
| `list_available_models()` | Lists all available Cellpose model types |
| `estimate_cell_diameter(image_path, ...)` | Estimates the typical cell diameter in an image |
| `save_masks(masks, output_path, ...)` | Saves segmentation masks to disk |
| `load_image_info(image_path)` | Returns image shape, dtype, and channel count |
| `save_overlay(image_path, masks_path, output_path, ...)` | Renders a visual overlay of masks on the source image |

Default `model_type` is `cpsam` (Cellpose SAM). Other options: `cyto`, `cyto2`, `cyto3`, `nuclei`.

---

### mcp-ipath

Whole-slide image (WSI) retrieval from the iPath telepathology platform (Dicoogle/DICOMweb).

| Tool | Description |
|---|---|
| `fetch_thumbnail(slide_uid, output_path, width?, height?)` | Downloads a scaled thumbnail of a whole-slide image |
| `get_slide_dimensions(slide_uid)` | Returns the full pixel dimensions of a whole-slide image |
| `scale_roi_to_slide(thumb_x, thumb_y, thumb_w, thumb_h, thumb_img_w, thumb_img_h, slide_w, slide_h)` | Scales a bounding box from thumbnail to full-slide coordinates. **Max 30px for thumb_w and thumb_h.** |
| `fetch_roi(slide_uid, x, y, width, height, output_path)` | Fetches a high-resolution ROI from a whole-slide image. Width and height are capped at 2700px. |
| `get_series_instances(series_uid)` | Lists all pyramid-level instances in a WSI series |
| `fetch_dicom_instance(study_uid, series_uid, instance_uid, output_path)` | Downloads a DICOM instance file from the DICOMweb server |

---

### mcp-utils

General-purpose file and DICOM utilities.

| Tool | Description |
|---|---|
| `parse_dicom(file_path)` | Parses a DICOM file and extracts metadata (modality, body part, dimensions, patient info) |
| `parse_dicom_directory(dir_path)` | Parses all DICOM files in a directory, grouped by series |
| `create_directory(path)` | Creates a directory and any missing parent directories |
| `move_file(src, dst)` | Moves a file or directory |
| `copy_file(src, dst)` | Copies a file |
| `delete_file(path)` | Deletes a file (not directories) |
| `write_file(path, content)` | Writes text content to a file, creating parent directories if needed |
| `read_file(path)` | Reads text content from a file |
| `write_json(path, data)` | Writes a JSON object to a file |
| `list_directory(path)` | Lists files and subdirectories with name, type, size, and modification time |
| `get_file_metadata(path)` | Returns size, creation/modification time, and extension for a file or directory |
| `find_files(directory, pattern, recursive?)` | Finds files matching a glob pattern within a directory |

---

### fhir (optional)

Connects to a FHIR R4 server over HTTP MCP. Used to write clinical findings as structured FHIR resources. This server is optional and can be added via the UI Settings page without restarting the backend.

Default URL: `http://localhost:8000/mcp`

Typical usage: create an anonymous `Patient` resource, then create a linked `Observation` recording a clinical finding.

---

## Built-in Tools

These tools are always available to the agent regardless of which MCP servers are connected.

### Task Management

| Tool | Description |
|---|---|
| `queue_task(task_type, description, input_data)` | Queues a long-running operation as a background task and returns immediately. Use for MONAI inference (`task_type: "inference"`) or report generation (`task_type: "report"`). The user is notified when the task finishes. |
| `list_tasks()` | Lists all background tasks for the current session and their status (`queued`, `running`, `completed`, `failed`) |
| `goal_achieved(summary)` | Signals that the agent has completed its goal. Terminates the execution loop and returns the summary to the user. |

### Short-Term Memory (stateless mode only)

These tools are only available when the backend is configured in stateless LLM mode (`/api/llm-mode`). In the default stateful mode they are not present.

| Tool | Description |
|---|---|
| `update_agent_notes(key, value)` | Persists a key/value fact across iterations (e.g., a file path, a count, a constraint discovered during execution) |
| `set_next_objective(objective)` | Declares the agent's next working step, included in the prompt context on the following iteration |

> **Note:** Stateless mode with STM is functional but experimental. The default stateful mode produces better results for most workflows.
