"""
BMI (Body Mass Index) Calculator
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


@register_calculator("bmi")
class BMICalculator(BaseCalculator):
    """BMI计算器实现"""
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=6,
            name="Body Mass Index (BMI)",
            category="anthropometry",
            description="Calculate BMI from height and weight with unit conversion support",
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
            ],
            references=[
                "WHO. Obesity: preventing and managing the global epidemic. 2000."
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
    
    def validate_parameters(self, params: Dict[str, Any]) -> ValidationResult:
        errors = []
        warnings = []
        
        # 获取参数定义
        param_defs = {p.name: p for p in self.get_info().parameters}
        
        # 检查必需参数
        for param_name, param_def in param_defs.items():
            if param_def.required and param_name not in params:
                errors.append(f"Missing required parameter: {param_name}")
        
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
                converter = UnitConverter()
                if param_name == "height":
                    height_unit = unit or params.get("height_unit", "cm")
                    try:
                        # 转换为厘米进行验证
                        height_cm = converter.convert(value, height_unit, "cm")
                        if height_cm < 30 or height_cm > 300:
                            errors.append(f"Height {value} {height_unit} is outside valid range (30-300 cm)")
                    except ValueError as e:
                        errors.append(f"Invalid height unit: {height_unit}")
                elif param_name == "weight":
                    weight_unit = unit or params.get("weight_unit", "kg")
                    try:
                        # 转换为千克进行验证
                        weight_kg = converter.convert(value, weight_unit, "kg")
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
        # 解析参数值
        height_value, height_unit_parsed = self._parse_parameter(params["height"])
        weight_value, weight_unit_parsed = self._parse_parameter(params["weight"])
        
        # 确定单位（优先使用解析出的单位）
        height_unit = height_unit_parsed or params.get("height_unit", "cm")
        weight_unit = weight_unit_parsed or params.get("weight_unit", "kg")
        
        # 单位转换到标准单位（米和千克）
        converter = UnitConverter()
        height_m = converter.convert(height_value, height_unit, "m")
        weight_kg = converter.convert(weight_value, weight_unit, "kg")
        
        # 保存原始数值用于显示
        height = height_value
        weight = weight_value
        
        # 计算BMI
        bmi = weight_kg / (height_m * height_m)
        bmi = round(bmi, 1)  # 使用标准的 round 函数
        
        # 确定分类
        category = self._get_category(bmi)
        
        # 生成详细解释（基于原有逻辑）
        explanation = self._generate_explanation(
            height, height_unit, height_m,
            weight, weight_unit, weight_kg,
            bmi, category
        )
        
        return CalculationResult(
            value=bmi,
            unit="kg/m^2",
            explanation=explanation,
            metadata={
                "category": category,
                "height_m": height_m,
                "weight_kg": weight_kg,
                "original_height": height,
                "original_weight": weight,
                "height_unit": height_unit,
                "weight_unit": weight_unit
            },
            warnings=[]
        )
    
    def _get_category(self, bmi: float) -> str:
        """根据BMI值确定分类"""
        if bmi < 18.5:
            return "Underweight"
        elif bmi < 25:
            return "Normal weight"
        elif bmi < 30:
            return "Overweight"
        else:
            return "Obese"
    
    def _generate_explanation(self, height: float, height_unit: str, height_m: float,
                            weight: float, weight_unit: str, weight_kg: float,
                            bmi: float, category: str) -> str:
        """生成详细的计算解释（基于原有逻辑）"""
        
        explanation = "The formula for computing the patient's BMI is (weight)/(height * height), where weight is the patient's weight in kg and height is the patient's height in m.\n\n"
        
        # 高度转换解释
        height_explanation = self._get_height_explanation(height, height_unit, height_m)
        explanation += height_explanation
        
        # 重量转换解释  
        weight_explanation = self._get_weight_explanation(weight, weight_unit, weight_kg)
        explanation += weight_explanation
        
        # BMI计算
        weight_kg_rounded = round(weight_kg, 1)
        height_m_rounded = round(height_m, 2)
        explanation += f"The patient's BMI is therefore {weight_kg_rounded} kg / ({height_m_rounded} m * {height_m_rounded} m) = {bmi} kg/m^2.\n\n"
        
        # 分类信息
        explanation += f"Category: {category}\n\n"
        explanation += "BMI Categories:\n"
        explanation += "- < 18.5: Underweight\n"
        explanation += "- 18.5-24.9: Normal weight\n"
        explanation += "- 25.0-29.9: Overweight\n"
        explanation += "- ≥ 30.0: Obese"
        
        return explanation
    
    def _get_height_explanation(self, height: float, height_unit: str, height_m: float) -> str:
        """生成高度转换解释"""
        height_m_rounded = round(height_m, 3)
        if height_unit == "m":
            return f"The patient's height is {height} m.\n"
        elif height_unit == "cm":
            return f"The patient's height is {height} cm, which is {height} cm * 1 m / 100 cm = {height_m_rounded} m.\n"
        elif height_unit == "ft":
            return f"The patient's height is {height} ft, which is {height} ft * 0.3048 m / ft = {height_m_rounded} m.\n"
        elif height_unit == "in":
            return f"The patient's height is {height} in, which is {height} in * 0.0254 m / in = {height_m_rounded} m.\n"
        else:
            return f"The patient's height is {height} {height_unit}, converted to {height_m_rounded} m.\n"
    
    def _get_weight_explanation(self, weight: float, weight_unit: str, weight_kg: float) -> str:
        """生成重量转换解释"""
        weight_kg_rounded = round(weight_kg, 3)
        if weight_unit == "kg":
            return f"The patient's weight is {weight} kg.\n"
        elif weight_unit in ["lb", "lbs"]:
            return f"The patient's weight is {weight} lbs so this converts to {weight} lbs * 0.453592 kg/lbs = {weight_kg_rounded} kg.\n"
        elif weight_unit == "g":
            return f"The patient's weight is {weight} g so this converts to {weight} g * 1 kg/1000 g = {weight_kg_rounded} kg.\n"
        else:
            return f"The patient's weight is {weight} {weight_unit}, converted to {weight_kg_rounded} kg.\n"
