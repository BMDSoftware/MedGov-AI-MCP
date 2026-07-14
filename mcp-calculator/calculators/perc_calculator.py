"""
PERC (Pulmonary Embolism Rule-out Criteria) Calculator
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


@register_calculator("perc")
class PERCCalculator(BaseCalculator):
    """PERC肺栓塞排除标准计算器实现"""
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=48,
            name="PERC Rule (Pulmonary Embolism Rule-out Criteria)",
            category="pulmonology",
            description="PERC rule for excluding pulmonary embolism in low-risk patients",
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
                    name="heart_rate",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="bpm",
                    min_value=30,
                    max_value=300,
                    description="Heart rate in beats per minute"
                ),
                Parameter(
                    name="oxygen_saturation",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="%",
                    min_value=50,
                    max_value=100,
                    description="Oxygen saturation on room air (%)"
                ),
                Parameter(
                    name="unilateral_leg_swelling",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Unilateral leg swelling"
                ),
                Parameter(
                    name="hemoptysis",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Hemoptysis (coughing up blood)"
                ),
                Parameter(
                    name="recent_surgery_or_trauma",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Recent surgery or trauma (within 4 weeks, requiring general anesthesia)"
                ),
                Parameter(
                    name="previous_pe",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Prior pulmonary embolism"
                ),
                Parameter(
                    name="previous_dvt",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Prior deep vein thrombosis"
                ),
                Parameter(
                    name="hormone_use",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Hormone use (oral contraceptives, hormone replacement, or estrogenic hormones)"
                )
            ]
        )
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> ValidationResult:
        """验证参数"""
        errors = []
        
        # 获取参数定义
        info = self.get_info()
        param_defs = {p.name: p for p in info.parameters}
        
        # 验证必填参数
        for param in info.parameters:
            if param.required and param.name not in parameters:
                errors.append(f"Missing required parameter: {param.name}")
            elif param.name in parameters:
                value = parameters[param.name]
                # 验证数值范围
                if param.type.value == "numeric" and value is not None:
                    try:
                        value = float(value)
                        if param.min_value is not None and value < param.min_value:
                            errors.append(f"{param.name}: {value} is below minimum {param.min_value}")
                        if param.max_value is not None and value > param.max_value:
                            errors.append(f"{param.name}: {value} is above maximum {param.max_value}")
                    except (TypeError, ValueError):
                        errors.append(f"{param.name}: Invalid numeric value {value}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )
    
    def calculate(self, parameters: Dict[str, Any]) -> CalculationResult:
        """计算PERC标准"""
        
        # 获取参数值 - 直接从字典获取，使用默认值
        age = parameters.get("age")
        heart_rate = parameters.get("heart_rate")
        oxygen_saturation = parameters.get("oxygen_saturation")
        unilateral_leg_swelling = parameters.get("unilateral_leg_swelling", False)
        hemoptysis = parameters.get("hemoptysis", False)
        recent_surgery_or_trauma = parameters.get("recent_surgery_or_trauma", False)
        previous_pe = parameters.get("previous_pe", False)
        previous_dvt = parameters.get("previous_dvt", False)
        hormone_use = parameters.get("hormone_use", False)
        
        criteria_count = 0
        explanation_parts = []
        
        # 1. 年龄 ≥ 50岁
        if age >= 50:
            criteria_count += 1
            explanation_parts.append(f"Age {age} ≥ 50 years: +1 criterion")
        else:
            explanation_parts.append(f"Age {age} < 50 years: 0 criteria")
        
        # 2. 心率 ≥ 100 bpm
        if heart_rate >= 100:
            criteria_count += 1
            explanation_parts.append(f"Heart rate {heart_rate} ≥ 100 bpm: +1 criterion")
        else:
            explanation_parts.append(f"Heart rate {heart_rate} < 100 bpm: 0 criteria")
        
        # 3. 室内空气下血氧饱和度 < 95%
        if oxygen_saturation < 95:
            criteria_count += 1
            explanation_parts.append(f"O2 saturation {oxygen_saturation}% < 95%: +1 criterion")
        else:
            explanation_parts.append(f"O2 saturation {oxygen_saturation}% ≥ 95%: 0 criteria")
        
        # 4. 单侧腿部肿胀
        if unilateral_leg_swelling:
            criteria_count += 1
            explanation_parts.append("Unilateral leg swelling: +1 criterion")
        else:
            explanation_parts.append("No unilateral leg swelling: 0 criteria")
        
        # 5. 咯血
        if hemoptysis:
            criteria_count += 1
            explanation_parts.append("Hemoptysis: +1 criterion")
        else:
            explanation_parts.append("No hemoptysis: 0 criteria")
        
        # 6. 近期手术或外伤
        if recent_surgery_or_trauma:
            criteria_count += 1
            explanation_parts.append("Recent surgery or trauma (within 4 weeks): +1 criterion")
        else:
            explanation_parts.append("No recent surgery or trauma: 0 criteria")
        
        # 7. 既往PE或DVT史
        if previous_pe or previous_dvt:
            criteria_count += 1
            history_types = []
            if previous_pe:
                history_types.append("PE")
            if previous_dvt:
                history_types.append("DVT")
            explanation_parts.append(f"Prior {'/'.join(history_types)}: +1 criterion")
        else:
            explanation_parts.append("No prior PE or DVT: 0 criteria")
        
        # 8. 激素使用
        if hormone_use:
            criteria_count += 1
            explanation_parts.append("Hormone use: +1 criterion")
        else:
            explanation_parts.append("No hormone use: 0 criteria")
        
        # 生成解释
        explanation = "PERC Rule (Pulmonary Embolism Rule-out Criteria) assessment:\n\n"
        explanation += "\n".join([f"• {part}" for part in explanation_parts])
        explanation += f"\n\nTotal PERC criteria met: {criteria_count}/8"
        
        # 添加解释和建议
        if criteria_count == 0:
            perc_negative = True
            recommendation = "PERC rule negative - PE can be ruled out without further testing in low-risk patients"
            pe_probability = "<1.8%"
        else:
            perc_negative = False
            recommendation = "PERC rule positive - Further evaluation for PE is warranted (consider D-dimer, imaging)"
            pe_probability = "Cannot be ruled out"
        
        explanation += f"\n\nPERC Rule: {'Negative' if perc_negative else 'Positive'}"
        explanation += f"\nPE Probability: {pe_probability}"
        explanation += f"\nRecommendation: {recommendation}"
        
        # 添加使用注意事项
        explanation += "\n\nNote: PERC rule should only be applied to patients with low clinical probability of PE"
        
        return CalculationResult(
            value=criteria_count,
            unit="criteria",
            explanation=explanation,
            metadata={
                "perc_negative": perc_negative,
                "pe_probability": pe_probability,
                "recommendation": recommendation,
                "criteria_breakdown": {
                    "age_50_or_older": age >= 50,
                    "heart_rate_100_or_higher": heart_rate >= 100,
                    "oxygen_sat_less_than_95": oxygen_saturation < 95,
                    "unilateral_leg_swelling": unilateral_leg_swelling,
                    "hemoptysis": hemoptysis,
                    "recent_surgery_trauma": recent_surgery_or_trauma,
                    "prior_pe_dvt": previous_pe or previous_dvt,
                    "hormone_use": hormone_use
                }
            }
        )
