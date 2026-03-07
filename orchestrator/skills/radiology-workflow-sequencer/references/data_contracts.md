# Data Contracts

## 1) `monai_raw_result`

Input from `monai.run_inference`.

```json
{
  "status": "success",
  "model_used": "string",
  "model_type": "segmentation|detection|classification",
  "input_image": "string",
  "results": {
    "detected_structures": [
      {
        "label_id": 1,
        "name": "string",
        "voxel_count": 0,
        "volume_percentage": 0.0,
        "volume_cm3": 0.0,
        "detected": true
      }
    ]
  },
  "labels": {}
}
```

## 2) `structured_findings`

Normalized findings used for mapping and phrasing.

```json
{
  "study_context": {
    "modality": "string|null",
    "body_part": "string|null",
    "clinical_indication": "string|null"
  },
  "model_context": {
    "model_name": "string",
    "model_type": "string"
  },
  "findings": [
    {
      "finding_id": "string",
      "class_name": "string",
      "label_id": 1,
      "voxel_count": 0,
      "volume_percentage": 0.0,
      "volume_cm3": 0.0,
      "confidence": 0.0,
      "confidence_band": "confident|suggestive|inconclusive",
      "priority": "critical|major|minor"
    }
  ],
  "sparse_fields": ["string"],
  "status": "ok|needs_more_data|blocked"
}
```

## 3) `template_selection_payload`

```json
{
  "initial_query": "string",
  "generalized_query": "string",
  "resolved_specialty": "string",
  "search_passes": [
    {"pass": 1, "query": "string", "specialty_code": "string"},
    {"pass": 2, "query": "string", "specialty_code": "string"},
    {"pass": 3, "query": null, "specialty_code": "string"}
  ]
}
```

## 4) `radreport_findings_payload`

Schema-aligned dict passed to `radlex.generate_report`.

```json
{
  "key_or_alias": "mapped clinical text",
  "another_key": "mapped clinical text"
}
```

Rules:

- Keys must be valid schema keys/aliases.
- Values must be concise clinical text from supported findings only.

## 5) `workflow_validation_result`

```json
{
  "passed": true,
  "checks": [
    {
      "name": "consistency|coverage|confidence_wording|safety_statement",
      "passed": true,
      "details": "string"
    }
  ],
  "failure_reason": "radlex_template_unresolved|radlex_generation_failed|qa_failed|null"
}
```
