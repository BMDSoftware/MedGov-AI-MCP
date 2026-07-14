"""
Target Weight Calculator
目标体重计算器的 FastMCP 2.0 实现
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
from medcalc.utils import round_number, UnitConverter


@register_calculator("target_weight")
class TargetWeightCalculator(BaseCalculator):
    """目标体重计算器实现"""
    
    def __init__(self):
        self.unit_converter = UnitConverter()
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=61,
            name="Target Weight Calculator",
            category="anthropometry",
            description="Calculate target weight based on desired BMI and height with unit conversion support",
            parameters=[
                Parameter(
                    name="height",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="cm",
                    min_value=30,
                    max_value=300,
                    description="Height (supports cm, m, ft, in)"
                ),
                Parameter(
                    name="height_unit",
                    type=ParameterType.CHOICE,
                    required=False,
                    choices=["cm", "m", "ft", "in"],
                    default="cm",
                    description="Height unit"
                ),
                Parameter(
                    name="target_bmi", 
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="kg/m²",
                    min_value=15,
                    max_value=40,
                    description="Target BMI in kg/m²"
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
        else:
            try:
                height_val = float(height)
                height_unit = params.get("height_unit", "cm")
                
                # 验证单位
                if height_unit not in ["cm", "m", "ft", "in"]:
                    errors.append("Height unit must be one of: cm, m, ft, in")
                else:
                    # 转换为米进行范围验证
                    try:
                        height_m = self.unit_converter.convert(height_val, height_unit, "m")
                        if height_m < 1.0 or height_m > 2.5:  # 100cm 到 250cm
                            errors.append(f"Height must be between 100-250 cm, 1.0-2.5 m, 3.28-8.2 ft, or 39-98 in")
                    except ValueError as e:
                        errors.append(f"Invalid height unit conversion: {str(e)}")
                        
            except (ValueError, TypeError):
                errors.append("Height must be a valid number")
            
        # 验证目标BMI
        target_bmi = params.get("target_bmi")
        if target_bmi is None:
            errors.append("Target BMI is required")
        else:
            try:
                bmi_val = float(target_bmi)
                if bmi_val < 15 or bmi_val > 40:
                    errors.append("Target BMI must be between 15 and 40 kg/m²")
            except (ValueError, TypeError):
                errors.append("Target BMI must be a valid number")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )
    
    def calculate(self, params: Dict[str, Any]) -> CalculationResult:
        """计算目标体重"""
        # 验证参数
        validation = self.validate_parameters(params)
        if not validation.is_valid:
            raise ValueError(f"Invalid parameters: {', '.join(validation.errors)}")
        
        # 获取参数值
        height_value = float(params["height"])
        height_unit = params.get("height_unit", "cm")
        target_bmi = float(params["target_bmi"])
        
        # 使用 UnitConverter 转换身高为米
        height_m = self.unit_converter.convert(height_value, height_unit, "m")
        
        # 计算目标体重
        # 公式: Target Weight = BMI × height²
        target_weight = target_bmi * (height_m * height_m)
        target_weight_rounded = round_number(target_weight)
        
        # 构建解释说明
        explanation = (
            f"Target Weight calculation:\n"
            f"Formula: Target Weight = Target BMI × Height²\n"
            f"Where:\n"
            f"- Target BMI = {target_bmi} kg/m²\n"
            f"- Height = {height_value} {height_unit} = {height_m:.3f} m\n\n"
            f"Calculation:\n"
            f"Target Weight = {target_bmi} × ({height_m:.3f})²\n"
            f"Target Weight = {target_bmi} × {height_m * height_m:.4f}\n"
            f"Target Weight = {target_weight_rounded} kg"
        )
        
        # 添加BMI分类信息
        if target_bmi < 18.5:
            bmi_category = "Underweight"
        elif target_bmi < 25:
            bmi_category = "Normal weight"
        elif target_bmi < 30:
            bmi_category = "Overweight"
        else:
            bmi_category = "Obese"
        
        return CalculationResult(
            value=target_weight_rounded,
            unit="kg",
            explanation=explanation,
            metadata={
                "height_value": height_value,
                "height_unit": height_unit,
                "height_m": height_m,
                "target_bmi": target_bmi,
                "bmi_category": bmi_category
            }
        )
