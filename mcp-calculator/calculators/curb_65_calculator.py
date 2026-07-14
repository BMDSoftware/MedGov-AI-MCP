"""
CURB-65 Score Calculator
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


@register_calculator("curb_65")
class CURB65Calculator(BaseCalculator):
    """CURB-65肺炎严重程度评分计算器实现"""
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=45,
            name="CURB-65 Score",
            category="pulmonology",
            description="CURB-65 pneumonia severity score for community-acquired pneumonia assessment",
            parameters=[
                Parameter(
                    name="confusion",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Confusion (altered mental status)"
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
                    name="diastolic_bp",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="mmHg",
                    min_value=20,
                    max_value=200,
                    description="Diastolic blood pressure in mmHg"
                ),
                Parameter(
                    name="age",
                    type=ParameterType.NUMERIC,
                    required=True,
                    min_value=0,
                    max_value=120,
                    description="Patient age in years"
                )
            ]
        )
    
    def _parse_parameter(self, value: Any) -> tuple[float, str]:
        """解析参数，支持字符串格式如 '40.0mg/dL' 或 '34breaths/min'"""
        if isinstance(value, (int, float)):
            return float(value), ""
        
        if isinstance(value, str):
            import re
            # 匹配数字和单位
            match = re.match(r'^([0-9]*\.?[0-9]+)\s*([a-zA-Z/]*)$', value.strip())
            if match:
                num_str, unit = match.groups()
                return float(num_str), unit.lower()
        
        raise ValueError(f"Cannot parse parameter value: {value}")
    
    def validate_parameters(self, params: Dict[str, Any]) -> ValidationResult:
        """验证参数"""
        errors = []
        
        # 获取参数定义
        param_defs = {p.name: p for p in self.get_info().parameters}
        
        # 检查必需参数
        for param_name, param_def in param_defs.items():
            if param_def.required and param_name not in params:
                errors.append(f"Missing required parameter: {param_name}")
        
        if errors:
            return ValidationResult(is_valid=False, errors=errors)
        
        # 验证数值参数
        for param_name in ["bun", "respiratory_rate", "systolic_bp", "diastolic_bp", "age"]:
            if param_name in params:
                try:
                    value, unit = self._parse_parameter(params[param_name])
                    param_def = param_defs[param_name]
                    
                    # 检查数值范围
                    if param_def.min_value is not None and value < param_def.min_value:
                        errors.append(f"{param_name} value {value} is below minimum {param_def.min_value}")
                    if param_def.max_value is not None and value > param_def.max_value:
                        errors.append(f"{param_name} value {value} is above maximum {param_def.max_value}")
                        
                except ValueError as e:
                    errors.append(f"Invalid {param_name} format: {e}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )
    
    def calculate(self, params: Dict[str, Any]) -> CalculationResult:
        """计算CURB-65评分"""
        
        # 获取参数值
        confusion = params.get("confusion", False)
        
        # 解析数值参数
        bun_value, bun_unit = self._parse_parameter(params["bun"])
        respiratory_rate_value, _ = self._parse_parameter(params["respiratory_rate"])
        systolic_bp_value, _ = self._parse_parameter(params["systolic_bp"])
        diastolic_bp_value, _ = self._parse_parameter(params["diastolic_bp"])
        age_value, _ = self._parse_parameter(params["age"])
        
        # BUN 单位转换（mmol/L 转 mg/dL）
        if bun_unit == "mmol/l":
            bun = bun_value * 2.8  # 1 mmol/L = 2.8 mg/dL
        else:
            bun = bun_value
            
        respiratory_rate = respiratory_rate_value
        systolic_bp = systolic_bp_value
        diastolic_bp = diastolic_bp_value
        age = age_value
        
        score = 0
        explanation_parts = []
        
        # 1. 意识混乱
        if confusion:
            score += 1
            explanation_parts.append("Confusion (altered mental status): +1 point")
        else:
            explanation_parts.append("No confusion: 0 points")
        
        # 2. BUN > 19 mg/dL
        if bun > 19:
            score += 1
            explanation_parts.append(f"BUN {bun:.1f} > 19 mg/dL: +1 point")
        else:
            explanation_parts.append(f"BUN {bun:.1f} ≤ 19 mg/dL: 0 points")
        
        # 3. 呼吸频率 ≥ 30
        if respiratory_rate >= 30:
            score += 1
            explanation_parts.append(f"Respiratory rate {respiratory_rate:.0f} ≥ 30 breaths/min: +1 point")
        else:
            explanation_parts.append(f"Respiratory rate {respiratory_rate:.0f} < 30 breaths/min: 0 points")
        
        # 4. 血压 (收缩压 < 90 或舒张压 ≤ 60)
        if systolic_bp < 90 or diastolic_bp <= 60:
            score += 1
            explanation_parts.append(f"Blood pressure {systolic_bp:.0f}/{diastolic_bp:.0f} (SBP < 90 or DBP ≤ 60): +1 point")
        else:
            explanation_parts.append(f"Blood pressure {systolic_bp:.0f}/{diastolic_bp:.0f} (SBP ≥ 90 and DBP > 60): 0 points")
        
        # 5. 年龄 ≥ 65
        if age >= 65:
            score += 1
            explanation_parts.append(f"Age {age:.0f} ≥ 65 years: +1 point")
        else:
            explanation_parts.append(f"Age {age:.0f} < 65 years: 0 points")
        
        # 生成解释
        explanation = "CURB-65 Score calculation:\n\n"
        explanation += "\n".join([f"• {part}" for part in explanation_parts])
        explanation += f"\n\nTotal CURB-65 Score: {score} points"
        
        # 添加风险分层和建议
        if score == 0:
            risk_level = "Low risk"
            mortality_risk = "0.7%"
            recommendation = "Consider home treatment"
        elif score == 1:
            risk_level = "Low risk"
            mortality_risk = "2.1%"
            recommendation = "Consider home treatment"
        elif score == 2:
            risk_level = "Intermediate risk"
            mortality_risk = "9.2%"
            recommendation = "Consider short inpatient stay or closely supervised outpatient treatment"
        elif score == 3:
            risk_level = "High risk"
            mortality_risk = "14.5%"
            recommendation = "Manage as severe pneumonia with inpatient treatment"
        elif score == 4:
            risk_level = "High risk"
            mortality_risk = "40%"
            recommendation = "Manage as severe pneumonia with possible ICU admission"
        else:  # score == 5
            risk_level = "Very high risk"
            mortality_risk = "57%"
            recommendation = "Manage as severe pneumonia with possible ICU admission"
        
        explanation += f"\n\nRisk Level: {risk_level}"
        explanation += f"\n30-day Mortality Risk: {mortality_risk}"
        explanation += f"\nRecommendation: {recommendation}"
        
        return CalculationResult(
            value=score,
            unit="points",
            explanation=explanation,
            metadata={
                "risk_level": risk_level,
                "mortality_risk": mortality_risk,
                "recommendation": recommendation,
                "confusion_points": 1 if confusion else 0,
                "bun_points": 1 if bun > 19 else 0,
                "respiratory_rate_points": 1 if respiratory_rate >= 30 else 0,
                "blood_pressure_points": 1 if systolic_bp < 90 or diastolic_bp <= 60 else 0,
                "age_points": 1 if age >= 65 else 0,
                "bun_original": bun_value,
                "bun_unit": bun_unit,
                "bun_converted": bun
            }
        )
