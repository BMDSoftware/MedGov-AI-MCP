"""
Maintenance Fluid Calculator
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


@register_calculator("maintenance_fluid")
class MaintenanceFluidCalculator(BaseCalculator):
    """维持液体计算器实现"""
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=22,
            name="Maintenance Fluid Calculator",
            category="pharmacology",
            description="Calculate maintenance fluid requirements based on body weight",
            parameters=[
                Parameter(
                    name="weight",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="kg",
                    min_value=0.5,
                    max_value=200,
                    description="Patient weight in kilograms"
                )
            ]
        )
    
    def _parse_parameter(self, value: Any) -> tuple[float, str]:
        """解析参数，支持字符串格式如 '30kg' 或 '22lbs'"""
        if isinstance(value, (int, float)):
            return float(value), ""
        
        if isinstance(value, str):
            import re
            # 匹配数字和单位
            match = re.match(r'^([0-9]*\.?[0-9]+)\s*([a-zA-Z]*)$', value.strip())
            if match:
                num_str, unit = match.groups()
                try:
                    return float(num_str), unit.lower()
                except ValueError:
                    pass
        
        raise ValueError(f"Invalid parameter format: {value}")
    
    def _convert_weight_to_kg(self, weight: float, unit: str) -> float:
        """将体重转换为千克"""
        if unit in ["kg", ""]:
            return weight
        elif unit in ["g", "grams"]:
            return weight / 1000
        elif unit in ["lb", "lbs", "pounds"]:
            return weight * 0.453592  # 1 lb = 0.453592 kg
        elif unit in ["oz", "ounces"]:
            return weight * 0.0283495  # 1 oz = 0.0283495 kg
        else:
            raise ValueError(f"Unsupported weight unit: {unit}")

    def validate_parameters(self, parameters: Dict[str, Any]) -> ValidationResult:
        """验证输入参数"""
        errors = []
        
        # 检查必需参数
        if "weight" not in parameters:
            errors.append("weight is required")
            return ValidationResult(is_valid=False, errors=errors)
        
        try:
            # 解析体重值
            weight_value, weight_unit = self._parse_parameter(parameters["weight"])
            
            # 转换为千克
            weight_kg = self._convert_weight_to_kg(weight_value, weight_unit)
            
            # 验证范围
            if weight_kg <= 0:
                errors.append("weight must be greater than 0")
            elif weight_kg > 200:
                errors.append("weight must be 200 kg or less")
                
        except ValueError as e:
            errors.append(f"Invalid weight format: {e}")
        
        return ValidationResult(is_valid=len(errors) == 0, errors=errors)
    
    def calculate(self, parameters: Dict[str, Any]) -> CalculationResult:
        """计算维持液体需求"""
        # 解析体重值
        weight_value, weight_unit = self._parse_parameter(parameters["weight"])
        
        # 转换为千克
        weight = self._convert_weight_to_kg(weight_value, weight_unit)
        
        # 根据体重计算维持液体需求
        if weight < 10:
            # <10kg: 4 mL/kg/hr
            fluid_rate = round_number(weight * 4)
            formula = f"{weight} kg × 4 mL/kg/hr"
            rule = "For patients with weight less than 10 kg: 4 mL/kg/hr"
        elif 10 <= weight <= 20:
            # 10-20kg: 40 mL/hr + 2 mL/kg/hr × (weight-10)
            fluid_rate = round_number(40 + 2 * (weight - 10))
            formula = f"40 mL/hr + 2 mL/kg/hr × ({weight} kg - 10 kg)"
            rule = "For patients with weight between 10-20 kg: 40 mL/hr + 2 mL/kg/hr × (weight - 10 kg)"
        else:
            # >20kg: 60 mL/hr + 1 mL/kg/hr × (weight-20)
            fluid_rate = round_number(60 + (weight - 20))
            formula = f"60 mL/hr + 1 mL/kg/hr × ({weight} kg - 20 kg)"
            rule = "For patients with weight greater than 20 kg: 60 mL/hr + 1 mL/kg/hr × (weight - 20 kg)"
        
        # 计算24小时总量
        daily_total = round_number(fluid_rate * 24)
        
        # 生成解释
        explanation = self._generate_explanation(weight, fluid_rate, formula, rule, daily_total, weight_value, weight_unit)
        
        return CalculationResult(
            value=fluid_rate,
            unit="mL/hr",
            explanation=explanation,
            metadata={
                "weight_kg": weight,
                "fluid_rate_ml_per_hr": fluid_rate,
                "daily_total_ml": daily_total,
                "formula": formula,
                "rule": rule,
                "original_weight": weight_value,
                "weight_unit": weight_unit or "kg"
            }
        )
    
    def _generate_explanation(self, weight: float, fluid_rate: float, formula: str, rule: str, daily_total: float, original_weight: float, weight_unit: str) -> str:
        """生成计算解释"""
        explanation = f"""Maintenance Fluid Calculation using the Holliday-Segar method:

{rule}

Patient weight: {original_weight} {weight_unit or 'kg'}"""

        # 如果需要单位转换，显示转换信息
        if weight_unit and weight_unit.lower() not in ["kg", ""]:
            explanation += f" (converted to: {weight:.2f} kg)"
        
        explanation += f"""

Calculation: {formula} = {fluid_rate} mL/hr

Daily total: {fluid_rate} mL/hr × 24 hours = {daily_total} mL/day

The patient's maintenance fluid requirement is {fluid_rate} mL/hr."""
        
        return explanation
