"""
Ideal Body Weight Calculator
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


@register_calculator("ideal_body_weight")
class IdealBodyWeightCalculator(BaseCalculator):
    """理想体重计算器实现"""
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=10,
            name="Ideal Body Weight",
            category="anthropometry",
            description="Calculate ideal body weight based on height and sex using Devine formula",
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
                    name="sex",
                    type=ParameterType.CHOICE,
                    required=True,
                    choices=["Male", "Female"],
                    description="Patient sex"
                ),
                Parameter(
                    name="height_unit",
                    type=ParameterType.CHOICE,
                    required=False,
                    choices=["cm", "inches", "feet"],
                    default="cm",
                    description="Height unit"
                )
            ]
        )
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> ValidationResult:
        """验证参数"""
        errors = []
        
        # 获取参数值
        height = parameters.get("height")
        sex = parameters.get("sex")
        height_unit = parameters.get("height_unit", "cm")
        
        # 验证身高
        if height is None:
            errors.append("Missing required parameter: height")
        else:
            # 转换身高为数字
            try:
                height_value = float(height)
                
                # 验证身高范围（根据单位调整）
                if height_unit == "cm":
                    if not (100 <= height_value <= 250):
                        errors.append("Height must be between 100 and 250 cm")
                elif height_unit == "inches":
                    if not (39 <= height_value <= 98):
                        errors.append("Height must be between 39 and 98 inches")
                elif height_unit == "feet":
                    if not (3.25 <= height_value <= 8.17):
                        errors.append("Height must be between 3.25 and 8.17 feet")
            except (ValueError, TypeError):
                errors.append("Height must be a valid number")
        
        # 验证性别
        if sex is None:
            errors.append("Missing required parameter: sex")
        elif sex not in ["Male", "Female"]:
            errors.append("Sex must be 'Male' or 'Female'")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )
    
    def calculate(self, parameters: Dict[str, Any]) -> CalculationResult:
        """执行计算"""
        height = parameters.get("height")
        sex = parameters.get("sex")
        height_unit = parameters.get("height_unit", "cm")
        
        # 转换身高为数字
        height_value = float(height)
        
        # 转换身高为英寸
        height_inches = self._convert_to_inches(height_value, height_unit)
        
        # 计算理想体重
        if sex == "Male":
            # 男性：IBW = 50 + 2.3 × (身高(英寸) - 60)
            ibw = round_number(50 + 2.3 * (height_inches - 60))
        else:
            # 女性：IBW = 45.5 + 2.3 × (身高(英寸) - 60)
            ibw = round_number(45.5 + 2.3 * (height_inches - 60))
        
        # 生成解释
        explanation = self._generate_explanation(height_value, height_unit, height_inches, sex, ibw)
        
        return CalculationResult(
            value=ibw,
            unit="kg",
            explanation=explanation,
            metadata={
                "height": height_value,
                "height_unit": height_unit,
                "height_inches": height_inches,
                "sex": sex,
                "formula": f"IBW = {50 if sex == 'Male' else 45.5} + 2.3 × (height_inches - 60)"
            }
        )
    
    def _convert_to_inches(self, height: float, unit: str) -> float:
        """转换身高为英寸"""
        converter = UnitConverter()
        # 将输入单位映射为UnitConverter支持的单位
        unit_mapping = {
            "cm": "cm",
            "inches": "in",
            "feet": "ft"
        }
        from_unit = unit_mapping.get(unit, unit)
        return converter.convert(height, from_unit, "in")
    
    def _generate_explanation(self, height: float, height_unit: str, height_inches: float, 
                            sex: str, ibw: float) -> str:
        """生成计算解释"""
        explanation = f"The patient's gender is {sex}.\n"
        
        if height_unit != "inches":
            explanation += f"The patient's height is {height} {height_unit}, which converts to {round_number(height_inches)} inches.\n\n"
        else:
            explanation += f"The patient's height is {height} inches.\n\n"
        
        if sex == "Male":
            explanation += f"For males, the ideal body weight (IBW) is calculated as follows:\n"
            explanation += f"IBW = 50 kg + 2.3 kg * (height (in inches) - 60)\n"
            explanation += f"Plugging in the values gives us 50 kg + 2.3 kg * ({round_number(height_inches)} (in inches) - 60) = {ibw} kg.\n"
        else:
            explanation += f"For females, the ideal body weight (IBW) is calculated as follows:\n"
            explanation += f"IBW = 45.5 kg + 2.3 kg * (height (in inches) - 60)\n"
            explanation += f"Plugging in the values gives us 45.5 kg + 2.3 kg * ({round_number(height_inches)} (in inches) - 60) = {ibw} kg.\n"
        
        explanation += f"Hence, the patient's IBW is {ibw} kg."
        
        return explanation
    

