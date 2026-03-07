# Lung Nodule CT Detection Findings Mapping

## Label(s)
| Label ID | Structure |
|----------|----------|
| 1        | Nodule   |

## Volume (cm³) to Severity
| Volume Range (cm³) | Severity |
|-------------------|----------|
| < 0.5             | Normal   |
| 0.5–1.0           | Mild     |
| 1.0–2.0           | Moderate |
| > 2.0             | Severe   |

## Intensity Mean (HU) to Tissue Type
| HU Range | Tissue Type |
|----------|-------------|
| < -50    | Fat         |
| -50–50   | Soft Tissue |
| 50–200   | Blood/Fluid |
| > 200    | Calcification |

## Confidence Mapping
| Confidence Score | Clinical Wording     |
|------------------|---------------------|
| > 0.9            | Consistent with     |
| 0.7–0.9          | Suggestive of       |
| < 0.7            | Possible            |