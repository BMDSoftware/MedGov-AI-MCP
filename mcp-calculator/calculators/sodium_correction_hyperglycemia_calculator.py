"""
Sodium Correction for Hyperglycemia Calculator
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


@register_calculator("sodium_correction_hyperglycemia")
class SodiumCorrectionHyperglycemiaCalculator(BaseCalculator):
    """高血糖钠校正计算器实现"""
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=26,
            name="Sodium Correction for Hyperglycemia",
            category="laboratory",
            description="Calculate corrected sodium concentration in hyperglycemic patients",
            parameters=[
                Parameter(
                    name="sodium",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="mEq/L",
                    min_value=100,
                    max_value=180,
                    description="Measured serum sodium in mEq/L"
                ),
                Parameter(
                    name="glucose",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="mg/dL",
                    min_value=50,
                    max_value=1000,
                    description="Serum glucose in mg/dL"
                )
            ]
        )
    
    def _parse_parameter(self, value: Any) -> tuple[float, str]:
        """解析参数，支持字符串格式如 '550mg/dL' 或 '138mEq/L'"""
        if isinstance(value, (int, float)):
            return float(value), ""
        
        if isinstance(value, str):
            import re
            # 匹配数字和单位
            match = re.match(r'^([0-9]*\.?[0-9]+)\s*([a-zA-Z/]+)$', value.strip())
            if match:
                num_str, unit = match.groups()
                return float(num_str), unit.lower()
        
        raise ValueError(f"Cannot parse parameter value: {value}")
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> ValidationResult:
        """验证输入参数"""
        errors = []
        
        # 获取参数值
        sodium_raw = parameters.get("sodium")
        glucose_raw = parameters.get("glucose")
        
        # 验证必需参数
        if sodium_raw is None:
            errors.append("sodium is required")
        else:
            try:
                sodium, sodium_unit = self._parse_parameter(sodium_raw)
                if sodium <= 0:
                    errors.append("sodium must be a positive number")
            except ValueError:
                errors.append(f"Invalid sodium format: {sodium_raw}")
                
        if glucose_raw is None:
            errors.append("glucose is required")
        else:
            try:
                glucose, glucose_unit = self._parse_parameter(glucose_raw)
                if glucose <= 0:
                    errors.append("glucose must be a positive number")
            except ValueError:
                errors.append(f"Invalid glucose format: {glucose_raw}")
            
        return ValidationResult(is_valid=len(errors) == 0, errors=errors)
    
    def _convert_glucose_to_mgdl(self, value: float, unit: str) -> float:
        """将glucose转换为mg/dL"""
        unit = unit.lower()
        if unit == "mmol/l":
            return value * 18.0182  # 1 mmol/L = 18.0182 mg/dL
        elif unit == "mg/dl":
            return value
        else:
            return value  # 假设默认为mg/dL
    
    def _convert_sodium_to_meql(self, value: float, unit: str) -> float:
        """将sodium转换为mEq/L"""
        unit = unit.lower()
        if unit in ["mmol/l", "meq/l"]:
            return value  # mmol/L和mEq/L在钠离子情况下数值相同
        elif unit == "meq/dl":
            return value * 10  # mEq/dL转换为mEq/L
        else:
            return value  # 假设默认为mEq/L
    
    def calculate(self, parameters: Dict[str, Any]) -> CalculationResult:
        """计算高血糖钠校正"""
        # 解析参数值
        sodium_raw = parameters["sodium"]
        glucose_raw = parameters["glucose"]
        
        sodium_value, sodium_unit = self._parse_parameter(sodium_raw)
        glucose_value, glucose_unit = self._parse_parameter(glucose_raw)
        
        # 转换为标准单位
        sodium = self._convert_sodium_to_meql(sodium_value, sodium_unit)
        glucose = self._convert_glucose_to_mgdl(glucose_value, glucose_unit)
        
        # 计算校正钠浓度
        # 公式: 校正钠 = 测定钠 + 0.024 × (血糖 - 100)
        corrected_sodium = round_number(sodium + 0.024 * (glucose - 100))
        
        # 生成解释
        explanation = self._generate_explanation(sodium, glucose, corrected_sodium)
        
        # 解释结果
        interpretation = self._interpret_result(sodium, corrected_sodium, glucose)
        
        return CalculationResult(
            value=corrected_sodium,
            unit="mEq/L",
            explanation=explanation,
            metadata={
                "measured_sodium_mEq_per_L": sodium,
                "serum_glucose_mg_per_dL": glucose,
                "corrected_sodium_mEq_per_L": corrected_sodium,
                "correction_factor": 0.024,
                "glucose_excess": glucose - 100,
                "sodium_correction": round_number(0.024 * (glucose - 100)),
                "interpretation": interpretation
            }
        )
    
    def _generate_explanation(self, sodium: float, glucose: float, corrected_sodium: float) -> str:
        """生成计算解释"""
        glucose_excess = glucose - 100
        sodium_correction = round_number(0.024 * glucose_excess)
        
        explanation = f"""Sodium Correction for Hyperglycemia

The formula for sodium correction in hyperglycemia is:
Corrected Sodium = Measured Sodium + 0.024 × (Serum Glucose - 100)

Where:
- Measured Sodium is in mEq/L
- Serum Glucose is in mg/dL

Given values:
- Measured sodium: {sodium} mEq/L
- Serum glucose: {glucose} mg/dL

Calculation:
Glucose excess above 100 mg/dL: {glucose} - 100 = {glucose_excess} mg/dL
Sodium correction: 0.024 × {glucose_excess} = {sodium_correction} mEq/L

Corrected sodium: {sodium} + {sodium_correction} = {corrected_sodium} mEq/L

Therefore, the patient's corrected sodium concentration is {corrected_sodium} mEq/L."""
        
        return explanation
    
    def _interpret_result(self, measured_sodium: float, corrected_sodium: float, glucose: float) -> str:
        """解释结果"""
        if glucose <= 100:
            return "No correction needed as glucose is not elevated"
        elif corrected_sodium < 135:
            return "Corrected sodium indicates hyponatremia"
        elif corrected_sodium > 145:
            return "Corrected sodium indicates hypernatremia"
        else:
            return "Corrected sodium is within normal range"
