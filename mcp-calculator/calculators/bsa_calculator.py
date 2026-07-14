"""
Body Surface Area (BSA) Calculator
体表面积计算器的 FastMCP 2.0 实现
"""

import math
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


@register_calculator("bsa")
class BSACalculator(BaseCalculator):
    """体表面积计算器实现"""
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=60,
            name="Body Surface Area (BSA)",
            category="anthropometry",
            description="Calculate body surface area using the Mosteller formula",
            parameters=[
                Parameter(
                    name="height",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="cm",
                    min_value=30,
                    max_value=300,
                    description="Height in centimeters"
                ),
                Parameter(
                    name="weight", 
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="kg",
                    min_value=1,
                    max_value=500,
                    description="Weight in kilograms"
                ),
                Parameter(
                    name="height_unit",
                    type=ParameterType.CHOICE,
                    required=False,
                    default="cm",
                    choices=["cm", "m", "in", "ft"],
                    description="Unit for height"
                ),
                Parameter(
                    name="weight_unit",
                    type=ParameterType.CHOICE,
                    required=False,
                    default="kg",
                    choices=["kg", "g", "lb", "lbs", "oz"],
                    description="Unit for weight"
                )
            ]
        )
    
    def _parse_parameter(self, value: Any) -> tuple[float, str]:
        """解析参数，支持字符串格式如 '175cm' 或 '70kg'"""
        if isinstance(value, (int, float)):
            return float(value), ""
        
        if isinstance(value, str):
            import re
            # 匹配数字和单位
            match = re.match(r'^([0-9]*\.?[0-9]+)\s*([a-zA-Z]*)$', value.strip())
            if match:
                num_str, unit = match.groups()
                return float(num_str), unit.lower()
            
            # 处理英制高度格式如 "5ft 9in"
            ft_in_match = re.match(r'^([0-9]+)\s*ft\s*([0-9]+)\s*in$', value.strip())
            if ft_in_match:
                feet, inches = ft_in_match.groups()
                total_inches = int(feet) * 12 + int(inches)
                return float(total_inches), "in"
        
        raise ValueError(f"Cannot parse parameter value: {value}")
    
    def _get_height_explanation(self, value: float, unit: str, height_cm: float) -> str:
        """生成高度转换的解释说明"""
        if unit == "cm":
            return f"The patient's height is {value} cm."
        elif unit == "m":
            return f"The patient's height is {value} m, which is {value} m * 100 cm/m = {height_cm} cm."
        elif unit == "ft":
            return f"The patient's height is {value} ft, which is {value} ft * 30.48 cm/ft = {height_cm} cm."
        elif unit == "in":
            return f"The patient's height is {value} in, which is {value} in * 2.54 cm/in = {height_cm} cm."
        else:
            return f"The patient's height is {height_cm} cm."
    
    def _get_weight_explanation(self, value: float, unit: str, weight_kg: float) -> str:
        """生成重量转换的解释说明"""
        if unit == "kg":
            return f"The patient's weight is {value} kg."
        elif unit in ["lb", "lbs"]:
            return f"The patient's weight is {value} lbs so this converts to {value} lbs * 0.453592 kg/lbs = {weight_kg} kg."
        elif unit == "g":
            return f"The patient's weight is {value} g so this converts to {value} g * 1 kg/1000 g = {weight_kg} kg."
        elif unit == "oz":
            return f"The patient's weight is {value} oz so this converts to {value} oz * 0.0283495 kg/oz = {weight_kg} kg."
        else:
            return f"The patient's weight is {weight_kg} kg."
    
    def validate_parameters(self, params: Dict[str, Any]) -> ValidationResult:
        """验证输入参数"""
        errors = []
        warnings = []
        
        # 检查必需参数
        if "height" not in params:
            errors.append("Height is required")
        if "weight" not in params:
            errors.append("Weight is required")
        
        if errors:
            return ValidationResult(is_valid=False, errors=errors)
        
        # 验证数值范围（考虑单位转换）
        for param_name in ["height", "weight"]:
            if param_name in params:
                try:
                    value, unit = self._parse_parameter(params[param_name])
                except ValueError as e:
                    errors.append(f"Invalid {param_name} format: {e}")
                    continue
                
                # 获取单位并转换为标准单位进行验证
                if param_name == "height":
                    height_unit = unit or params.get("height_unit", "cm")
                    try:
                        # 转换为厘米进行验证
                        height_cm = self.unit_converter.convert(value, height_unit, "cm")
                        if height_cm < 30 or height_cm > 300:
                            errors.append(f"Height {value} {height_unit} is outside valid range (30-300 cm)")
                    except ValueError as e:
                        errors.append(f"Invalid height unit: {height_unit}")
                elif param_name == "weight":
                    weight_unit = unit or params.get("weight_unit", "kg")
                    try:
                        # 转换为千克进行验证
                        weight_kg = self.unit_converter.convert(value, weight_unit, "kg")
                        if weight_kg < 1 or weight_kg > 500:
                            errors.append(f"Weight {value} {weight_unit} is outside valid range (1-500 kg)")
                        
                        # 添加警告（使用转换后的数值）
                        if weight_kg > 200:
                            warnings.append("Weight is very high, please verify")
                    except ValueError as e:
                        errors.append(f"Invalid weight unit: {weight_unit}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def calculate(self, params: Dict[str, Any]) -> CalculationResult:
        """计算体表面积"""
        # 验证参数
        validation = self.validate_parameters(params)
        if not validation.is_valid:
            raise ValueError(f"Invalid parameters: {', '.join(validation.errors)}")
        
        # 解析参数值
        height_value, height_unit_parsed = self._parse_parameter(params["height"])
        weight_value, weight_unit_parsed = self._parse_parameter(params["weight"])
        
        # 获取单位（优先使用解析出的单位）
        height_unit = height_unit_parsed or params.get("height_unit", "cm")
        weight_unit = weight_unit_parsed or params.get("weight_unit", "kg")
        
        # 转换为标准单位（cm, kg）
        height_cm = self.unit_converter.convert(height_value, height_unit, "cm")
        weight_kg = self.unit_converter.convert(weight_value, weight_unit, "kg")
        
        # 使用 Mosteller 公式计算体表面积
        # BSA = sqrt((weight * height) / 3600)
        bsa = math.sqrt((weight_kg * height_cm) / 3600)
        bsa_rounded = round_number(bsa)
        
        # 构建解释说明（遵循原始代码风格）
        height_explanation = self._get_height_explanation(height_value, height_unit, height_cm)
        weight_explanation = self._get_weight_explanation(weight_value, weight_unit, weight_kg)
        
        explanation = (
            f"For the body surface area computation, the formula is sqrt((weight (in kgs) * height (in cm))/3600), "
            f"where the units of weight is in kg and the units of height is in cm.\n\n"
            f"{height_explanation}\n"
            f"{weight_explanation}\n\n"
            f"Therefore, the patient's BSA is sqrt(({weight_kg} (in kgs) * {height_cm} (in cm))/3600) = "
            f"sqrt({weight_kg * height_cm}/3600) = sqrt({weight_kg * height_cm / 3600:.4f}) = {bsa_rounded} m²."
        )
        
        return CalculationResult(
            value=bsa_rounded,
            unit="m²",
            explanation=explanation,
            metadata={
                "height_cm": height_cm,
                "weight_kg": weight_kg,
                "formula": "Mosteller",
                "original_height": f"{height_value} {height_unit}",
                "original_weight": f"{weight_value} {weight_unit}"
            }
        )
