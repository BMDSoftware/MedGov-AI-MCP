"""
Albumin Corrected Anion Gap Calculator
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


@register_calculator("albumin_corrected_anion_gap")
class AlbuminCorrectedAnionGapCalculator(BaseCalculator):
    """白蛋白校正阴离子间隙计算器实现"""
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=65,
            name="Albumin Corrected Anion Gap",
            category="laboratory",
            description="Calculate albumin-corrected anion gap",
            parameters=[
                Parameter(
                    name="sodium",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="mEq/L",
                    min_value=110,
                    max_value=180,
                    description="Sodium level in mEq/L"
                ),
                Parameter(
                    name="chloride", 
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="mEq/L",
                    min_value=60,
                    max_value=135,
                    description="Chloride level in mEq/L"
                ),
                Parameter(
                    name="bicarbonate",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="mEq/L",
                    min_value=2,
                    max_value=45,
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
        
        # 获取参数定义
        param_defs = {p.name: p for p in self.get_info().parameters}
        
        # 检查必需参数
        for param_name, param_def in param_defs.items():
            if param_def.required and param_name not in parameters:
                errors.append(f"Missing required parameter: {param_name}")
        
        if errors:
            return ValidationResult(is_valid=False, errors=errors)
        
        # 验证数值范围
        if "sodium" in parameters:
            sodium = float(parameters["sodium"])
            if not (110 <= sodium <= 180):
                errors.append("Sodium must be between 110 and 180 mEq/L")
        
        if "chloride" in parameters:
            chloride = float(parameters["chloride"])
            if not (60 <= chloride <= 135):
                errors.append("Chloride must be between 60 and 135 mEq/L")
        
        if "bicarbonate" in parameters:
            bicarbonate = float(parameters["bicarbonate"])
            if not (2 <= bicarbonate <= 45):
                errors.append("Bicarbonate must be between 2 and 45 mEq/L")
        
        if "albumin" in parameters:
            albumin = float(parameters["albumin"])
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
        
        # 生成解释
        explanation = self._generate_explanation(sodium, chloride, bicarbonate, albumin, anion_gap, corrected_anion_gap)
        
        return CalculationResult(
            value=corrected_anion_gap,
            unit="mEq/L",
            explanation=explanation,
            metadata={
                "sodium": sodium,
                "chloride": chloride,
                "bicarbonate": bicarbonate,
                "albumin": albumin,
                "uncorrected_anion_gap": anion_gap,
                "formula": "Corrected AG = AG + 2.5 * (4 - albumin)"
            }
        )
    
    def _generate_explanation(self, sodium: float, chloride: float, bicarbonate: float, 
                            albumin: float, anion_gap: float, corrected_anion_gap: float) -> str:
        """生成计算解释"""
        explanation = "The formula for computing a patient's albumin corrected anion gap is: anion_gap (in mEq/L) + 2.5 * (4 - albumin (in g/dL)).\n\n"
        
        explanation += f"First, we calculate the standard anion gap using the formula: Anion Gap = Sodium - (Chloride + Bicarbonate).\n"
        explanation += f"The patient's sodium level is {sodium} mEq/L.\n"
        explanation += f"The patient's chloride level is {chloride} mEq/L.\n"
        explanation += f"The patient's bicarbonate level is {bicarbonate} mEq/L.\n"
        explanation += f"Therefore, the anion gap = {sodium} - ({chloride} + {bicarbonate}) = {anion_gap} mEq/L.\n\n"
        
        explanation += f"The patient's albumin level is {albumin} g/dL.\n"
        explanation += f"Plugging in these values into the albumin corrected anion gap formula, we get {anion_gap} (mEq/L) + 2.5 * (4 - {albumin} (in g/dL)) = {corrected_anion_gap} mEq/L.\n"
        explanation += f"Hence, the patient's albumin corrected anion gap is {corrected_anion_gap} mEq/L."
        
        return explanation
