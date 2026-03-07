---
name: radiology-workflow-sequencer
description: End-to-end MONAI to RadReport orchestration skill for radiology workflows. Use when the task requires deterministic workflow sequencing, inference-to-report mapping, RadReport prompt shaping, sparse-output handling without follow-up questions, and validation of generated report drafts against raw MONAI findings.
---

# Radiology Workflow Sequencer

## Scope

Use this skill to convert MONAI inference output into a clinically structured RadReport draft through a fixed sequence and explicit validation.

This is an instruction-only skill.

- No `scripts/` directory is provided.
- Do not call `skills.execute_script`.

## Required Sequence

1. Call `monai.analyze_image(path=...)`.
2. Resolve model selection and call `monai.download_model(model_name=...)` if needed.
3. Call `monai.run_inference(image_path=..., model_name=...)`.
4. Normalize `monai_raw_result` into `structured_findings`.
5. Build `template_selection_payload`.
6. Run 3-pass template search using `radlex.find_templates`.
7. For selected candidate, call `radlex.get_template_schema(template_id=...)` (compact mode by default).
8. Map `structured_findings` into `radreport_findings_payload` by schema keys/aliases.
9. Call `radlex.generate_report(template_id=..., findings=..., report_title=...)`.
10. Run validation checks (`workflow_validation_result`).
11. Finalize output with mandatory safety statement.

## 3-Pass Template Search (Strict)

Use `radlex.find_templates(query?, specialty_code?)` in this order:

1. Pass 1 (specific): call with `initial_query` and `resolved_specialty`.
2. Pass 2 (generalized): if pass 1 has no usable template, generalize query by dropping least-specific terms while keeping modality + body part + top class keyword. Call with generalized query + same specialty.
3. Pass 3 (specialty-only): if pass 2 fails, call with `specialty_code` only (omit query).

If all 3 passes fail, return stopped result with:

- `reason: "radlex_template_unresolved"`

Usable template criteria:

- has `id` or `template_id`,
- `radlex.get_template_schema` succeeds,
- compact schema includes non-empty writable `fields` (or `all_fields` if requesting `response_mode="full"`).

## Confidence and Wording Policy

- Confidence threshold `Z = 0.65`.
- If derived finding confidence is `< 0.65`, wording must be inconclusive.
- Never present low-confidence findings as definitive.

## Sparse Output Policy

- Never ask the user for supplemental context.
- Leave missing non-MONAI fields empty/null.
- Continue workflow without inventing modality, body part, or indication.

## Required Stop Reasons

- `radlex_template_unresolved`
- `radlex_generation_failed`
- `qa_failed`


## Reference Navigation

- Read `references/workflow_sequence.md` for procedural flow and fallback logic.
- Read `references/data_contracts.md` for all object contracts.
- Read `references/inference_to_report_mapping.md` for class/modality mapping and confidence policy.
- Read `references/prompt_shaping.md` for clinical phrasing rules.
- Read `references/sparse_output_policy.md` for missing-data handling.
- Read `references/validation_step.md` for pre-finalization checks.
