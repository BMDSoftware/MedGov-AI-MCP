# BraTS MRI Segmentation Findings Mapping

## Label(s)
| Label ID | Structure        |
|----------|------------------|
| 1        | Necrotic Core    |
| 2        | Edema           |
| 3        | Enhancing Tumor |

## Volume (cm³) to Severity
| Volume Range (cm³) | Severity |
|-------------------|----------|
| < 10              | Normal   |
| 10–30             | Mild     |
| 30–60             | Moderate |
| > 60              | Severe   |

## Intensity Mean (MRI) to Tissue Type
| Intensity Range | Tissue Type |
|-----------------|-------------|
| < 200           | CSF         |
| 200–800         | Gray Matter |
| 800–2000        | White Matter|
| > 2000          | Tumor/Edema |

## Confidence Mapping
| Confidence Score | Clinical Wording     |
|------------------|---------------------|
| > 0.9            | Consistent with     |
| 0.7–0.9          | Suggestive of       |
| < 0.7            | Possible            |