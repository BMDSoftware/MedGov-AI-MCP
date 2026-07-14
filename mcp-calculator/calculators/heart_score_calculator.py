"""
HEART Score Calculator
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


@register_calculator("heart_score")
class HeartScoreCalculator(BaseCalculator):
    """HEART评分计算器实现"""
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=18,
            name="HEART Score",
            category="cardiology",
            description="Risk stratification in patients with chest pain using HEART Score",
            parameters=[
                Parameter(
                    name="history",
                    type=ParameterType.CHOICE,
                    required=False,
                    choices=["Slightly suspicious", "Moderately suspicious", "Highly suspicious"],
                    default="Slightly suspicious",
                    description="History suspicion level"
                ),
                Parameter(
                    name="electrocardiogram",
                    type=ParameterType.CHOICE,
                    required=False,
                    choices=["Normal", "Non-specific repolarization disturbance", "Significant ST deviation"],
                    default="Normal",
                    description="EKG findings"
                ),
                Parameter(
                    name="age",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="years",
                    min_value=0,
                    max_value=120,
                    description="Patient age in years"
                ),
                Parameter(
                    name="hypertension",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="History of hypertension"
                ),
                Parameter(
                    name="hypercholesterolemia",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="History of hypercholesterolemia"
                ),
                Parameter(
                    name="diabetes_mellitus",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="History of diabetes mellitus"
                ),
                Parameter(
                    name="obesity",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Obesity (BMI >30 kg/m²)"
                ),
                Parameter(
                    name="smoking",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Current smoking or cessation within 3 months"
                ),
                Parameter(
                    name="family_with_cvd",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Positive family history of cardiovascular disease before age 65"
                ),
                Parameter(
                    name="atherosclerotic_disease",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="History of atherosclerotic disease (prior MI, PCI/CABG, CVA/TIA, or peripheral arterial disease)"
                ),
                Parameter(
                    name="initial_troponin",
                    type=ParameterType.CHOICE,
                    required=False,
                    choices=["less than or equal to normal limit", "between the normal limit or up to three times the normal limit", "greater than three times normal limit"],
                    default="less than or equal to normal limit",
                    description="Initial troponin level"
                )
            ]
        )
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> ValidationResult:
        """验证参数"""
        errors = []
        
        # 验证年龄
        age = parameters.get("age")
        if age is None:
            errors.append("Age is required")
        elif not isinstance(age, (int, float)):
            errors.append("Age must be a number")
        elif age < 0 or age > 120:
            errors.append("Age must be between 0 and 120 years")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )
    
    def calculate(self, parameters: Dict[str, Any]) -> CalculationResult:
        """执行计算"""
        # 获取参数值
        history = parameters.get("history", "Slightly suspicious")
        electrocardiogram = parameters.get("electrocardiogram", "Normal")
        age = parameters.get("age")
        initial_troponin = parameters.get("initial_troponin", "less than or equal to normal limit")
        
        # 风险因素
        hypertension = parameters.get("hypertension", False)
        hypercholesterolemia = parameters.get("hypercholesterolemia", False)
        diabetes_mellitus = parameters.get("diabetes_mellitus", False)
        obesity = parameters.get("obesity", False)
        smoking = parameters.get("smoking", False)
        family_with_cvd = parameters.get("family_with_cvd", False)
        atherosclerotic_disease = parameters.get("atherosclerotic_disease", False)
        
        # 计算总分
        total_score = 0
        
        # 1. History (病史)
        history_scores = {
            "Slightly suspicious": 0,
            "Moderately suspicious": 1,
            "Highly suspicious": 2
        }
        total_score += history_scores[history]
        
        # 2. EKG (心电图)
        ekg_scores = {
            "Normal": 0,
            "Non-specific repolarization disturbance": 1,
            "Significant ST deviation": 2
        }
        total_score += ekg_scores[electrocardiogram]
        
        # 3. Age (年龄)
        if age < 45:
            age_score = 0
        elif 45 <= age < 65:
            age_score = 1
        else:  # age >= 65
            age_score = 2
        total_score += age_score
        
        # 4. Risk factors (风险因素)
        # atherosclerotic disease 单独计分：若存在则固定 +2，与其它风险因素数量无关
        # 其它风险因素：HTN, hypercholesterolemia, DM, obesity, smoking, family_with_cvd
        other_risk_factors = [hypertension, hypercholesterolemia, diabetes_mellitus, obesity, smoking, family_with_cvd]
        risk_factors_count = sum(other_risk_factors)
        if atherosclerotic_disease:
            risk_score = 2
        else:
            if risk_factors_count >= 3:
                risk_score = 2
            elif 1 <= risk_factors_count <= 2:
                risk_score = 1
            else:
                risk_score = 0
        total_score += risk_score
        
        # 5. Initial troponin (初始肌钙蛋白)
        troponin_scores = {
            "less than or equal to normal limit": 0,
            "between the normal limit or up to three times the normal limit": 1,
            "greater than three times normal limit": 2
        }
        total_score += troponin_scores[initial_troponin]
        
        # 生成解释
        explanation = self._generate_explanation(parameters, total_score)
        
        # 风险分层
        if total_score <= 3:
            risk_category = "Low risk"
        elif total_score <= 6:
            risk_category = "Moderate risk"
        else:
            risk_category = "High risk"
        
        return CalculationResult(
            value=total_score,
            unit="points",
            explanation=explanation,
            metadata={
                "risk_category": risk_category,
                "component_scores": {
                    "history": history_scores[history],
                    "electrocardiogram": ekg_scores[electrocardiogram],
                    "age": age_score,
                    "risk_factors": risk_score,
                    "initial_troponin": troponin_scores[initial_troponin]
                },
                "risk_factors_count": risk_factors_count,
                "atherosclerotic_disease": atherosclerotic_disease,
                "formula": "HEART Score = History + EKG + Age + Risk factors + Troponin"
            }
        )
    
    def _generate_explanation(self, parameters: Dict[str, Any], total_score: int) -> str:
        """生成计算解释"""
        explanation = "The HEART Score for risk stratification in patients with chest pain is shown below:\n\n"
        explanation += "1. History: Slightly suspicious = 0 points, Moderately suspicious = +1 point, Highly suspicious = +2 points\n"
        explanation += "2. EKG: Normal = 0 points, Non-specific repolarization disturbance = +1 point, Significant ST deviation = +2 points\n"
        explanation += "3. Age: <45 years = 0 points, 45-64 years = +1 point, ≥65 years = +2 points\n"
        explanation += "4. Risk factors (HTN, hypercholesterolemia, DM, obesity (BMI >30 kg/m²), smoking (current or cessation within 3 months), positive family history of cardiovascular disease before age 65): No known risk factors = 0 points, 1-2 risk factors = +1 point, ≥3 risk factors = +2 points. History of atherosclerotic disease (prior MI, PCI/CABG, CVA/TIA, or peripheral arterial disease) = +2 points irrespective of the number of other risk factors.\n"
        explanation += "5. Initial troponin level: ≤normal limit = 0 points, 1–3× normal limit = +1 point, >3× normal limit = +2 points\n\n"
        explanation += "The total score is calculated by summing the points for each criterion.\n\n"
        
        current_score = 0
        explanation += f"The current HEART Score is {current_score}.\n"
        
        # 获取参数值
        history = parameters.get("history", "Slightly suspicious")
        electrocardiogram = parameters.get("electrocardiogram", "Normal")
        age = parameters.get("age")
        initial_troponin = parameters.get("initial_troponin", "less than or equal to normal limit")
        
        # 风险因素
        hypertension = parameters.get("hypertension", False)
        hypercholesterolemia = parameters.get("hypercholesterolemia", False)
        diabetes_mellitus = parameters.get("diabetes_mellitus", False)
        obesity = parameters.get("obesity", False)
        smoking = parameters.get("smoking", False)
        family_with_cvd = parameters.get("family_with_cvd", False)
        atherosclerotic_disease = parameters.get("atherosclerotic_disease", False)
        
        # 1. History
        explanation += f"The value of 'history' in the patient's note is determined to be '{history}'. "
        history_scores = {"Slightly suspicious": 0, "Moderately suspicious": 1, "Highly suspicious": 2}
        points = history_scores[history]
        if points == 0:
            explanation += f"Based on the HEART Score criteria, 0 points are added for 'history', keeping the current total at {current_score}.\n"
        elif points == 1:
            explanation += f"Based on the HEART Score criteria, 1 point is added for 'history', increasing the current total to {current_score} + 1 = {current_score + 1}.\n"
            current_score += 1
        else:
            explanation += f"Based on the HEART Score criteria, 2 points are added for 'history', increasing the current total to {current_score} + 2 = {current_score + 2}.\n"
            current_score += 2
        
        # 2. EKG
        explanation += f"The value of 'electrocardiogram' in the patient's note is determined to be '{electrocardiogram}'. "
        ekg_scores = {"Normal": 0, "Non-specific repolarization disturbance": 1, "Significant ST deviation": 2}
        points = ekg_scores[electrocardiogram]
        if points == 0:
            explanation += f"Based on the HEART Score criteria, 0 points are added for 'electrocardiogram', keeping the current total at {current_score}.\n"
        elif points == 1:
            explanation += f"Based on the HEART Score criteria, 1 point is added for 'electrocardiogram', increasing the current total to {current_score} + 1 = {current_score + 1}.\n"
            current_score += 1
        else:
            explanation += f"Based on the HEART Score criteria, 2 points are added for 'electrocardiogram', increasing the current total to {current_score} + 2 = {current_score + 2}.\n"
            current_score += 2
        
        # 3. Age
        explanation += f"The patient's age is {age} years. "
        if age < 45:
            explanation += f"The patient's age is less than 45 years and so keep the current total at {current_score}.\n"
        elif 45 <= age < 65:
            explanation += f"The patient's age is between 45 and 65 years and so we increment the current total by 1, making the current total {current_score} + 1 = {current_score + 1}.\n"
            current_score += 1
        else:
            explanation += f"The patient's age is greater than 65 years and so we increment the current total by 2, making the current total {current_score} + 2 = {current_score + 2}.\n"
            current_score += 2
        
        # 4. Risk factors
        # atherosclerotic disease 单独计分：若存在则固定 +2，与其它风险因素数量无关
        other_risk_factors = [hypertension, hypercholesterolemia, diabetes_mellitus, obesity, smoking, family_with_cvd]
        risk_factors_count = sum(other_risk_factors)
        
        present_factors = []
        if hypertension: present_factors.append("hypertension")
        if hypercholesterolemia: present_factors.append("hypercholesterolemia")
        if diabetes_mellitus: present_factors.append("diabetes mellitus")
        if obesity: present_factors.append("obesity")
        if smoking: present_factors.append("smoking")
        if family_with_cvd: present_factors.append("family with cvd")
        if atherosclerotic_disease: present_factors.append("atherosclerotic disease")
        
        if present_factors:
            explanation += f"The following risk factor(s) are present based on the patient's note: {', '.join(present_factors)}. "
        
        if atherosclerotic_disease:
            explanation += f"Based on the HEART Score criteria, history of atherosclerotic disease gives +2 points irrespective of the number of other risk factors, making the current total {current_score} + 2 = {current_score + 2}.\n"
            current_score += 2
        else:
            explanation += f"Based on the HEART Score risk factors criteria, {risk_factors_count} risk factors are present and so "
            if risk_factors_count >= 3:
                explanation += f"2 points are added as 3 or more risk factors are present, making the current total {current_score} + 2 = {current_score + 2}.\n"
                current_score += 2
            elif 1 <= risk_factors_count <= 2:
                explanation += f"1 point is added for the risk factors criteria, making the current total, {current_score} + 1 = {current_score + 1}.\n"
                current_score += 1
            else:
                explanation += f"0 points are added for the risk factors criteria, keeping the current total at {current_score}.\n"
        
        # 5. Initial troponin
        explanation += f"The value of 'initial troponin' in the patient's note is determined to be '{initial_troponin}'. "
        troponin_scores = {
            "less than or equal to normal limit": 0,
            "between the normal limit or up to three times the normal limit": 1,
            "greater than three times normal limit": 2
        }
        points = troponin_scores[initial_troponin]
        if points == 0:
            explanation += f"Based on the HEART Score criteria, 0 points are added for 'initial troponin', keeping the current total at {current_score}.\n"
        elif points == 1:
            explanation += f"Based on the HEART Score criteria, 1 point is added for 'initial troponin', increasing the current total to {current_score} + 1 = {current_score + 1}.\n"
            current_score += 1
        else:
            explanation += f"Based on the HEART Score criteria, 2 points are added for 'initial troponin', increasing the current total to {current_score} + 2 = {current_score + 2}.\n"
            current_score += 2
        
        explanation += f"Based on the patient's data, the HEART Score is {total_score}."
        
        return explanation
