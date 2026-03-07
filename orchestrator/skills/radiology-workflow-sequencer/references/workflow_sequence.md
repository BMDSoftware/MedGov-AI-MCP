# Workflow Sequence

## Purpose

Define deterministic MONAI -> RadReport sequencing with fixed fallbacks.

## Step-by-Step Flow

1. `monai.analyze_image(path)`
   - Extract: modality hints, dimensionality, recommended models.
2. Resolve model
   - Select model from recommendations or configured mapping.
   - If model not downloaded, call `monai.download_model(model_name)`.
3. `monai.run_inference(image_path, model_name)`
   - Build `monai_raw_result`.
4. Normalize to `structured_findings`
   - Extract structures, counts, percentages, volumes, and confidence proxy.
5. Build template search query (`template_selection_payload`)
   - Construct specific query from modality + body part + top structure/class + indication tokens when available.
6. Template search with strict 3-pass fallback:
   - Pass 1: specific query + specialty.
   - Pass 2: generalized query + specialty.
   - Pass 3: specialty only.
7. Candidate validation
   - For each candidate, call `radlex.get_template_schema(template_id)` (compact default).
   - Select first candidate with non-empty `fields` (or `all_fields` when using `response_mode="full"`).
8. Build `radreport_findings_payload`
   - Map findings to schema keys/aliases.
9. `radlex.generate_report(template_id, findings, report_title)`
10. Validate generated draft
   - Produce `workflow_validation_result`.
11. Finalize or stop
   - On validation failure: `qa_failed`.
   - On generation failure after retry: `radlex_generation_failed`.
   - On no template after 3 passes: `radlex_template_unresolved`.

## Query Generalization Rule (Pass 2)

When pass 1 fails, drop least-specific tokens in this order:

1. generic qualifiers (for example: "possible", "mild", "chronic", "follow-up"),
2. vague indication adjectives,
3. nonessential free-text modifiers.

Keep:

- modality token,
- body-part token,
- top class/structure token.

## Failure Handling

- If `radlex.generate_report` returns `unknown_fields` or `invalid_choice`, remap once and retry generation once.
- If retry fails, stop with `radlex_generation_failed`.
- Never bypass validation.
