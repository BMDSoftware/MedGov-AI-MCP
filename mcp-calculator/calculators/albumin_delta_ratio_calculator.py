"""
Albumin Delta Ratio Calculator
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


@register_calculator("albumin_delta_ratio")
class AlbuminDeltaRatioCalculator(BaseCalculator):
    """白蛋白校正Delta Ratio计算器实现"""
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=67,
            name="Albumin Delta Ratio",
            category="laboratory",
            description="Calculate albumin-corrected delta ratio",
            parameters=[
                Parameter(
                    name="sodium",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="mEq/L",
                    min_value=120,
                    max_value=160,
                    description="Sodium level in mEq/L"
                ),
                Parameter(
                    name="chloride", 
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="mEq/L",
                    min_value=80,
                    max_value=120,
                    description="Chloride level in mEq/L"
                ),
                Parameter(
                    name="bicarbonate",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="mEq/L",
                    min_value=1,
                    max_value=60,
                    description="Bicarbonate level in mEq/L"
                ),
                Parameter(
                    name="albumin",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="g/dL",
                    min_value=1.0,
                    max_value=6.0,
                    description="Albumin level in g/dL"
                )
            ]
        )
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> ValidationResult:
        """验证参数"""
        errors = []
        
        # 检查必需参数
        required_params = ["sodium", "chloride", "bicarbonate", "albumin"]
        for param in required_params:
            if param not in parameters:
                errors.append(f"Missing required parameter: {param}")
        
        if errors:
            return ValidationResult(is_valid=False, errors=errors)
        
        # 获取参数值
        sodium = float(parameters["sodium"])
        chloride = float(parameters["chloride"])
        bicarbonate = float(parameters["bicarbonate"])
        albumin = float(parameters["albumin"])
        
        # 验证钠离子范围
        if not (120 <= sodium <= 160):
            errors.append("Sodium must be between 120 and 160 mEq/L")
        
        # 验证氯离子范围
        if not (80 <= chloride <= 120):
            errors.append("Chloride must be between 80 and 120 mEq/L")
        
        # 验证碳酸氢盐范围
        if not (1 <= bicarbonate <= 60):
            errors.append("Bicarbonate must be between 1 and 60 mEq/L")
        
        # 验证白蛋白范围
        if not (1.0 <= albumin <= 6.0):
            errors.append("Albumin must be between 1.0 and 6.0 g/dL")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )
    
    def calculate(self, parameters: Dict[str, Any]) -> CalculationResult:
        """执行计算"""
        sodium = float(parameters["sodium"])
        chloride = float(parameters["chloride"])
        bicarbonate = float(parameters["bicarbonate"])
        albumin = float(parameters["albumin"])
        
        # 计算标准阴离子间隙
        anion_gap = round_number(sodium - (chloride + bicarbonate))
        
        # 计算白蛋白校正阴离子间隙
        corrected_anion_gap = round_number(anion_gap + 2.5 * (4 - albumin))
        
        # 计算白蛋白校正Delta Gap
        corrected_delta_gap = round_number(corrected_anion_gap - 12.0)
        
        # 计算白蛋白校正Delta Ratio
        denominator = 24 - bicarbonate
        corrected_delta_ratio = round_number(corrected_delta_gap / denominator)
        
        # 生成解释
        explanation = self._generate_explanation(sodium, chloride, bicarbonate, albumin, 
                                               anion_gap, corrected_anion_gap, corrected_delta_gap, 
                                               corrected_delta_ratio, denominator)
        
        return CalculationResult(
            value=corrected_delta_ratio,
            unit="ratio",
            explanation=explanation,
            metadata={
                "sodium": sodium,
                "chloride": chloride,
                "bicarbonate": bicarbonate,
                "albumin": albumin,
                "uncorrected_anion_gap": anion_gap,
                "corrected_anion_gap": corrected_anion_gap,
                "corrected_delta_gap": corrected_delta_gap,
                "formula": "Corrected Delta Ratio = Corrected Delta Gap / (24 - bicarbonate)"
            }
        )
    
    def _generate_explanation(self, sodium: float, chloride: float, bicarbonate: float, 
                            albumin: float, anion_gap: float, corrected_anion_gap: float, 
                            corrected_delta_gap: float, corrected_delta_ratio: float, 
                            denominator: float) -> str:
        """生成计算解释"""
        explanation = "The formula for computing the albumin corrected delta ratio is albumin corrected delta gap (mEq/L)/(24 - bicarbonate mEq/L).\n\n"
        
        explanation += "First, we calculate the albumin corrected delta gap:\n"
        explanation += f"The patient's sodium level is {sodium} mEq/L.\n"
        explanation += f"The patient's chloride level is {chloride} mEq/L.\n"
        explanation += f"The patient's bicarbonate level is {bicarbonate} mEq/L.\n"
        explanation += f"Therefore, the anion gap = {sodium} - ({chloride} + {bicarbonate}) = {anion_gap} mEq/L.\n\n"
        
        explanation += f"The patient's albumin level is {albumin} g/dL.\n"
        explanation += f"The albumin corrected anion gap = {anion_gap} + 2.5 * (4 - {albumin}) = {corrected_anion_gap} mEq/L.\n"
        explanation += f"The albumin corrected delta gap = {corrected_anion_gap} - 12 = {corrected_delta_gap} mEq/L.\n\n"
        
        explanation += f"Plugging in the albumin corrected delta gap and the bicarbonate concentration into the albumin corrected delta ratio formula, we get {corrected_delta_gap} mEq/L / {denominator} mEq/L = {corrected_delta_ratio}.\n"
        explanation += f"The patient's albumin corrected delta ratio is {corrected_delta_ratio}."
        
        return explanation
