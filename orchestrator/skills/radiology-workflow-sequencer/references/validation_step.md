# Validation Step

## Purpose

Validate generated report draft against normalized MONAI-derived findings before finalization.

## Validation Checks

### 1. Consistency Check

- No contradiction between report text and `structured_findings` quantitative values.
- If a value is cited, it must match extracted value (or rounded equivalent).

### 2. Coverage Check

- All `priority=critical` findings must appear in findings or impression text.

### 3. Confidence Wording Check

- For findings with confidence `< 0.65`, wording must be inconclusive.
- No definitive language for low-confidence findings.

### 4. Safety Statement Check

- Final output must include exact statement:
  `Final interpretation requires licensed radiologist review.`

## Failure Outcomes

- Template not found after 3 passes -> `radlex_template_unresolved`.
- RadReport generation fails after one retry -> `radlex_generation_failed`.
- Any validation check fails -> `qa_failed`.

## Example `workflow_validation_result`

```json
{
  "passed": false,
  "checks": [
    {
      "name": "confidence_wording",
      "passed": false,
      "details": "Low-confidence pancreas finding was phrased as definitive."
    }
  ],
  "failure_reason": "qa_failed"
}
```

## Scenario Checklist

1. Discovery: skill appears in `SkillsManager.discover()`.
2. Sequencing: MONAI-first enforced before RadReport calls.
3. Mapping: valid `structured_findings` generated from MONAI output.
4. Threshold: confidence below `0.65` yields inconclusive wording.
5. Template fallback: pass1 miss -> pass2 generalized miss -> pass3 specialty-only success.
6. Template unresolved: all passes fail -> `radlex_template_unresolved`.
7. Sparse mode: missing context stays null/empty with no user follow-up.
8. Validation failure: mismatch between draft and findings -> `qa_failed`.
