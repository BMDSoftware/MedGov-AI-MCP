[tools Documentation]

# MCP Tools Documentation

## Overview

The agent interacts with various Model Context Protocol (MCP) servers to perform specialized tasks. Each MCP server provides specific capabilities that the agent can leverage to achieve its goals. The MCPs are designed to be modular and extensible, allowing for easy addition of new capabilities as needed.

## Available MCPs

- **MCP Skills**: Provides access to agent skills that the agent can invoke as needed (e.g., text processing, workflow automation).
- **MCP Monai**: Handles medical image analysis tasks, such as segmentation and detection, using MONAI models.
- **MCP Utils**: Offers utility functions and services, such as DICOM parsing and data preprocessing, to support other MCPs and agent workflows.
- **MCP Radlex**: Provides medical terminology and ontology services, such as filling structured report templates using RadLex terms.

## MCP Tools

### MCP MONAI

The MCP MONAI server provides a set of tools for medical image analysis using MONAI pre-trained models. The available tools include:

- `get_monai_info()`: Returns MONAI and PyTorch version info, CUDA/GPU details, bundle directory, and loaded models.
- `analyze_image(path: str)`: Analyzes a medical image to detect its type, modality, and characteristics. Returns metadata, statistics, and recommended models for the image.
- `list_models(category=None, modality=None, body_part=None)`: Lists available pre-trained models from the MONAI Model Zoo, with optional filters for category, modality, or body part.
- `download_model(model_name: str)`: Downloads a pre-trained model bundle from the MONAI Model Zoo. Must be called before running inference if the model is not already downloaded.
- `run_inference(image_path: str, model_name: str)`: Runs real inference on a medical image using a selected MONAI pre-trained model. Handles 2D/3D images, performs preprocessing, and returns segmentation/detection results.

### MCP Skills

The MCP Skills server provides a variety of skills that the agent can invoke to perform tasks such as text processing, workflow automation, and more. It has the following tools:

- `list_skills()`: Lists all available skills with their descriptions and parameters.
- `read_skill_file(skill_name: str)`: Reads the content of the `SKILL.md`file
- `execute_script(skill_name: str, command: str)`: Executes the script associated with a skill, passing any required parameters.
- `read_references(skill_name: str, file_path: str)`: Reads reference files associated with a skill, which can be used to provide additional context or information for the skill execution.
- `read_asset(skill_name: str, asset_path: str)`: Reads asset files associated with a skill, which can include images, templates, or other resources needed for the skill execution.

### MCP Utils

The MCP Utils server provides utility functions and services that support other MCPs and agent workflows. The available tools include:

- `parse_dicom(file_path: str)`: Parses a DICOM file and extracts relevant metadata and image data.
- `parse_dicom_directory(directory_path: str)`: Parses a directory of DICOM files, extracting metadata and image data for each file.

### MCP Radlex

The MCP Radlex server provides medical terminology and ontology services, such as filling structured report templates using RadLex terms. The available tools include:

- `list_subspecialties()`: Lists all available subspecialties in the RadLex ontology.
- `find_templates(query: str, specialty_code: str)`: Finds structured report templates based on a query and specialty code. 
- `get_template_schema(template_id: str)`: Retrieves the schema for a specific structured report template, including required fields and their types.
- `generate_report(template_id: str, findings: Dict, report_title: str)`: Generates a structured report based on a template and provided findings, returning the filled report in a structured format.

## Built In Tools

In addition to the MCP tools, there are also built-in tools that the agent can use for file management and other basic operations. These include:

### Background Task Management (Built-in Tools)

The following built-in tools are available for managing long-running or background operations, such as MONAI inference or report generation:

- `queue_task`: Queue a long-running operation as a background task. Use this instead of calling a tool directly whenever the operation may take more than a few seconds (e.g., MONAI inference, report generation, bulk analysis). The function returns immediately so you can keep talking to the user. The user will receive a notification when the task finishes.
  - **Parameters:**
    - `task_type` (string): Category of the task. Use 'inference' for MONAI model runs, 'report' for report generation, or any descriptive string for other tasks.
    - `description` (string): Human-readable label shown in the Results tab, e.g. 'WholeBody segmentation on PANCREAS_0001'.
    - `input_data` (object): Task-specific inputs as a JSON object. For 'inference': {image_path, model_name}. For 'report': {task_ids, patient_context}.

- `list_tasks`: List all background tasks for the current session and their status. Use this when the user asks whether their inference or report tasks have finished, or to check how many tasks are still running.