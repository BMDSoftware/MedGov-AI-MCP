"""
肺癌TNM分期计算器 (AJCC第九版)
Lung Cancer TNM Staging Calculator (AJCC 9th Edition)
支持多种TNM分期类型：cTNM, pTNM, ycTNM, ypTNM, rcTNM, rpTNM
"""

from typing import Dict, Any, List
from medcalc import (
    BaseCalculator, 
    CalculatorInfo, 
    Parameter, 
    ParameterType, 
    ValidationResult, 
    CalculationResult,
    register_calculator
)


@register_calculator("lung_cancer_staging")
class LungCancerStagingCalculator(BaseCalculator):
    """肺癌TNM分期计算器实现 - 支持多种分期类型"""
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=70,
            name="肺癌TNM分期计算器 (AJCC第九版)",
            category="oncology",
            description="根据AJCC第九版标准计算肺癌TNM分期，支持临床分期(cTNM)和病理分期(pTNM)等多种分期类型",
            parameters=[
                # 0. 分期类型控制参数
                Parameter(
                    name="staging_type",
                    type=ParameterType.CHOICE,
                    required=True,
                    choices=["clinical", "pathologic"],
                    default="clinical",
                    description="分期类型：clinical=临床分期(基于影像学和临床检查)，pathologic=病理分期(基于手术病理检查)"
                ),
                Parameter(
                    name="treatment_stage",
                    type=ParameterType.CHOICE,
                    required=True,
                    choices=["initial", "post_neoadjuvant", "recurrence"],
                    default="initial",
                    description="治疗时机：initial=初始诊断/首次治疗前，post_neoadjuvant=新辅助治疗后，recurrence=复发时"
                ),
                
                # 1. 基础肿瘤信息
                Parameter(
                    name="tumor_size",
                    type=ParameterType.NUMERIC,
                    required=False,
                    unit="cm",
                    min_value=0,
                    max_value=20,
                    description="肿瘤最大径（厘米）- 用于确定T分期。病理分期时为手术标本测量值，临床分期时为影像学测量值"
                ),
                Parameter(
                    name="tumor_special_status",
                    type=ParameterType.CHOICE,
                    required=False,
                    choices=["normal_tumor", "cannot_assess", "no_primary_tumor", "adenocarcinoma_in_situ", "squamous_carcinoma_in_situ", "minimally_invasive_adenocarcinoma"],
                    default="normal_tumor",
                    description="肿瘤特殊情况：normal_tumor=可测量的原发肿瘤，cannot_assess=无法评估(临床分期时穿刺阴性或仅细胞学阳性，病理分期时标本处理限制)，no_primary_tumor=无原发肿瘤证据，adenocarcinoma_in_situ=腺癌原位癌(≤3cm纯磨玻璃)，squamous_carcinoma_in_situ=鳞癌原位癌，minimally_invasive_adenocarcinoma=微浸润性腺癌(≤3cm，浸润成分≤5mm)"
                ),
                
                # 2. 肿瘤侵犯特征
                Parameter(
                    name="tumor_invasion_features",
                    type=ParameterType.CHOICE,
                    required=False,
                    choices=["none", "visceral_pleura", "main_bronchus_not_carina", "carina_involved", "chest_wall_diaphragm", "mediastinal_structures", "atelectasis_to_hilum", "total_lung_atelectasis"],
                    default="none",
                    description="肿瘤侵犯情况：none=无特殊侵犯，visceral_pleura=侵犯脏层胸膜，main_bronchus_not_carina=累及主支气管但未到隆突，carina_involved=累及隆突，chest_wall_diaphragm=侵犯胸壁或膈肌或心包，mediastinal_structures=侵犯纵隔或心脏或大血管，atelectasis_to_hilum=肺不张或阻塞性肺炎累及肺门，total_lung_atelectasis=全肺不张。病理分期时基于组织学确认，临床分期时基于影像学判断"
                ),
                
                # 3. 多发病变模式  
                Parameter(
                    name="multifocal_pattern",
                    type=ParameterType.CHOICE,
                    required=False,
                    choices=["single_nodule", "multiple_same_lobe", "multiple_ipsilateral_different_lobe"],
                    default="single_nodule",
                    description="病变分布模式：single_nodule=单发结节，multiple_same_lobe=同一肺叶内多个结节，multiple_ipsilateral_different_lobe=同侧不同肺叶内多个结节。依据AJCC标准：同叶多发为T3，同侧异叶为T4"
                ),
                
                # 4. 淋巴结状况
                Parameter(
                    name="lymph_nodes_assessable",
                    type=ParameterType.BOOLEAN,
                    required=True,
                    default=True,
                    description="区域淋巴结是否可评估。病理分期时需要足够的淋巴结采样(推荐≥10个)，临床分期时基于影像学评估"
                ),
                Parameter(
                    name="lymph_node_involvement",
                    type=ParameterType.CHOICE,
                    required=False,
                    choices=["no_nodes", "ipsilateral_pulmonary_hilar", "single_ipsilateral_mediastinal", "multiple_ipsilateral_mediastinal", "contralateral_nodes", "supraclavicular_scalene"],
                    default="no_nodes",
                    description="淋巴结转移情况：no_nodes=无区域淋巴结转移，ipsilateral_pulmonary_hilar=同侧肺内或支气管周围或肺门淋巴结，single_ipsilateral_mediastinal=单个同侧纵隔或隆突下淋巴结，multiple_ipsilateral_mediastinal=多个同侧纵隔或隆突下淋巴结，contralateral_nodes=对侧纵隔或肺门淋巴结，supraclavicular_scalene=锁骨上或斜角肌淋巴结。病理分期时基于组织学检查，临床分期时基于影像学判断"
                ),
                
                # 5. 远处转移
                Parameter(
                    name="distant_metastasis",
                    type=ParameterType.CHOICE,
                    required=False,
                    choices=["no_metastasis", "contralateral_lung_nodules", "malignant_pleural_effusion", "pleural_pericardial_nodules", "pleural_implants", "single_organ_single_lesion", "single_organ_multiple_lesions", "multiple_organs_metastasis"],
                    default="no_metastasis",
                    description="远处转移情况：no_metastasis=无远处转移，contralateral_lung_nodules=对侧肺内结节，malignant_pleural_effusion=恶性胸膜积液或心包积液，pleural_pericardial_nodules=胸膜结节或心包结节，pleural_implants=胸膜种植（归类M1a），single_organ_single_lesion=单器官单发转移，single_organ_multiple_lesions=单器官多发转移，multiple_organs_metastasis=多器官多发转移。病理分期时如切除转移灶需病理确认"
                )
            ],
            references=[
                "AJCC Cancer Staging Manual, 9th Edition (2024)",
                "American Joint Committee on Cancer. Lung Cancer Staging",
                "NCCN Guidelines for Non-Small Cell Lung Cancer",
                "TNM评估总体原则 - 临床分期与病理分期指导"
            ]
        )
    
    def _get_staging_prefix(self, params: Dict[str, Any]) -> str:
        """根据分期类型和治疗时机确定分期前缀"""
        staging_type = params.get("staging_type", "clinical")
        treatment_stage = params.get("treatment_stage", "initial")
        
        if staging_type == "clinical":
            if treatment_stage == "initial":
                return "c"  # cTNM
            elif treatment_stage == "post_neoadjuvant":
                return "yc"  # ycTNM
            elif treatment_stage == "recurrence":
                return "rc"  # rcTNM
        elif staging_type == "pathologic":
            if treatment_stage == "initial":
                return "p"  # pTNM
            elif treatment_stage == "post_neoadjuvant":
                return "yp"  # ypTNM
            elif treatment_stage == "recurrence":
                return "rp"  # rpTNM
        
        return "c"  # 默认临床分期
    
    def _calculate_t_stage(self, params: Dict[str, Any]) -> str:
        """计算T分期"""
        staging_type = params.get("staging_type", "clinical")
        
        # 检查特殊情况
        tumor_special = params.get("tumor_special_status", "normal_tumor")
        
        # 映射特殊情况到T分期
        special_mapping = {
            "cannot_assess": "TX",
            "no_primary_tumor": "T0", 
            "adenocarcinoma_in_situ": "Tis(AIS)",
            "squamous_carcinoma_in_situ": "Tis(SC)",
            "minimally_invasive_adenocarcinoma": "T1a(mi)"
        }
        
        if tumor_special in special_mapping:
            return special_mapping[tumor_special]
        
        # 获取肿瘤大小
        tumor_size = params.get("tumor_size")
        if tumor_size is None:
            return "TX"  # 无法评估
        
        # 获取侵犯特征和多发模式
        invasion_features = params.get("tumor_invasion_features", "none")
        multifocal_pattern = params.get("multifocal_pattern", "single_nodule")
        
        # T4判断：>7cm或重要结构侵犯或同侧不同肺叶结节
        if (tumor_size > 7 or 
            invasion_features == "carina_involved" or
            invasion_features == "mediastinal_structures" or
            multifocal_pattern == "multiple_ipsilateral_different_lobe"):
            return "T4"
        
        # T3判断：5-7cm或特定侵犯或同一肺叶多发结节
        if (5 < tumor_size <= 7 or 
            invasion_features == "chest_wall_diaphragm" or 
            invasion_features == "total_lung_atelectasis" or
            multifocal_pattern == "multiple_same_lobe"):
            return "T3"
        
        # T2判断：3-5cm或脏层胸膜侵犯或主支气管累及或肺不张
        if (3 < tumor_size <= 5 or 
            invasion_features in ["visceral_pleura", "main_bronchus_not_carina", "atelectasis_to_hilum"]):
            # 特殊情况：特定侵犯且肿瘤≤3cm
            if invasion_features in ["visceral_pleura", "main_bronchus_not_carina", "atelectasis_to_hilum"] and tumor_size <= 3:
                return "T2a"
            # 基于肿瘤大小的T2分级
            elif 3 < tumor_size <= 4:
                return "T2a"
            elif 4 < tumor_size <= 5:
                return "T2b"
            # 特殊侵犯情况且肿瘤>3cm的分级
            elif invasion_features in ["visceral_pleura", "main_bronchus_not_carina", "atelectasis_to_hilum"]:
                if tumor_size <= 4:
                    return "T2a"
                else:
                    return "T2b"
        
        # T1判断：≤3cm且无特殊侵犯
        if tumor_size <= 3 and invasion_features == "none":
            if tumor_size <= 1:
                return "T1a"
            elif tumor_size <= 2:
                return "T1b"
            else:  # 2-3cm
                return "T1c"
        
        return "TX"
    
    def _calculate_n_stage(self, params: Dict[str, Any]) -> str:
        """计算N分期"""
        staging_type = params.get("staging_type", "clinical")
        
        # 检查是否可评估
        if not params.get("lymph_nodes_assessable", True):
            return "NX"
        
        # 获取淋巴结转移模式并映射到N分期
        lymph_involvement = params.get("lymph_node_involvement", "no_nodes")
        
        # 映射到标准N分期
        mapping = {
            "no_nodes": "N0",
            "ipsilateral_pulmonary_hilar": "N1", 
            "single_ipsilateral_mediastinal": "N2a",
            "multiple_ipsilateral_mediastinal": "N2b",
            "contralateral_nodes": "N3",
            "supraclavicular_scalene": "N3"
        }
        
        return mapping.get(lymph_involvement, "N0")
    
    def _calculate_m_stage(self, params: Dict[str, Any]) -> str:
        """计算M分期"""
        staging_type = params.get("staging_type", "clinical")
        
        # 获取远处转移模式并映射到M分期
        metastasis_pattern = params.get("distant_metastasis", "no_metastasis")
        
        # 映射到标准M分期
        mapping = {
            "no_metastasis": "M0",
            "contralateral_lung_nodules": "M1a",
            "malignant_pleural_effusion": "M1a", 
            "pleural_pericardial_nodules": "M1a",
            "pleural_implants": "M1a",
            "single_organ_single_lesion": "M1b",
            "single_organ_multiple_lesions": "M1c",
            "multiple_organs_metastasis": "M1c"
        }
        
        return mapping.get(metastasis_pattern, "M0")
    
    def _get_final_stage(self, t_stage: str, n_stage: str, m_stage: str) -> str:
        """根据TNM组合确定最终分期"""
        # M1期直接判断
        if m_stage == "M1a" or m_stage == "M1b":
            return "IVA"
        elif m_stage == "M1c":
            return "IVB"
        
        # 根据分期表确定分期
        stage_table = {
            # T1a
            ("T1a", "N0"): "IA1",
            ("T1a", "N1"): "IIA", 
            ("T1a", "N2a"): "IIB",
            ("T1a", "N2b"): "IIIA",
            ("T1a", "N3"): "IIIB",
            # T1b
            ("T1b", "N0"): "IA2",
            ("T1b", "N1"): "IIA",
            ("T1b", "N2a"): "IIB", 
            ("T1b", "N2b"): "IIIA",
            ("T1b", "N3"): "IIIB",
            # T1c
            ("T1c", "N0"): "IA3",
            ("T1c", "N1"): "IIA",
            ("T1c", "N2a"): "IIB",
            ("T1c", "N2b"): "IIIA", 
            ("T1c", "N3"): "IIIB",
            # T2a
            ("T2a", "N0"): "IB",
            ("T2a", "N1"): "IIB",
            ("T2a", "N2a"): "IIIA",
            ("T2a", "N2b"): "IIIB",
            ("T2a", "N3"): "IIIB",
            # T2b
            ("T2b", "N0"): "IIA", 
            ("T2b", "N1"): "IIB",
            ("T2b", "N2a"): "IIIA",
            ("T2b", "N2b"): "IIIB",
            ("T2b", "N3"): "IIIB",
            # T3
            ("T3", "N0"): "IIB",
            ("T3", "N1"): "IIIA",
            ("T3", "N2a"): "IIIA", 
            ("T3", "N2b"): "IIIB",
            ("T3", "N3"): "IIIC",
            # T4
            ("T4", "N0"): "IIIA",
            ("T4", "N1"): "IIIA",
            ("T4", "N2a"): "IIIB",
            ("T4", "N2b"): "IIIB", 
            ("T4", "N3"): "IIIC",
        }
        
        # 特殊情况处理
        if t_stage in ["TX", "T0", "Tis(AIS)", "Tis(SC)", "T1a(mi)"]:
            if t_stage == "Tis(AIS)" or t_stage == "Tis(SC)":
                return "0"  # 原位癌
            elif t_stage == "T1a(mi)":
                return "IA1"  # 微浸润性腺癌
            return "无法确定"
        
        key = (t_stage, n_stage)
        return stage_table.get(key, "无法确定")
    
    def validate_parameters(self, params: Dict[str, Any]) -> ValidationResult:
        errors = []
        warnings = []
        
        # 检查必需参数
        required_params = ["staging_type", "treatment_stage", "lymph_nodes_assessable"]
        for param in required_params:
            if param not in params:
                errors.append(f"缺少必需参数：{param}")
        
        # 检查分期类型和治疗时机组合的逻辑一致性
        staging_type = params.get("staging_type", "clinical")
        treatment_stage = params.get("treatment_stage", "initial")
        tumor_special = params.get("tumor_special_status", "normal_tumor")
        tumor_size = params.get("tumor_size")
        
        # 病理分期的特殊要求
        if staging_type == "pathologic":
            if tumor_special == "normal_tumor" and tumor_size is None:
                warnings.append("病理分期时建议提供手术标本的肿瘤大小，否则T分期将标记为pTX")
            
            # 病理分期时的淋巴结评估提示
            if params.get("lymph_nodes_assessable", True) and params.get("lymph_node_involvement", "no_nodes") == "no_nodes":
                warnings.append("病理分期时建议至少检查10个淋巴结以获得准确的N分期")
        
        # 临床分期的提示
        elif staging_type == "clinical":
            if tumor_special == "normal_tumor" and tumor_size is None:
                warnings.append("临床分期时未提供影像学测量的肿瘤大小，T分期将标记为cTX")
        
        # 新辅助治疗后的特殊提示
        if treatment_stage == "post_neoadjuvant":
            prefix = "yc" if staging_type == "clinical" else "yp"
            warnings.append(f"这是新辅助治疗后的{prefix}TNM分期，请确认所有参数反映新辅助治疗后的情况")
        
        # 复发时的特殊提示
        if treatment_stage == "recurrence":
            prefix = "rc" if staging_type == "clinical" else "rp"
            warnings.append(f"这是复发时的{prefix}TNM分期，请确认所有参数反映复发病变的情况")
        
        # 特殊情况的逻辑检查
        if tumor_special != "normal_tumor" and tumor_size is not None:
            warnings.append("已指定T分期特殊情况，肿瘤大小参数将被忽略")
        
        # 验证肿瘤大小范围
        if tumor_size is not None:
            if tumor_size < 0 or tumor_size > 20:
                errors.append("肿瘤大小应在0-20cm范围内")
            if tumor_size > 15:
                warnings.append("肿瘤大小超过15cm，请确认数值正确")
        
        # 验证选择参数的有效性
        valid_choices = {
            "staging_type": ["clinical", "pathologic"],
            "treatment_stage": ["initial", "post_neoadjuvant", "recurrence"],
            "tumor_special_status": ["normal_tumor", "cannot_assess", "no_primary_tumor", "adenocarcinoma_in_situ", "squamous_carcinoma_in_situ", "minimally_invasive_adenocarcinoma"],
            "tumor_invasion_features": ["none", "visceral_pleura", "main_bronchus_not_carina", "carina_involved", "chest_wall_diaphragm", "mediastinal_structures", "atelectasis_to_hilum", "total_lung_atelectasis"],
            "multifocal_pattern": ["single_nodule", "multiple_same_lobe", "multiple_ipsilateral_different_lobe"],
            "lymph_node_involvement": ["no_nodes", "ipsilateral_pulmonary_hilar", "single_ipsilateral_mediastinal", "multiple_ipsilateral_mediastinal", "contralateral_nodes", "supraclavicular_scalene"],
            "distant_metastasis": ["no_metastasis", "contralateral_lung_nodules", "malignant_pleural_effusion", "pleural_pericardial_nodules", "pleural_implants", "single_organ_single_lesion", "single_organ_multiple_lesions", "multiple_organs_metastasis"]
        }
        
        for param_name, valid_values in valid_choices.items():
            if param_name in params:
                value = params[param_name]
                if value not in valid_values:
                    errors.append(f"参数{param_name}的值'{value}'无效，有效选项：{valid_values}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def calculate(self, params: Dict[str, Any]) -> CalculationResult:
        # 获取分期类型前缀
        staging_prefix = self._get_staging_prefix(params)
        
        # 计算各个分期
        t_stage = self._calculate_t_stage(params)
        n_stage = self._calculate_n_stage(params)
        m_stage = self._calculate_m_stage(params)
        
        # 确定最终分期
        final_stage = self._get_final_stage(t_stage, n_stage, m_stage)
        
        # 生成带前缀的TNM分期
        tnm_with_prefix = f"{staging_prefix}{t_stage}{n_stage}{m_stage}"
        
        # 生成详细解释
        explanation = self._generate_explanation(params, t_stage, n_stage, m_stage, final_stage, staging_prefix)
        
        # 确定分期类型名称
        staging_type_names = {
            "c": "临床分期(cTNM)",
            "p": "病理分期(pTNM)",
            "yc": "新辅助治疗后临床分期(ycTNM)",
            "yp": "新辅助治疗后病理分期(ypTNM)",
            "rc": "复发临床分期(rcTNM)",
            "rp": "复发病理分期(rpTNM)"
        }
        
        return CalculationResult(
            value=final_stage,
            unit="期",
            explanation=explanation,
            metadata={
                "staging_type": staging_type_names.get(staging_prefix, "未知分期类型"),
                "staging_prefix": staging_prefix,
                "t_stage": t_stage,
                "n_stage": n_stage, 
                "m_stage": m_stage,
                "tnm_combined": tnm_with_prefix,
                "tumor_size": params.get("tumor_size"),
                "ajcc_version": "第九版",
                "treatment_stage": params.get("treatment_stage", "initial")
            },
            warnings=[]
        )
    
    def _generate_explanation(self, params: Dict[str, Any], t_stage: str, n_stage: str, m_stage: str, final_stage: str, staging_prefix: str) -> str:
        """生成详细的分期解释"""
        # 分期类型说明
        staging_type_descriptions = {
            "c": "临床分期 - 基于影像学和临床检查",
            "p": "病理分期 - 基于手术病理检查",
            "yc": "新辅助治疗后临床分期 - 基于治疗后影像学和临床检查",
            "yp": "新辅助治疗后病理分期 - 基于治疗后手术病理检查",
            "rc": "复发临床分期 - 基于复发时影像学和临床检查",
            "rp": "复发病理分期 - 基于复发时手术病理检查"
        }
        
        explanation = f"# 肺癌TNM分期计算结果 (AJCC第九版)\n\n"
        explanation += f"**分期类型**: {staging_type_descriptions.get(staging_prefix, '未知类型')}\n\n"
        
        # T分期解释
        explanation += "## T分期（原发肿瘤）\n"
        explanation += self._explain_t_stage(params, t_stage)
        
        # N分期解释
        explanation += "\n## N分期（区域淋巴结）\n"
        explanation += self._explain_n_stage(params, n_stage)
        
        # M分期解释
        explanation += "\n## M分期（远处转移）\n"
        explanation += self._explain_m_stage(params, m_stage)
        
        # 分期组合
        explanation += f"\n## 综合分期\n"
        explanation += f"TNM组合：{staging_prefix}{t_stage}{n_stage}{m_stage}\n"
        explanation += f"**最终分期：{final_stage}期**\n\n"
        
        # 根据分期类型添加特殊说明
        if staging_prefix in ["yc", "yp"]:
            explanation += "### 注意事项\n"
            explanation += "- 这是新辅助治疗后的分期，反映治疗后的病变情况\n"
            explanation += "- 该分期用于评估新辅助治疗的疗效和指导后续治疗\n"
        elif staging_prefix in ["rc", "rp"]:
            explanation += "### 注意事项\n"
            explanation += "- 这是复发时的分期，反映复发病变的情况\n"
            explanation += "- 该分期用于重新评估疾病状态和制定治疗方案\n"
        elif staging_prefix == "p":
            explanation += "### 注意事项\n"
            explanation += "- 病理分期是最准确的分期，基于手术标本的组织学检查\n"
            explanation += "- 该分期是制定术后辅助治疗和判断预后的金标准\n"
        
        return explanation
    
    def _explain_t_stage(self, params: Dict[str, Any], t_stage: str) -> str:
        """解释T分期判断过程"""
        staging_type = params.get("staging_type", "clinical")
        tumor_special = params.get("tumor_special_status", "normal_tumor")
        
        if tumor_special != "normal_tumor":
            explanations = {
                "TX": f"无法评估肿瘤 - {'手术标本处理限制或仅细胞学阳性' if staging_type == 'pathologic' else '影像学无法明确或仅穿刺细胞学阳性'}",
                "T0": "无原发肿瘤证据", 
                "Tis(AIS)": "腺癌原位癌（肿瘤最大径≤3cm，纯磨玻璃）",
                "Tis(SC)": "鳞癌原位癌",
                "T1a(mi)": "微浸润性腺癌（肿瘤最大径≤3cm，浸润成分≤5mm）"
            }
            return f"**{t_stage}**: {explanations.get(t_stage, '')}\n"
        
        tumor_size = params.get("tumor_size")
        if tumor_size is None:
            assessment_method = "手术标本" if staging_type == "pathologic" else "影像学"
            return f"**TX**: 未提供{assessment_method}测量的肿瘤大小，无法评估\n"
        
        assessment_method = "手术标本测量" if staging_type == "pathologic" else "影像学测量"
        explanation = f"肿瘤大小（{assessment_method}）：{tumor_size} cm\n"
        
        # 基于大小的判断
        if tumor_size <= 1:
            explanation += f"**{t_stage}**: 肿瘤最大径≤1cm\n"
        elif tumor_size <= 2:
            explanation += f"**{t_stage}**: 1cm < 肿瘤最大径≤2cm\n"
        elif tumor_size <= 3:
            explanation += f"**{t_stage}**: 2cm < 肿瘤最大径≤3cm\n" 
        elif tumor_size <= 4:
            explanation += f"**{t_stage}**: 3cm < 肿瘤最大径≤4cm\n"
        elif tumor_size <= 5:
            explanation += f"**{t_stage}**: 4cm < 肿瘤最大径≤5cm\n"
        elif tumor_size <= 7:
            explanation += f"**{t_stage}**: 5cm < 肿瘤最大径≤7cm\n"
        else:
            explanation += f"**{t_stage}**: 肿瘤最大径>7cm\n"
        
        # 其他影响因素
        invasion_features = params.get("tumor_invasion_features", "none")
        multifocal_pattern = params.get("multifocal_pattern", "single_nodule")
        
        other_factors = []
        
        # 侵犯特征描述
        invasion_base = {
            "visceral_pleura": "侵犯脏层胸膜",
            "main_bronchus_not_carina": "累及主支气管但未累及隆突",
            "carina_involved": "累及隆突",
            "chest_wall_diaphragm": "直接侵犯胸壁、膈肌或心包",
            "mediastinal_structures": "侵犯纵隔、心脏或大血管",
            "atelectasis_to_hilum": "肺不张或阻塞性肺炎累及肺门",
            "total_lung_atelectasis": "全肺不张"
        }
        
        if invasion_features != "none":
            invasion_desc = invasion_base.get(invasion_features, invasion_features)
            assessment_note = "（组织学确认）" if staging_type == "pathologic" else "（影像学判断）"
            other_factors.append(f"{invasion_desc}{assessment_note}")
        
        # 多发病变描述
        multifocal_descriptions = {
            "multiple_same_lobe": "同一肺叶内多发结节",
            "multiple_ipsilateral_different_lobe": "同侧不同肺叶内孤立结节"
        }
        
        if multifocal_pattern != "single_nodule":
            other_factors.append(multifocal_descriptions.get(multifocal_pattern, multifocal_pattern))
        
        if other_factors:
            explanation += f"其他影响T分期的因素：{', '.join(other_factors)}\n"
        
        return explanation
    
    def _explain_n_stage(self, params: Dict[str, Any], n_stage: str) -> str:
        """解释N分期"""
        staging_type = params.get("staging_type", "clinical")
        explanation = ""
        
        if not params.get("lymph_nodes_assessable", True):
            assessment_note = "手术采样不足" if staging_type == "pathologic" else "影像学无法评估"
            explanation += f"**NX**: 区域淋巴结无法评估（{assessment_note}）\n"
            return explanation
        
        # 获取淋巴结转移模式
        lymph_involvement = params.get("lymph_node_involvement", "no_nodes")
        
        # 描述具体的淋巴结转移情况
        lymph_descriptions = {
            "no_nodes": "无区域淋巴结转移",
            "ipsilateral_pulmonary_hilar": "同侧肺内、支气管周围淋巴结转移",
            "single_ipsilateral_mediastinal": "单个同侧纵隔或隆突下淋巴结转移",
            "multiple_ipsilateral_mediastinal": "多个同侧纵隔或隆突下淋巴结转移",
            "contralateral_nodes": "对侧纵隔或肺门淋巴结转移",
            "supraclavicular_scalene": "锁骨上或斜角肌淋巴结转移"
        }
        
        lymph_feature = lymph_descriptions.get(lymph_involvement, "未知转移模式")
        assessment_note = "（组织学检查）" if staging_type == "pathologic" else "（影像学判断）"
        explanation += f"淋巴结转移情况{assessment_note}：{lymph_feature}\n"
        
        # N分期结果映射
        n_explanations = {
            "N0": "无区域淋巴结转移",
            "N1": "同侧肺内、支气管周围或纵隔淋巴结转移",
            "N2a": "单个同侧纵隔或隆突下淋巴结转移",
            "N2b": "多个同侧纵隔或隆突下淋巴结转移",
            "N3": "对侧纵隔/肺门或斜角肌/锁骨上淋巴结转移"
        }
        
        # 病理分期时的特殊提示
        if staging_type == "pathologic" and lymph_involvement == "no_nodes":
            explanation += "注：病理分期建议检查至少10个淋巴结以获得准确的N分期\n"
        
        explanation += f"**{n_stage}**: {n_explanations.get(n_stage, '')}\n"
        return explanation
    
    def _explain_m_stage(self, params: Dict[str, Any], m_stage: str) -> str:
        """解释M分期"""
        staging_type = params.get("staging_type", "clinical")
        explanation = ""
        
        # 获取远处转移模式
        metastasis_pattern = params.get("distant_metastasis", "no_metastasis")
        
        # 描述具体的转移情况
        metastasis_descriptions = {
            "no_metastasis": "无远处转移",
            "contralateral_lung_nodules": "对侧肺结节",
            "malignant_pleural_effusion": "恶性胸膜积液或心包积液",
            "pleural_pericardial_nodules": "胸膜结节或心包结节",
            "pleural_implants": "胸膜种植",
            "single_organ_single_lesion": "单器官单发转移",
            "single_organ_multiple_lesions": "单器官多发转移",
            "multiple_organs_metastasis": "多器官转移"
        }
        
        metastasis_feature = metastasis_descriptions.get(metastasis_pattern, "未知转移模式")
        assessment_note = "（组织学确认）" if staging_type == "pathologic" and metastasis_pattern != "no_metastasis" else "（影像学判断）" if staging_type == "clinical" and metastasis_pattern != "no_metastasis" else ""
        explanation += f"转移情况{assessment_note}：{metastasis_feature}\n"
        
        # M分期结果映射
        m_explanations = {
            "M0": "无远处转移",
            "M1a": "对侧肺结节，或恶性胸膜/心包积液，或胸膜/心包结节，或胸膜种植",
            "M1b": "单器官单发转移",
            "M1c": "单器官多发转移或多器官多发转移"
        }
        
        # 病理分期时的特殊提示
        if staging_type == "pathologic" and metastasis_pattern not in ["no_metastasis"]:
            explanation += "注：病理分期时如切除转移灶需组织学确认\n"
        
        explanation += f"**{m_stage}**: {m_explanations.get(m_stage, '')}\n"
        return explanation
    
    
