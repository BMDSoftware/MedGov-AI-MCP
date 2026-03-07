# Whole Body CT Segmentation Findings Mapping

## Label(s)
| Label ID | Structure |
|----------|----------|
| 1        | Spleen   |
| 2        | Kidney Right |
| 3        | Kidney Left |
| 4        | Gallbladder |
| 5        | Liver |
| 6        | Stomach |
| 7        | Aorta |
| 8        | Inferior Vena Cava |
| 9        | Portal Vein/Splenic Vein |
| 10       | Pancreas |
| 11       | Adrenal Gland Right |
| 12       | Adrenal Gland Left |
| ...      | ... (see server.py for full list) |

## Volume (cm³) to Severity
| Volume Range (cm³) | Severity |
|-------------------|----------|
| < 150             | Normal   |
| 150–250           | Mild     |
| 250–400           | Moderate |
| > 400             | Severe   |

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