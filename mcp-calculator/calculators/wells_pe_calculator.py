"""
Wells Criteria for Pulmonary Embolism Calculator
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


@register_calculator("wells_pe")
class WellsPECalculator(BaseCalculator):
    """Wells肺栓塞标准计算器实现"""
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=8,
            name="Wells Criteria for Pulmonary Embolism",
            category="pulmonology",
            description="Assess the probability of pulmonary embolism using Wells criteria",
            parameters=[
                Parameter(
                    name="clinical_dvt",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Clinical signs and symptoms of DVT"
                ),
                Parameter(
                    name="pe_number_one",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="PE is #1 diagnosis OR equally likely"
                ),
                Parameter(
                    name="heart_rate",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="bpm",
                    min_value=30,
                    max_value=250,
                    description="Heart rate in beats per minute"
                ),
                Parameter(
                    name="immobilization_for_3days",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Immobilization at least 3 days"
                ),
                Parameter(
                    name="surgery_in_past4weeks",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Surgery in the previous 4 weeks"
                ),
                Parameter(
                    name="previous_pe",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Previous objectively diagnosed PE"
                ),
                Parameter(
                    name="previous_dvt",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Previous objectively diagnosed DVT"
                ),
                Parameter(
                    name="hemoptysis",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Hemoptysis"
                ),
                Parameter(
                    name="malignancy_with_treatment",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Malignancy with treatment within 6 months or palliative"
                )
            ]
        )
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> ValidationResult:
        """验证参数"""
        errors = []

        # 心率为必填参数，且需在 30-250 bpm 范围内
        heart_rate = parameters.get("heart_rate", None)
        if heart_rate is None:
            errors.append("Missing required parameter: heart_rate")
        else:
            try:
                hr_value = float(heart_rate)
            except (TypeError, ValueError):
                errors.append("Invalid heart_rate, must be a number")
            else:
                if hr_value < 30 or hr_value > 250:
                    errors.append("Heart rate must be between 30 and 250 bpm")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )
    
    def calculate(self, parameters: Dict[str, Any]) -> CalculationResult:
        """执行计算"""
        # 直接从参数字典读取值（避免与基类 get_param_value 的签名不匹配问题）
        clinical_dvt = bool(parameters.get("clinical_dvt", False))
        pe_number_one = bool(parameters.get("pe_number_one", False))
        heart_rate = float(parameters.get("heart_rate"))
        immobilization_for_3days = bool(parameters.get("immobilization_for_3days", False))
        surgery_in_past4weeks = bool(parameters.get("surgery_in_past4weeks", False))
        previous_pe = bool(parameters.get("previous_pe", False))
        previous_dvt = bool(parameters.get("previous_dvt", False))
        hemoptysis = bool(parameters.get("hemoptysis", False))
        malignancy_with_treatment = bool(parameters.get("malignancy_with_treatment", False))
        
        # 计算Wells评分
        score = 0.0
        
        if clinical_dvt:
            score += 3.0
        
        if pe_number_one:
            score += 3.0
        
        if heart_rate > 100:
            score += 1.5
        
        if immobilization_for_3days or surgery_in_past4weeks:
            score += 1.5
        
        if previous_pe or previous_dvt:
            score += 1.5
        
        if hemoptysis:
            score += 1.0
        
        if malignancy_with_treatment:
            score += 1.0
        
        # 生成解释
        explanation = self._generate_explanation(
            clinical_dvt, pe_number_one, heart_rate, immobilization_for_3days,
            surgery_in_past4weeks, previous_pe, previous_dvt, hemoptysis,
            malignancy_with_treatment, score
        )
        
        return CalculationResult(
            value=score,
            unit="points",
            explanation=explanation,
            metadata={
                "clinical_dvt": clinical_dvt,
                "pe_number_one": pe_number_one,
                "heart_rate": heart_rate,
                "immobilization_or_surgery": immobilization_for_3days or surgery_in_past4weeks,
                "previous_pe_or_dvt": previous_pe or previous_dvt,
                "hemoptysis": hemoptysis,
                "malignancy_with_treatment": malignancy_with_treatment,
                "risk_category": self._get_risk_category(score)
            }
        )
    
    def _generate_explanation(self, clinical_dvt: bool, pe_number_one: bool, heart_rate: float,
                            immobilization_for_3days: bool, surgery_in_past4weeks: bool,
                            previous_pe: bool, previous_dvt: bool, hemoptysis: bool,
                            malignancy_with_treatment: bool, score: float) -> str:
        """生成计算解释"""
        explanation = """The criteria for the Wells' Criteria for Pulmonary Embolism score are listed below:

   1. Clinical signs and symptoms of DVT: No = 0 points, Yes = +3 points
   2. PE is #1 diagnosis OR equally likely: No = 0 points, Yes = +3 points
   3. Heart rate > 100: No = 0 points, Yes = +1.5 points
   4. Immobilization at least 3 days OR surgery in the previous 4 weeks: No = 0 points, Yes = +1.5 points
   5. Previous, objectively diagnosed PE or DVT: No = 0 points, Yes = +1.5 points
   6. Hemoptysis: No = 0 points, Yes = +1 point
   7. Malignancy with treatment within 6 months or palliative: No = 0 points, Yes = +1 point

The total score is calculated by summing the points for each criterion.\n\n"""
        
        explanation += "The Well's score for pulmonary embolism is currently 0.\n"
        
        current_score = 0.0
        
        # Clinical DVT
        if clinical_dvt:
            explanation += f"Clinical signs and symptoms of DVT are reported to be present and so three points are added to the score, making the current total {current_score} + 3 = {current_score + 3}. "
            current_score += 3
        else:
            explanation += f"Clinical signs and symptoms of DVT are reported to be absent and so the total score remains unchanged, keeping the total score at {current_score}. "
        
        # PE number one diagnosis
        if pe_number_one:
            explanation += f"Pulmonary Embolism is reported to be the #1 diagnosis or equally likely to be the #1 diagnosis and so we add 3 points to the score making the current total = {current_score} + 3 = {current_score + 3}.\n"
            current_score += 3
        else:
            explanation += f"Pulmonary Embolism is not reported to be the #1 diagnosis and so the total score remains unchanged, keeping the total score at {current_score}.\n"
        
        # Heart rate
        explanation += f"The patient's heart rate is {heart_rate} beats per minute. "
        if heart_rate > 100:
            explanation += f"The heart rate is more than 100 bpm, and so the score is increased by 1.5, making the total score, {current_score} + 1.5 = {current_score + 1.5}.\n"
            current_score += 1.5
        else:
            explanation += f"The heart rate is less than 100 bpm, and so the score remains unchanged, keeping the total score at {current_score}.\n"
        
        # Immobilization or surgery
        if not immobilization_for_3days and not surgery_in_past4weeks:
            explanation += f"Because the patient has not had an immobilization for at least 3 days, and the patient did not have a surgery in the past 4 weeks, the score remains at {current_score}.\n"
        elif not immobilization_for_3days and surgery_in_past4weeks:
            explanation += f"Because the patient did not have an immobilization for at least 3 days but the patient had a surgery in the past 4 weeks, the score increases to {current_score} + 1.5 = {current_score + 1.5}.\n"
            current_score += 1.5
        elif immobilization_for_3days and not surgery_in_past4weeks:
            explanation += f"Because the patient has had an immobilization for at least 3 days but the patient did not have a surgery in the past 4 weeks, the score increases to {current_score} + 1.5 = {current_score + 1.5}.\n"
            current_score += 1.5
        elif immobilization_for_3days and surgery_in_past4weeks:
            explanation += f"Because the patient has had an immobilization for at least 3 days and the patient had a surgery in the past 4 weeks, the score increases to {current_score} + 1.5 = {current_score + 1.5}.\n"
            current_score += 1.5
        
        # Previous PE or DVT
        if not previous_pe and not previous_dvt:
            explanation += f"Because the patient has no previous diagnosis of pulmonary embolism (PE) or deep vein thrombosis (DVT), the score remains at {current_score}.\n"
        elif not previous_pe and previous_dvt:
            explanation += f"The patient has not been diagnosed with pulmonary embolism (PE), but the patient has previously been diagnosed with deep vein thrombosis (DVT), we increase the current total by 1.5 so that {current_score} + 1.5 = {current_score + 1.5}.\n"
            current_score += 1.5
        elif previous_pe and not previous_dvt:
            explanation += f"Because the patient has been previously diagnosed for pulmonary embolism (PE), but the patient has never been diagnosed for deep vein thrombosis (DVT), we increase the current total by 1.5 so that {current_score} + 1.5 = {current_score + 1.5}.\n"
            current_score += 1.5
        elif previous_pe and previous_dvt:
            explanation += f"Because the patient has previously been diagnosed for pulmonary embolism (PE) and deep vein thrombosis (DVT), we increase the current total by 1.5 so that {current_score} + 1.5 = {current_score + 1.5}.\n"
            current_score += 1.5
        
        # Hemoptysis
        if hemoptysis:
            explanation += f"Hemoptysis is reported to be present and so one point is incremented to the score, making the current total {current_score} + 1 = {current_score + 1}.\n"
            current_score += 1
        else:
            explanation += f"Hemoptysis is reported to be absent and so the total score remains unchanged, keeping the total score at {current_score}.\n"
        
        # Malignancy
        if malignancy_with_treatment:
            explanation += f"Malignancy with treatment within 6 months or palliative is reported to be present and so one point is added to the score, making the total score {current_score} + 1 = {current_score + 1}.\n"
            current_score += 1
        else:
            explanation += f"Malignancy with treatment within 6 months or palliative is reported to be absent and so the total score remains unchanged, keeping the total score at {current_score}.\n"
        
        explanation += f"The patient's Well's score for pulmonary embolism is {score}."
        
        return explanation
    
    def _get_risk_category(self, score: float) -> str:
        """获取风险分类"""
        if score <= 4.0:
            return "Low probability"
        elif score <= 6.0:
            return "Moderate probability"
        else:
            return "High probability"
