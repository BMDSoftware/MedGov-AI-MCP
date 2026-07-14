"""
Adjusted Body Weight Calculator
调整体重计算器的 FastMCP 2.0 实现
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


@register_calculator("adjusted_body_weight")
class AdjustedBodyWeightCalculator(BaseCalculator):
    """调整体重计算器实现"""
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=62,
            name="Adjusted Body Weight (ABW)",
            category="anthropometry",
            description="Calculate adjusted body weight: IBW + 0.4 × (actual weight - IBW)",
            parameters=[
                Parameter(
                    name="height",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="cm",
                    min_value=100,
                    max_value=250,
                    description="Height in centimeters"
                ),
                Parameter(
                    name="weight", 
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="kg",
                    min_value=20,
                    max_value=300,
                    description="Actual weight in kilograms"
                ),
                Parameter(
                    name="sex",
                    type=ParameterType.CHOICE,
                    required=True,
                    choices=["male", "female"],
                    description="Biological sex"
                )
            ]
        )
    
    def validate_parameters(self, params: Dict[str, Any]) -> ValidationResult:
        """验证输入参数"""
        errors = []
        
        # 验证身高
        height = params.get("height")
        if height is None:
            errors.append("Height is required")
        elif not (100 <= height <= 250):
            errors.append("Height must be between 100 and 250 cm")
            
        # 验证体重
        weight = params.get("weight")
        if weight is None:
            errors.append("Weight is required")
        elif not (20 <= weight <= 300):
            errors.append("Weight must be between 20 and 300 kg")
            
        # 验证性别
        sex = params.get("sex")
        if sex is None:
            errors.append("Sex is required")
        elif sex not in ["male", "female"]:
            errors.append("Sex must be 'male' or 'female'")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )
    
    def calculate(self, params: Dict[str, Any]) -> CalculationResult:
        """计算调整体重"""
        # 验证参数
        validation = self.validate_parameters(params)
        if not validation.is_valid:
            raise ValueError(f"Invalid parameters: {', '.join(validation.errors)}")
        
        # 获取参数值
        height_cm = float(params["height"])
        actual_weight = float(params["weight"])
        sex = params["sex"]
        
        # 转换身高为英寸
        height_inches = height_cm / 2.54
        
        # 计算理想体重 (IBW)
        if sex == "male":
            ibw = 50 + 2.3 * (height_inches - 60)
        else:  # female
            ibw = 45.5 + 2.3 * (height_inches - 60)
        
        ibw_rounded = round_number(ibw)
        
        # 计算调整体重 (ABW)
        # 公式: ABW = IBW + 0.4 × (actual weight - IBW)
        abw = ibw + 0.4 * (actual_weight - ibw)
        abw_rounded = round_number(abw)
        
        # 构建解释说明
        explanation = (
            f"Adjusted Body Weight (ABW) calculation:\n"
            f"Step 1: Calculate Ideal Body Weight (IBW)\n"
            f"Height: {height_cm} cm = {round_number(height_inches)} inches\n"
        )
        
        if sex == "male":
            explanation += f"IBW (male) = 50 + 2.3 × (height in inches - 60)\n"
        else:
            explanation += f"IBW (female) = 45.5 + 2.3 × (height in inches - 60)\n"
        
        explanation += (
            f"IBW = {ibw_rounded} kg\n\n"
            f"Step 2: Calculate Adjusted Body Weight\n"
            f"ABW = IBW + 0.4 × (actual weight - IBW)\n"
            f"ABW = {ibw_rounded} + 0.4 × ({actual_weight} - {ibw_rounded})\n"
            f"ABW = {ibw_rounded} + 0.4 × {round_number(actual_weight - ibw)}\n"
            f"ABW = {ibw_rounded} + {round_number(0.4 * (actual_weight - ibw))}\n"
            f"ABW = {abw_rounded} kg"
        )
        
        # 添加临床意义
        weight_difference = actual_weight - ibw
        if weight_difference > 30:
            clinical_note = "Significant obesity - ABW recommended for drug dosing"
        elif weight_difference > 20:
            clinical_note = "Moderate obesity - consider ABW for drug dosing"
        elif weight_difference < -10:
            clinical_note = "Underweight - use actual weight for drug dosing"
        else:
            clinical_note = "Near ideal weight - actual weight appropriate for dosing"
        
        return CalculationResult(
            value=abw_rounded,
            unit="kg",
            explanation=explanation,
            metadata={
                "height_cm": height_cm,
                "height_inches": round_number(height_inches),
                "actual_weight": actual_weight,
                "ideal_body_weight": ibw_rounded,
                "sex": sex,
                "clinical_note": clinical_note
            }
        )
