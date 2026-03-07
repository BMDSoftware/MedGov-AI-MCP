# MRI Modality Mapping

## Intensity Mean to Tissue Type (Sequence-aware Policy)
| Intensity Mean Availability | Tissue-Type Mapping Policy |
|----------------------------|----------------------------|
| Sequence provided | Use sequence-specific mapping table from model file |
| Sequence missing | Keep tissue type as indeterminate |

## Generic MRI Intensity Bands (Use with caution)
| Intensity Range | Tissue Type Hint |
|-----------------|------------------|
| < 200 | Fluid/CSF-like signal |
| 200 to 800 | Intermediate soft tissue signal |
| 800 to 2000 | Fibroglandular or white-matter-predominant signal |
| > 2000 | Hyperintense lesion/edema-like signal |

## Confidence to Clinical Wording
| Confidence Score | Clinical Wording |
|------------------|------------------|
| > 0.9 | Consistent with |
| 0.7-0.9 | Suggestive of |
| < 0.7 | Possible |
