# Prompt Shaping for RadReport

## Goal

Transform MONAI quantitative findings into clinically useful template-selection and report text without inventing unsupported clinical claims.

## Template Selection Query Style

Use compact, clinical token ordering:

1. modality
2. body part
3. top class/structure
4. optional indication token (if present)

Example:

`CT abdomen spleen trauma`

## Findings Phrasing Rules

- Base text on observed values:
  - `volume_cm3`
  - `volume_percentage`
  - `voxel_count`
- Prefer objective wording:
  - "Spleen segmentation is present with estimated volume 248.4 cm3."
- Avoid unsupported pathology assertions:
  - Do not claim definitive diagnosis solely from structure presence.

## Impression Tiers

### Confident (confidence >= 0.80)

- "Findings are consistent with ..."

### Suggestive (0.65 <= confidence < 0.80)

- "Findings may represent ..."

### Inconclusive (confidence < 0.65)

- "Findings are inconclusive and require clinical/radiologic correlation."

Inconclusive tier is mandatory when confidence is below threshold.

## Forbidden Patterns

- No fabricated signs not present in MONAI-derived findings.
- No deterministic pathology language from sparse or low-confidence output.
- No patient-history assumptions when fields are missing.
