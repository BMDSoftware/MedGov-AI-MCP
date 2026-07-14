"""
FeverPAIN Score Calculator
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


@register_calculator("feverpain")
class FeverPAINCalculator(BaseCalculator):
    """FeverPAIN评分计算器实现"""
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=33,
            name="FeverPAIN Score",
            category="infectious_disease",
            description="FeverPAIN score for assessing streptococcal pharyngitis probability",
            parameters=[
                Parameter(
                    name="fever_24_hours",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Fever in past 24 hours"
                ),
                Parameter(
                    name="cough_coryza_absent",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Absence of cough or coryza (runny nose)"
                ),
                Parameter(
                    name="symptom_onset",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Symptom onset ≤3 days"
                ),
                Parameter(
                    name="purulent_tonsils",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Purulent tonsils"
                ),
                Parameter(
                    name="severe_tonsil_inflammation",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Severe tonsil inflammation"
                )
            ]
        )
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> ValidationResult:
        """验证参数"""
        errors = []
        warnings = []
        
        # 获取参数定义
        param_defs = {p.name: p for p in self.get_info().parameters}
        
        # 验证所有参数类型
        for param_name, value in parameters.items():
            if param_name in param_defs:
                param_def = param_defs[param_name]
                if param_def.type == ParameterType.BOOLEAN:
                    if not isinstance(value, bool):
                        errors.append(f"Parameter '{param_name}' must be a boolean, got {type(value).__name__}")
            else:
                warnings.append(f"Unknown parameter: {param_name}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def calculate(self, parameters: Dict[str, Any]) -> CalculationResult:
        """计算FeverPAIN评分"""
        
        # 获取参数值
        fever_24_hours = parameters.get("fever_24_hours", False)
        cough_coryza_absent = parameters.get("cough_coryza_absent", False)
        symptom_onset = parameters.get("symptom_onset", False)
        purulent_tonsils = parameters.get("purulent_tonsils", False)
        severe_tonsil_inflammation = parameters.get("severe_tonsil_inflammation", False)
        
        score = 0
        explanation_parts = []
        
        # 1. 过去24小时发热
        if fever_24_hours:
            score += 1
            explanation_parts.append("Fever in past 24 hours: +1 point")
        else:
            explanation_parts.append("No fever in past 24 hours: 0 points")
        
        # 2. 无咳嗽或鼻炎
        if cough_coryza_absent:
            score += 1
            explanation_parts.append("Absence of cough or coryza: +1 point")
        else:
            explanation_parts.append("Presence of cough or coryza: 0 points")
        
        # 3. 症状发作≤3天
        if symptom_onset:
            score += 1
            explanation_parts.append("Symptom onset ≤3 days: +1 point")
        else:
            explanation_parts.append("Symptom onset >3 days: 0 points")
        
        # 4. 化脓性扁桃体
        if purulent_tonsils:
            score += 1
            explanation_parts.append("Purulent tonsils: +1 point")
        else:
            explanation_parts.append("No purulent tonsils: 0 points")
        
        # 5. 严重扁桃体炎症
        if severe_tonsil_inflammation:
            score += 1
            explanation_parts.append("Severe tonsil inflammation: +1 point")
        else:
            explanation_parts.append("No severe tonsil inflammation: 0 points")
        
        # 生成解释
        explanation = "FeverPAIN Score calculation:\n\n"
        explanation += "\n".join([f"• {part}" for part in explanation_parts])
        explanation += f"\n\nTotal FeverPAIN Score: {score} points"
        
        # 添加风险分层和建议
        if score == 0 or score == 1:
            strep_probability = "13-18%"
            recommendation = "No antibiotic or delayed antibiotic prescription"
        elif score == 2 or score == 3:
            strep_probability = "34-40%"
            recommendation = "Consider delayed antibiotic prescription or rapid antigen test"
        else:  # score >= 4
            strep_probability = "62-65%"
            recommendation = "Consider immediate antibiotic prescription or rapid antigen test"
        
        explanation += f"\n\nStreptococcal pharyngitis probability: {strep_probability}"
        explanation += f"\nRecommendation: {recommendation}"
        
        return CalculationResult(
            value=score,
            unit="points",
            explanation=explanation,
            metadata={
                "strep_probability": strep_probability,
                "recommendation": recommendation,
                "fever_points": 1 if fever_24_hours else 0,
                "cough_coryza_points": 1 if cough_coryza_absent else 0,
                "onset_points": 1 if symptom_onset else 0,
                "purulent_points": 1 if purulent_tonsils else 0,
                "inflammation_points": 1 if severe_tonsil_inflammation else 0
            }
        )
