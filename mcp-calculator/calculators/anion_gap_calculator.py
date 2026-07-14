"""
Anion Gap Calculator
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


@register_calculator("anion_gap")
class AnionGapCalculator(BaseCalculator):
    """阴离子间隙计算器实现"""
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=39,
            name="Anion Gap",
            category="laboratory",
            description="Calculate anion gap from sodium, chloride, and bicarbonate levels",
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
                    max_value=130,
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
                errors.append("Sodium level must be between 110 and 180 mEq/L")
        
        if "chloride" in parameters:
            chloride = float(parameters["chloride"])
            if not (60 <= chloride <= 130):
                errors.append("Chloride level must be between 60 and 130 mEq/L")
        
        if "bicarbonate" in parameters:
            bicarbonate = float(parameters["bicarbonate"])
            if not (2 <= bicarbonate <= 45):
                errors.append("Bicarbonate level must be between 2 and 45 mEq/L")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )
    
    def calculate(self, parameters: Dict[str, Any]) -> CalculationResult:
        """执行计算"""
        sodium = float(parameters["sodium"])
        chloride = float(parameters["chloride"])
        bicarbonate = float(parameters["bicarbonate"])
        
        # 计算阴离子间隙: 阴离子间隙 = 钠 - (氯 + 碳酸氢盐)
        anion_gap = round_number(sodium - (chloride + bicarbonate))
        
        # 生成解释
        explanation = self._generate_explanation(sodium, chloride, bicarbonate, anion_gap)
        
        return CalculationResult(
            value=anion_gap,
            unit="mEq/L",
            explanation=explanation,
            metadata={
                "sodium": sodium,
                "chloride": chloride,
                "bicarbonate": bicarbonate,
                "formula": "Anion Gap = Sodium - (Chloride + Bicarbonate)"
            }
        )
    
    def _generate_explanation(self, sodium: float, chloride: float, bicarbonate: float, anion_gap: float) -> str:
        """生成计算解释"""
        explanation = "The formula for computing a patient's anion gap is: sodium (mEq/L) - (chloride (mEq/L) + bicarbonate (mEq/L)).\n"
        explanation += f"Plugging in these values into the anion gap formula gives us {sodium} mEq/L - ({chloride} mEq/L + {bicarbonate} mEq/L) = {anion_gap} mEq/L. "
        explanation += f"Hence, the patient's anion gap is {anion_gap} mEq/L."
        
        return explanation
