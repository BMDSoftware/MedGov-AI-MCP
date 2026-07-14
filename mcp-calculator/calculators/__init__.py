"""Medical Calculators Package
包含各种医学计算器的实现
"""

# 人体测量学和基础计算
from .bmi_calculator import BMICalculator  # ID:6 体重指数计算器
from .bsa_calculator import BSACalculator  # ID:60 体表面积计算器
from .ideal_body_weight_calculator import IdealBodyWeightCalculator  # ID:10 理想体重计算器
from .adjusted_body_weight_calculator import AdjustedBodyWeightCalculator  # ID:62 调整体重计算器
from .target_weight_calculator import TargetWeightCalculator  # ID:61 目标体重计算器

# # 心血管计算器
from .mean_arterial_pressure_calculator import MeanArterialPressureCalculator  # ID:5 平均动脉压计算器
from .qtc_bazett_calculator import QTcBazettCalculator  # ID:11 QTc间期计算器(Bazett公式)
from .qtc_fredericia_calculator import QTcFredericiaCalculator  # ID:56 QTc间期计算器(Fredericia公式)
from .qtc_framingham_calculator import QTcFraminghamCalculator  # ID:57 QTc间期计算器(Framingham公式)
from .qtc_hodges_calculator import QTcHodgesCalculator  # ID:58 QTc间期计算器(Hodges公式)
from .qtc_rautaharju_calculator import QTcRautaharjuCalculator  # ID:59 QTc间期计算器(Rautaharju公式)
from .cha2ds2_vasc_calculator import CHA2DS2VAScCalculator  # ID:4 CHA2DS2-VASc卒中风险评分
from .has_bled_calculator import HasBledCalculator  # ID:25 HAS-BLED出血风险评分
from .heart_score_calculator import HeartScoreCalculator  # ID:18 HEART评分计算器
from .cardiac_risk_index_calculator import CardiacRiskIndexCalculator  # ID:17 心脏风险指数计算器
from .framingham_calculator import FraminghamCalculator  # ID:46 Framingham风险评分
from .wells_dvt_calculator import WellsDVTCalculator  # ID:16 Wells深静脉血栓评分
from .caprini_calculator import CapriniCalculator  # ID:36 Caprini血栓风险评估

# # 肾脏功能计算器
from .creatinine_clearance_calculator import CreatinineClearanceCalculator  # ID:2 肌酐清除率计算器
from .ckd_epi_gfr_calculator import CKDEPIGFRCalculator  # ID:3 CKD-EPI肾小球滤过率计算器
from .mdrd_gfr_calculator import MDRDGFRCalculator  # ID:9 MDRD肾小球滤过率计算器
from .fena_calculator import FENaCalculator  # ID:40 钠排泄分数计算器

# # 肝脏功能计算器
from .child_pugh_calculator import ChildPughCalculator  # ID:15 Child-Pugh肝功能分级
from .meld_na_calculator import MeldNaCalculator  # ID:23 MELD-Na评分计算器
from .fibrosis_4_calculator import Fibrosis4Calculator  # ID:19 FIB-4肝纤维化指数

# # 实验室计算器
from .anion_gap_calculator import AnionGapCalculator  # ID:39 阴离子间隙计算器
from .delta_gap_calculator import DeltaGapCalculator  # ID:63 Delta间隙计算器
from .delta_ratio_calculator import DeltaRatioCalculator  # ID:64 Delta比值计算器
from .albumin_corrected_anion_gap_calculator import AlbuminCorrectedAnionGapCalculator  # ID:65 白蛋白校正阴离子间隙
from .albumin_corrected_delta_gap_calculator import AlbuminCorrectedDeltaGapCalculator  # ID:66 白蛋白校正Delta间隙
from .albumin_delta_ratio_calculator import AlbuminDeltaRatioCalculator  # ID:67 白蛋白Delta比值计算器
from .calcium_correction_calculator import CalciumCorrectionCalculator  # ID:7 钙离子校正计算器
from .sodium_correction_hyperglycemia_calculator import SodiumCorrectionHyperglycemiaCalculator  # ID:26 高血糖钠离子校正
from .serum_osmolality_calculator import SerumOsmolalityCalculator  # ID:30 血清渗透压计算器
from .ldl_cholesterol_calculator import LDLCholesterolCalculator  # ID:44 LDL胆固醇计算器
from .homa_ir_calculator import HOMAIRCalculator  # ID:31 HOMA-IR胰岛素抵抗指数
from .free_water_deficit_calculator import FreeWaterDeficitCalculator  # ID:38 自由水缺失计算器

# # 危重症和评分系统
from .apache_ii_calculator import ApacheIICalculator  # ID:28 APACHE II急性生理评分
from .sofa_calculator import SOFACalculator  # ID:43 SOFA序贯器官衰竭评估
from .sirs_criteria_calculator import SIRSCriteriaCalculator  # ID:51 SIRS全身炎症反应综合征
from .glasgow_coma_score_calculator import GlasgowComaScoreCalculator  # ID:21 Glasgow昏迷评分
from .glasgow_bleeding_score_calculator import GlasgowBleedingScoreCalculator  # ID:27 Glasgow出血评分
from .cci_calculator import CCICalculator  # ID:32 Charlson合并症指数

# # 呼吸系统计算器
from .curb_65_calculator import CURB65Calculator  # ID:45 CURB-65肺炎严重程度评分
from .psi_calculator import PSICalculator  # ID:29 肺炎严重程度指数
from .wells_pe_calculator import WellsPECalculator  # ID:8 Wells肺栓塞评分
from .perc_calculator import PERCCalculator  # ID:48 PERC肺栓塞排除标准

# # 感染和炎症计算器
from .centor_score_calculator import CentorScoreCalculator  # ID:20 Centor链球菌性咽炎评分
from .feverpain_calculator import FeverPAINCalculator  # ID:33 FeverPAIN咽炎评分

# # 液体和药物计算器
from .maintenance_fluid_calculator import MaintenanceFluidCalculator  # ID:22 维持液体计算器
from .steroid_conversion_calculator import SteroidConversionCalculator  # ID:24 激素转换计算器
from .mme_calculator import MMECalculator  # ID:49 吗啡当量剂量计算器

# 妊娠相关计算器
from .estimated_conception_calculator import EstimatedConceptionCalculator  # ID:68 预计受孕日期计算器
from .estimated_gestational_age_calculator import EstimatedGestationalAgeCalculator  # ID:69 预计妊娠期计算器
from .estimated_due_date_calculator import EstimatedDueDateCalculator  # ID:13 预计分娩日期计算器

# 肿瘤学计算器
from .lung_cancer_staging_calculator import LungCancerStagingCalculator  # ID:70 肺癌TNM分期计算器(中文版)

__all__ = [
    "BMICalculator",
    "BSACalculator",
    "IdealBodyWeightCalculator",
    "AdjustedBodyWeightCalculator",
    "TargetWeightCalculator",
    "MeanArterialPressureCalculator",
    "QTcBazettCalculator",
    "QTcFredericiaCalculator",
    "QTcFraminghamCalculator",
    "QTcHodgesCalculator",
    "QTcRautaharjuCalculator",
    "CHA2DS2VAScCalculator",
    "HasBledCalculator",
    "HeartScoreCalculator",
    "CardiacRiskIndexCalculator",
    "FraminghamCalculator",
    "CreatinineClearanceCalculator",
    "CKDEPIGFRCalculator",
    "MDRDGFRCalculator",
    "FENaCalculator",
    "ChildPughCalculator",
    "MeldNaCalculator",
    "Fibrosis4Calculator",
    "AnionGapCalculator",
    "DeltaGapCalculator",
    "DeltaRatioCalculator",
    "AlbuminCorrectedAnionGapCalculator",
    "AlbuminCorrectedDeltaGapCalculator",
    "AlbuminDeltaRatioCalculator",
    "CalciumCorrectionCalculator",
    "SodiumCorrectionHyperglycemiaCalculator",
    "SerumOsmolalityCalculator",
    "LDLCholesterolCalculator",
    "HOMAIRCalculator",
    "FreeWaterDeficitCalculator",
    "ApacheIICalculator",
    "SOFACalculator",
    "SIRSCriteriaCalculator",
    "GlasgowComaScoreCalculator",
    "GlasgowBleedingScoreCalculator",
    "CURB65Calculator",
    "PSICalculator",
    "WellsPECalculator",
    "PERCCalculator",
    "WellsDVTCalculator",
    "CapriniCalculator",
    "CentorScoreCalculator",
    "FeverPAINCalculator",
    "CCICalculator",
    "MaintenanceFluidCalculator",
    "SteroidConversionCalculator",
    "MMECalculator",
    "EstimatedConceptionCalculator",
    "EstimatedGestationalAgeCalculator",
    "EstimatedDueDateCalculator",
    "LungCancerStagingCalculator",
]
