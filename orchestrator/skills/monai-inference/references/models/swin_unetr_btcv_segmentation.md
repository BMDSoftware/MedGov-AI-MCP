# Swin UNETR BTCV Segmentation Findings Mapping

## Label(s)
| Label ID | Structure              |
|----------|------------------------|
| 1        | Spleen                 |
| 2        | Right Kidney           |
| 3        | Left Kidney            |
| 4        | Gallbladder            |
| 5        | Esophagus              |
| 6        | Liver                  |
| 7        | Stomach                |
| 8        | Aorta                  |
| 9        | Inferior Vena Cava     |
| 10       | Portal Vein/Splenic Vein |
| 11       | Pancreas               |
| 12       | Right Adrenal Gland    |
| 13       | Left Adrenal Gland     |

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