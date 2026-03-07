# Sparse Output Policy

## Mandatory Behavior

- Never ask the user for supplemental context.
- Leave missing non-MONAI fields as `null` or empty strings/arrays.
- Continue workflow with explicit uncertainty where needed.

## Missing Field Handling

When missing:

- `modality`: keep `null`; do not infer from unsupported hints.
- `body_part`: keep `null`; do not invent.
- `clinical_indication`: keep `null`.
- patient-specific details: keep empty/null.

Allowed inference:

- Only from explicit tool outputs (`monai.analyze_image` and `monai.run_inference`).

## Reporting with Sparse Inputs

- Preserve factual quantitative statements.
- Use inconclusive phrasing when confidence is low or context is incomplete.
- Do not block report generation solely due to missing non-critical context.

## Non-Compliant Behavior (Do Not Do)

- Asking user follow-up questions to fill gaps.
- Guessing modality/body part/indication.
- Filling placeholders with fabricated values.
