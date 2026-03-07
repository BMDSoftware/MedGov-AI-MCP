# Inference-to-Report Mapping

## Purpose

Map MONAI classes and context to RadReport template search strategy and report phrasing.

## Confidence Policy

- Derive confidence per finding from available model output signals.
- If no explicit probability/confidence exists, use conservative proxy:
  - `0.70` for clear quantitative structure presence with strong volume signal.
  - `0.60` for sparse/partial signal.
- Threshold `Z = 0.65`.
- If confidence `< 0.65`, mark finding and impression wording as inconclusive.

## Seed Mapping Table

| Class/Structure Pattern | Modality | Body Part | Query Terms | Specialty Hint |
|---|---|---|---|---|
| spleen | CT | abdomen | `CT spleen injury grade` | AB |
| liver | CT | abdomen | `CT liver lesion` | AB |
| pancreas | CT | abdomen | `CT pancreas` | GI |
| kidney_right or kidney_left | CT | abdomen | `CT renal mass` | GU |
| lung_* or nodule | CT | chest | `CT chest pulmonary nodule` | CH |

## Fallback Mapping

When class is unknown:

1. Build query from modality + body part only.
2. Use top detectable structure name if present.
3. If specialty cannot be resolved, use `OT`.

## Specialty Resolution Rules

1. First priority: seed table specialty.
2. Second priority: body-part-derived specialty mapping.
3. Final fallback: `OT`.

## Output Requirements

For each normalized finding:

- assign `priority`,
- assign `confidence` and `confidence_band`,
- generate one clinically readable sentence for mapping payload.

Never promote inconclusive findings into definitive statements.
