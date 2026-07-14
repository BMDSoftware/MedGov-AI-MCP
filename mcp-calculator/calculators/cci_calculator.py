"""
CCI (Charlson Comorbidity Index) Calculator
"""

from typing import Dict, Any
from medcalc import (
    BaseCalculator, 
    CalculatorInfo, 
    Parameter, 
    ParameterType, 
    ValidationResult, 
    CalculationResult,
    register_calculator
)
from medcalc.utils import round_number


@register_calculator("cci")
class CCICalculator(BaseCalculator):
    """Charlson合并症指数计算器实现"""
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=32,
            name="Charlson Comorbidity Index (CCI)",
            category="critical_care",
            description="Charlson Comorbidity Index for predicting 10-year survival based on age and comorbidities",
            parameters=[
                Parameter(
                    name="age",
                    type=ParameterType.NUMERIC,
                    required=True,
                    min_value=0,
                    max_value=120,
                    description="Patient age in years"
                ),
                Parameter(
                    name="mi",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Myocardial infarction history"
                ),
                Parameter(
                    name="chf",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Congestive heart failure"
                ),
                Parameter(
                    name="peripheral_vascular_disease",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Peripheral vascular disease"
                ),
                Parameter(
                    name="cva",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Cerebrovascular accident"
                ),
                Parameter(
                    name="tia",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Transient ischemic attack"
                ),
                Parameter(
                    name="dementia",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Dementia"
                ),
                Parameter(
                    name="copd",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Chronic obstructive pulmonary disease"
                ),
                Parameter(
                    name="connective_tissue_disease",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Connective tissue disease"
                ),
                Parameter(
                    name="peptic_ulcer_disease",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Peptic ulcer disease"
                ),
                Parameter(
                    name="liver_disease",
                    type=ParameterType.CHOICE,
                    required=False,
                    choices=["none", "mild", "moderate_to_severe"],
                    default="none",
                    description="Liver disease severity (none, mild, moderate_to_severe)"
                ),
                Parameter(
                    name="diabetes_mellitus",
                    type=ParameterType.CHOICE,
                    required=False,
                    choices=["none", "uncomplicated", "end_organ_damage"],
                    default="none",
                    description="Diabetes mellitus severity (none, uncomplicated, end_organ_damage)"
                ),
                Parameter(
                    name="hemiplegia",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Hemiplegia"
                ),
                Parameter(
                    name="moderate_to_severe_ckd",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Moderate to severe chronic kidney disease"
                ),
                Parameter(
                    name="solid_tumor",
                    type=ParameterType.CHOICE,
                    required=False,
                    choices=["none", "localized", "metastatic"],
                    default="none",
                    description="Solid tumor status (none, localized, metastatic)"
                ),
                Parameter(
                    name="leukemia",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Leukemia"
                ),
                Parameter(
                    name="lymphoma",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Lymphoma"
                ),
                Parameter(
                    name="aids",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="AIDS"
                )
            ]
        )
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> ValidationResult:
        """验证参数"""
        errors = []
        
        # 获取参数定义
        param_defs = {p.name: p for p in self.get_info().parameters}
        
        # 检查必需参数
        for param_name, param_def in param_defs.items():
            if param_def.required and param_name not in parameters:
                errors.append(f"Missing required parameter: {param_name}")
        
        if errors:
            return ValidationResult(is_valid=False, errors=errors)
        
        # 验证年龄参数
        if "age" in parameters:
            age = parameters["age"]
            if not isinstance(age, (int, float)):
                errors.append("Age must be a number")
            elif age < 0 or age > 120:
                errors.append("Age must be between 0 and 120 years")
        
        # 验证布尔参数
        boolean_params = [
            "mi", "chf", "peripheral_vascular_disease", "cva", "tia", "dementia", 
            "copd", "connective_tissue_disease", "peptic_ulcer_disease", 
            "hemiplegia", "moderate_to_severe_ckd", "leukemia", "lymphoma", "aids"
        ]
        for param in boolean_params:
            if param in parameters and not isinstance(parameters[param], bool):
                errors.append(f"{param} must be a boolean value")
        
        # 验证选择参数
        choice_params = {
            "liver_disease": ["none", "mild", "moderate_to_severe"],
            "diabetes_mellitus": ["none", "uncomplicated", "end_organ_damage"],
            "solid_tumor": ["none", "localized", "metastatic"]
        }
        for param, valid_choices in choice_params.items():
            if param in parameters and parameters[param] not in valid_choices:
                errors.append(f"{param} must be one of: {', '.join(valid_choices)}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )
    
    def calculate(self, parameters: Dict[str, Any]) -> CalculationResult:
        """计算CCI评分"""
        
        # 直接从参数字典获取值
        age = parameters.get("age")
        mi = parameters.get("mi", False)
        chf = parameters.get("chf", False)
        peripheral_vascular_disease = parameters.get("peripheral_vascular_disease", False)
        cva = parameters.get("cva", False)
        tia = parameters.get("tia", False)
        dementia = parameters.get("dementia", False)
        copd = parameters.get("copd", False)
        connective_tissue_disease = parameters.get("connective_tissue_disease", False)
        peptic_ulcer_disease = parameters.get("peptic_ulcer_disease", False)
        liver_disease = parameters.get("liver_disease", "none")
        diabetes_mellitus = parameters.get("diabetes_mellitus", "none")
        hemiplegia = parameters.get("hemiplegia", False)
        moderate_to_severe_ckd = parameters.get("moderate_to_severe_ckd", False)
        solid_tumor = parameters.get("solid_tumor", "none")
        leukemia = parameters.get("leukemia", False)
        lymphoma = parameters.get("lymphoma", False)
        aids = parameters.get("aids", False)
        
        score = 0
        explanation_parts = []
        
        # 1. 年龄评分
        if age < 50:
            age_points = 0
        elif 50 <= age < 60:
            age_points = 1
        elif 60 <= age < 70:
            age_points = 2
        elif 70 <= age < 80:
            age_points = 3
        else:  # >= 80
            age_points = 4
        
        score += age_points
        explanation_parts.append(f"Age {age} years: +{age_points} points")
        
        # 2. 心肌梗死史 (1分)
        if mi:
            score += 1
            explanation_parts.append("Myocardial infarction: +1 point")
        
        # 3. 充血性心力衰竭 (1分)
        if chf:
            score += 1
            explanation_parts.append("Congestive heart failure: +1 point")
        
        # 4. 外周血管疾病 (1分)
        if peripheral_vascular_disease:
            score += 1
            explanation_parts.append("Peripheral vascular disease: +1 point")
        
        # 5. 脑血管疾病 (CVA或TIA，1分)
        if cva or tia:
            score += 1
            cerebrovascular_type = []
            if cva:
                cerebrovascular_type.append("CVA")
            if tia:
                cerebrovascular_type.append("TIA")
            explanation_parts.append(f"Cerebrovascular disease ({'/'.join(cerebrovascular_type)}): +1 point")
        
        # 6. 痴呆 (1分)
        if dementia:
            score += 1
            explanation_parts.append("Dementia: +1 point")
        
        # 7. 慢性阻塞性肺病 (1分)
        if copd:
            score += 1
            explanation_parts.append("Chronic obstructive pulmonary disease: +1 point")
        
        # 8. 结缔组织疾病 (1分)
        if connective_tissue_disease:
            score += 1
            explanation_parts.append("Connective tissue disease: +1 point")
        
        # 9. 消化性溃疡病 (1分)
        if peptic_ulcer_disease:
            score += 1
            explanation_parts.append("Peptic ulcer disease: +1 point")
        
        # 10. 肝病
        if liver_disease == "mild":
            score += 1
            explanation_parts.append("Liver disease (mild): +1 point")
        elif liver_disease == "moderate_to_severe":
            score += 3
            explanation_parts.append("Liver disease (moderate to severe): +3 points")
        
        # 11. 糖尿病
        if diabetes_mellitus == "uncomplicated":
            score += 1
            explanation_parts.append("Diabetes mellitus (uncomplicated): +1 point")
        elif diabetes_mellitus == "end_organ_damage":
            score += 2
            explanation_parts.append("Diabetes mellitus (end-organ damage): +2 points")
        
        # 12. 偏瘫 (2分)
        if hemiplegia:
            score += 2
            explanation_parts.append("Hemiplegia: +2 points")
        
        # 13. 中重度慢性肾病 (2分)
        if moderate_to_severe_ckd:
            score += 2
            explanation_parts.append("Moderate to severe chronic kidney disease: +2 points")
        
        # 14. 实体瘤
        if solid_tumor == "localized":
            score += 2
            explanation_parts.append("Solid tumor (localized): +2 points")
        elif solid_tumor == "metastatic":
            score += 6
            explanation_parts.append("Solid tumor (metastatic): +6 points")
        
        # 15. 白血病 (2分)
        if leukemia:
            score += 2
            explanation_parts.append("Leukemia: +2 points")
        
        # 16. 淋巴瘤 (2分)
        if lymphoma:
            score += 2
            explanation_parts.append("Lymphoma: +2 points")
        
        # 17. AIDS (6分)
        if aids:
            score += 6
            explanation_parts.append("AIDS: +6 points")
        
        # 生成解释
        explanation = "Charlson Comorbidity Index (CCI) calculation:\n\n"
        explanation += "\n".join([f"• {part}" for part in explanation_parts])
        explanation += f"\n\nTotal CCI Score: {score} points"
        
        # 添加10年生存率预测
        if score == 0:
            ten_year_survival = "98%"
        elif score == 1:
            ten_year_survival = "96%"
        elif score == 2:
            ten_year_survival = "90%"
        elif score == 3:
            ten_year_survival = "77%"
        elif score == 4:
            ten_year_survival = "53%"
        elif score == 5:
            ten_year_survival = "21%"
        else:  # >= 6
            ten_year_survival = "2%"
        
        explanation += f"\n\nPredicted 10-year survival: {ten_year_survival}"
        
        return CalculationResult(
            value=score,
            unit="points",
            explanation=explanation,
            metadata={
                "age_points": age_points,
                "ten_year_survival": ten_year_survival,
                "comorbidity_breakdown": {
                    "cardiovascular": (
                        (1 if mi else 0) +
                        (1 if chf else 0) +
                        (1 if peripheral_vascular_disease else 0) +
                        (1 if cva or tia else 0)
                    ),
                    "neurological": (
                        (1 if dementia else 0) +
                        (2 if hemiplegia else 0)
                    ),
                    "pulmonary": (1 if copd else 0),
                    "gastrointestinal": (
                        (1 if peptic_ulcer_disease else 0) +
                        (1 if liver_disease == "mild" else 0) +
                        (3 if liver_disease == "moderate_to_severe" else 0)
                    ),
                    "endocrine": (
                        (1 if diabetes_mellitus == "uncomplicated" else 0) +
                        (2 if diabetes_mellitus == "end_organ_damage" else 0)
                    ),
                    "renal": (2 if moderate_to_severe_ckd else 0),
                    "malignancy": (
                        (2 if solid_tumor == "localized" else 0) +
                        (6 if solid_tumor == "metastatic" else 0) +
                        (2 if leukemia else 0) +
                        (2 if lymphoma else 0)
                    ),
                    "immunological": (
                        (1 if connective_tissue_disease else 0) +
                        (6 if aids else 0)
                    )
                }
            }
        )
