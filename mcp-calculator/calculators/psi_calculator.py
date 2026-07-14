"""
PSI (Pneumonia Severity Index) Calculator
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


@register_calculator("psi")
class PSICalculator(BaseCalculator):
    """PSI肺炎严重程度指数计算器实现"""
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=29,
            name="Pneumonia Severity Index (PSI)",
            category="pulmonology",
            description="Pneumonia severity assessment for community-acquired pneumonia risk stratification",
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
                    name="sex",
                    type=ParameterType.CHOICE,
                    required=True,
                    choices=["Male", "Female"],
                    description="Patient sex"
                ),
                Parameter(
                    name="nursing_home_resident",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Nursing home resident"
                ),
                Parameter(
                    name="neoplastic_disease",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="History of neoplastic disease"
                ),
                Parameter(
                    name="liver_disease",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="History of liver disease"
                ),
                Parameter(
                    name="chf",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="History of congestive heart failure"
                ),
                Parameter(
                    name="cerebrovascular_disease",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="History of cerebrovascular disease"
                ),
                Parameter(
                    name="renal_disease",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="History of renal disease"
                ),
                Parameter(
                    name="altered_mental_status",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Altered mental status"
                ),
                Parameter(
                    name="respiratory_rate",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="breaths/min",
                    min_value=5,
                    max_value=80,
                    description="Respiratory rate in breaths per minute"
                ),
                Parameter(
                    name="systolic_bp",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="mmHg",
                    min_value=30,
                    max_value=300,
                    description="Systolic blood pressure in mmHg"
                ),
                Parameter(
                    name="temperature",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="°C",
                    min_value=25,
                    max_value=45,
                    description="Body temperature in Celsius"
                ),
                Parameter(
                    name="heart_rate",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="bpm",
                    min_value=20,
                    max_value=250,
                    description="Heart rate in beats per minute"
                ),
                Parameter(
                    name="ph",
                    type=ParameterType.NUMERIC,
                    required=True,
                    min_value=6.5,
                    max_value=8.0,
                    description="Arterial pH"
                ),
                Parameter(
                    name="bun",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="mg/dL",
                    min_value=1,
                    max_value=200,
                    description="Blood urea nitrogen in mg/dL"
                ),
                Parameter(
                    name="sodium",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="mmol/L",
                    min_value=100,
                    max_value=200,
                    description="Serum sodium in mmol/L"
                ),
                Parameter(
                    name="glucose",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="mg/dL",
                    min_value=30,
                    max_value=800,
                    description="Serum glucose in mg/dL"
                ),
                Parameter(
                    name="hematocrit",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="%",
                    min_value=10,
                    max_value=70,
                    description="Hematocrit percentage"
                ),
                Parameter(
                    name="pao2",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="mmHg",
                    min_value=20,
                    max_value=500,
                    description="Partial pressure of oxygen in mmHg"
                ),
                Parameter(
                    name="pleural_effusion",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Pleural effusion on chest X-ray"
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
        
        # 验证数值范围
        for param_name, value in parameters.items():
            if param_name in param_defs:
                param_def = param_defs[param_name]
                if param_def.type == ParameterType.NUMERIC and value is not None:
                    try:
                        numeric_value = float(value)
                        if param_def.min_value is not None and numeric_value < param_def.min_value:
                            errors.append(f"Parameter {param_name}: value {numeric_value} is below minimum {param_def.min_value}")
                        if param_def.max_value is not None and numeric_value > param_def.max_value:
                            errors.append(f"Parameter {param_name}: value {numeric_value} is above maximum {param_def.max_value}")
                    except (ValueError, TypeError):
                        errors.append(f"Parameter {param_name}: invalid numeric value {value}")
                elif param_def.type == ParameterType.CHOICE and value is not None:
                    if value not in param_def.choices:
                        errors.append(f"Parameter {param_name}: value '{value}' is not in allowed choices {param_def.choices}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )
    
    def calculate(self, parameters: Dict[str, Any]) -> CalculationResult:
        """计算PSI评分"""
        
        # 获取参数值
        age = parameters["age"]
        sex = parameters["sex"]
        nursing_home_resident = parameters.get("nursing_home_resident", False)
        neoplastic_disease = parameters.get("neoplastic_disease", False)
        liver_disease = parameters.get("liver_disease", False)
        chf = parameters.get("chf", False)
        cerebrovascular_disease = parameters.get("cerebrovascular_disease", False)
        renal_disease = parameters.get("renal_disease", False)
        altered_mental_status = parameters.get("altered_mental_status", False)
        respiratory_rate = parameters["respiratory_rate"]
        systolic_bp = parameters["systolic_bp"]
        temperature = parameters["temperature"]
        heart_rate = parameters["heart_rate"]
        ph = parameters["ph"]
        bun = parameters["bun"]
        sodium = parameters["sodium"]
        glucose = parameters["glucose"]
        hematocrit = parameters["hematocrit"]
        pao2 = parameters["pao2"]
        pleural_effusion = parameters.get("pleural_effusion", False)
        
        score = 0
        explanation_parts = []
        
        # 1. 年龄评分（年龄即分数）
        score += age
        explanation_parts.append(f"Age {age} years: +{age} points")
        
        # 2. 性别评分
        if sex == "Female":
            score -= 10
            explanation_parts.append("Female sex: -10 points")
        else:
            explanation_parts.append("Male sex: 0 points")
        
        # 3. 护理院居民
        if nursing_home_resident:
            score += 10
            explanation_parts.append("Nursing home resident: +10 points")
        
        # 4. 肿瘤疾病史
        if neoplastic_disease:
            score += 30
            explanation_parts.append("Neoplastic disease: +30 points")
        
        # 5. 肝病史
        if liver_disease:
            score += 20
            explanation_parts.append("Liver disease: +20 points")
        
        # 6. 充血性心力衰竭史
        if chf:
            score += 10
            explanation_parts.append("Congestive heart failure: +10 points")
        
        # 7. 脑血管疾病史
        if cerebrovascular_disease:
            score += 10
            explanation_parts.append("Cerebrovascular disease: +10 points")
        
        # 8. 肾病史
        if renal_disease:
            score += 10
            explanation_parts.append("Renal disease: +10 points")
        
        # 9. 精神状态改变
        if altered_mental_status:
            score += 20
            explanation_parts.append("Altered mental status: +20 points")
        
        # 10. 呼吸频率
        if respiratory_rate >= 30:
            score += 20
            explanation_parts.append(f"Respiratory rate {respiratory_rate} ≥30 breaths/min: +20 points")
        else:
            explanation_parts.append(f"Respiratory rate {respiratory_rate} <30 breaths/min: 0 points")
        
        # 11. 收缩压
        if systolic_bp < 90:
            score += 20
            explanation_parts.append(f"Systolic BP {systolic_bp} <90 mmHg: +20 points")
        else:
            explanation_parts.append(f"Systolic BP {systolic_bp} ≥90 mmHg: 0 points")
        
        # 12. 体温
        if temperature < 35 or temperature > 39.9:
            score += 15
            explanation_parts.append(f"Temperature {temperature}°C (<35°C or >39.9°C): +15 points")
        else:
            explanation_parts.append(f"Temperature {temperature}°C (35-39.9°C): 0 points")
        
        # 13. 心率
        if heart_rate >= 125:
            score += 10
            explanation_parts.append(f"Heart rate {heart_rate} ≥125 bpm: +10 points")
        else:
            explanation_parts.append(f"Heart rate {heart_rate} <125 bpm: 0 points")
        
        # 14. pH
        if ph < 7.35:
            score += 30
            explanation_parts.append(f"pH {ph} <7.35: +30 points")
        else:
            explanation_parts.append(f"pH {ph} ≥7.35: 0 points")
        
        # 15. BUN
        if bun >= 30:
            score += 20
            explanation_parts.append(f"BUN {bun} ≥30 mg/dL: +20 points")
        else:
            explanation_parts.append(f"BUN {bun} <30 mg/dL: 0 points")
        
        # 16. 钠
        if sodium < 130:
            score += 20
            explanation_parts.append(f"Sodium {sodium} <130 mmol/L: +20 points")
        else:
            explanation_parts.append(f"Sodium {sodium} ≥130 mmol/L: 0 points")
        
        # 17. 葡萄糖
        if glucose >= 250:
            score += 10
            explanation_parts.append(f"Glucose {glucose} ≥250 mg/dL: +10 points")
        else:
            explanation_parts.append(f"Glucose {glucose} <250 mg/dL: 0 points")
        
        # 18. 血细胞比容
        if hematocrit < 30:
            score += 10
            explanation_parts.append(f"Hematocrit {hematocrit}% <30%: +10 points")
        else:
            explanation_parts.append(f"Hematocrit {hematocrit}% ≥30%: 0 points")
        
        # 19. 氧分压
        if pao2 < 60:
            score += 10
            explanation_parts.append(f"PaO2 {pao2} <60 mmHg: +10 points")
        else:
            explanation_parts.append(f"PaO2 {pao2} ≥60 mmHg: 0 points")
        
        # 20. 胸腔积液
        if pleural_effusion:
            score += 10
            explanation_parts.append("Pleural effusion on X-ray: +10 points")
        
        # 生成解释
        explanation = "PSI (Pneumonia Severity Index) calculation:\n\n"
        explanation += "\n".join([f"• {part}" for part in explanation_parts])
        explanation += f"\n\nTotal PSI Score: {score} points"
        
        # 添加风险分层
        if score <= 70:
            risk_class = "Class I"
            mortality_risk = "<0.1%"
            recommendation = "Outpatient treatment"
        elif score <= 85:
            risk_class = "Class II"
            mortality_risk = "0.1-0.4%"
            recommendation = "Outpatient treatment"
        elif score <= 130:
            risk_class = "Class III"
            mortality_risk = "0.4-0.9%"
            recommendation = "Brief inpatient observation or outpatient treatment"
        elif score <= 170:
            risk_class = "Class IV"
            mortality_risk = "0.9-2.8%"
            recommendation = "Inpatient treatment"
        else:
            risk_class = "Class V"
            mortality_risk = "2.8-8.2%"
            recommendation = "Inpatient treatment"
        
        explanation += f"\n\nRisk Classification: {risk_class}"
        explanation += f"\n30-day Mortality Risk: {mortality_risk}"
        explanation += f"\nRecommendation: {recommendation}"
        
        return CalculationResult(
            value=score,
            unit="points",
            explanation=explanation,
            metadata={
                "risk_class": risk_class,
                "mortality_risk": mortality_risk,
                "recommendation": recommendation,
                "age_points": age,
                "sex_points": -10 if sex == "Female" else 0,
                "comorbidity_points": (
                    (10 if nursing_home_resident else 0) +
                    (30 if neoplastic_disease else 0) +
                    (20 if liver_disease else 0) +
                    (10 if chf else 0) +
                    (10 if cerebrovascular_disease else 0) +
                    (10 if renal_disease else 0)
                ),
                "physical_exam_points": (
                    (20 if altered_mental_status else 0) +
                    (20 if respiratory_rate >= 30 else 0) +
                    (20 if systolic_bp < 90 else 0) +
                    (15 if temperature < 35 or temperature > 39.9 else 0) +
                    (10 if heart_rate >= 125 else 0)
                ),
                "laboratory_points": (
                    (30 if ph < 7.35 else 0) +
                    (20 if bun >= 30 else 0) +
                    (20 if sodium < 130 else 0) +
                    (10 if glucose >= 250 else 0) +
                    (10 if hematocrit < 30 else 0) +
                    (10 if pao2 < 60 else 0) +
                    (10 if pleural_effusion else 0)
                )
            }
        )
