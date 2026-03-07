# Pancreas CT DiNTS Segmentation Findings Mapping

## Label(s)
| Label ID | Structure |
|----------|----------|
| 1        | Pancreas |
| 2        | Tumor    |

## Volume (cm³) to Severity
| Volume Range (cm³) | Severity |
|-------------------|----------|
| < 50              | Normal   |
| 50–100            | Mild     |
| 100–200           | Moderate |
| > 200             | Severe   |

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