"""
Revised Cardiac Risk Index Calculator
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


@register_calculator("cardiac_risk_index")
class CardiacRiskIndexCalculator(BaseCalculator):
    """修订心脏风险指数计算器实现"""
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=17,
            name="Revised Cardiac Risk Index (RCRI)",
            category="cardiology",
            description="Assess perioperative cardiac event risk using the Revised Cardiac Risk Index",
            parameters=[
                Parameter(
                    name="elevated_risk_surgery",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Elevated-risk surgery (intraperitoneal, intrathoracic, or suprainguinal vascular)"
                ),
                Parameter(
                    name="ischemic_heart_disease",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="History of ischemic heart disease"
                ),
                Parameter(
                    name="congestive_heart_failure",
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
                    description="History of cerebrovascular disease (prior TIA or stroke)"
                ),
                Parameter(
                    name="pre_operative_insulin_treatment",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Pre-operative treatment with insulin"
                ),
                Parameter(
                    name="pre_operative_creatinine",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="mg/dL",
                    min_value=0.1,
                    max_value=20.0,
                    description="Pre-operative creatinine level in mg/dL"
                )
            ]
        )
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> ValidationResult:
        """验证参数"""
        errors = []
        
        # 验证肌酐值
        creatinine = parameters.get("pre_operative_creatinine")
        if creatinine is not None:
            if creatinine < 0.1 or creatinine > 20.0:
                errors.append("Pre-operative creatinine must be between 0.1 and 20.0 mg/dL")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )
    
    def calculate(self, parameters: Dict[str, Any]) -> CalculationResult:
        """执行计算"""
        # 获取所有参数值
        elevated_risk_surgery = parameters.get("elevated_risk_surgery", False)
        ischemic_heart_disease = parameters.get("ischemic_heart_disease", False)
        congestive_heart_failure = parameters.get("congestive_heart_failure", False)
        cerebrovascular_disease = parameters.get("cerebrovascular_disease", False)
        pre_operative_insulin_treatment = parameters.get("pre_operative_insulin_treatment", False)
        pre_operative_creatinine = parameters.get("pre_operative_creatinine")
        
        # 计算总分
        score = 0
        
        # 每个布尔标准加1分
        if elevated_risk_surgery:
            score += 1
        if ischemic_heart_disease:
            score += 1
        if congestive_heart_failure:
            score += 1
        if cerebrovascular_disease:
            score += 1
        if pre_operative_insulin_treatment:
            score += 1
        
        # 术前肌酐>2 mg/dL加1分
        if pre_operative_creatinine > 2.0:
            score += 1
        
        # 生成解释
        explanation = self._generate_explanation(parameters, score)
        
        # 风险分层
        if score == 0:
            risk_category = "Class I (0.4% risk)"
        elif score == 1:
            risk_category = "Class II (0.9% risk)"
        elif score == 2:
            risk_category = "Class III (6.6% risk)"
        else:
            risk_category = "Class IV (≥11% risk)"
        
        return CalculationResult(
            value=score,
            unit="points",
            explanation=explanation,
            metadata={
                "risk_category": risk_category,
                "criteria_met": self._get_criteria_met(parameters),
                "formula": "RCRI Score = Sum of applicable risk factors"
            }
        )
    
    def _get_criteria_met(self, parameters: Dict[str, Any]) -> Dict[str, bool]:
        """获取满足的标准"""
        pre_operative_creatinine = parameters.get("pre_operative_creatinine")
        
        return {
            "elevated_risk_surgery": parameters.get("elevated_risk_surgery", False),
            "ischemic_heart_disease": parameters.get("ischemic_heart_disease", False),
            "congestive_heart_failure": parameters.get("congestive_heart_failure", False),
            "cerebrovascular_disease": parameters.get("cerebrovascular_disease", False),
            "pre_operative_insulin_treatment": parameters.get("pre_operative_insulin_treatment", False),
            "elevated_creatinine": pre_operative_creatinine > 2.0 if pre_operative_creatinine else False
        }
    
    def _generate_explanation(self, parameters: Dict[str, Any], score: int) -> str:
        """生成计算解释"""
        explanation = "The criteria for the Revised Cardiac Risk Index (RCRI) are listed below:\n\n"
        explanation += "1. Elevated-risk surgery (intraperitoneal, intrathoracic, or suprainguinal vascular): No = 0 points, Yes = +1 point\n"
        explanation += "2. History of ischemic heart disease (history of myocardial infarction, positive exercise test, current chest pain due to myocardial ischemia, use of nitrate therapy, or ECG with pathological Q waves): No = 0 points, Yes = +1 point\n"
        explanation += "3. History of congestive heart failure (pulmonary edema, bilateral rales or S3 gallop, paroxysmal nocturnal dyspnea, or chest x-ray showing pulmonary vascular redistribution): No = 0 points, Yes = +1 point\n"
        explanation += "4. History of cerebrovascular disease (prior transient ischemic attack or stroke): No = 0 points, Yes = +1 point\n"
        explanation += "5. Pre-operative treatment with insulin: No = 0 points, Yes = +1 point\n"
        explanation += "6. Pre-operative creatinine >2 mg/dL (176.8 μmol/L): No = 0 points, Yes = +1 point\n\n"
        explanation += "The total score is calculated by summing the points for each criterion.\n\n"
        
        # 详细计算过程
        current_score = 0
        explanation += f"The current cardiac risk index is {current_score}.\n"
        
        # 检查每个标准
        criteria_details = [
            ("elevated_risk_surgery", "elevated risk surgery"),
            ("ischemic_heart_disease", "ischemic heart disease"),
            ("congestive_heart_failure", "congestive heart failure"),
            ("cerebrovascular_disease", "cerebrovascular_disease"),
            ("pre_operative_insulin_treatment", "pre-operative insulin treatment")
        ]
        
        # 处理布尔标准
        for param_name, description in criteria_details:
            param_value = parameters.get(param_name, False)
            param_status = "present" if param_value else "absent"
            explanation += f"The patient note reports {description} as '{param_status}' for the patient. "
            
            if param_value:
                explanation += f"This means that we increment the score by one and the current total will be {current_score} + 1 = {current_score + 1}.\n"
                current_score += 1
            else:
                explanation += f"This means that the total score remains unchanged at {current_score}.\n"
        
        # 处理肌酐
        pre_operative_creatinine = parameters.get("pre_operative_creatinine")
        explanation += f"The patient's pre-operative creatinine is {pre_operative_creatinine} mg/dL. "
        
        if pre_operative_creatinine > 2.0:
            explanation += f"The patient has pre-operative creatinine > 2 mg/dL, so we increment the score by one and the current total will be {current_score} + 1 = {current_score + 1}.\n"
            current_score += 1
        else:
            explanation += f"The patient has pre-operative creatinine <= 2 mg/dL, so we keep the score the same at {current_score}.\n"
        
        explanation += f"\nThe cardiac risk index score is {score}."
        
        return explanation
