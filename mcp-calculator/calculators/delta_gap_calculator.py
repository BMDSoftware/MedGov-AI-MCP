"""
Delta Gap Calculator
Delta Gap 计算器的 FastMCP 2.0 实现
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


@register_calculator("delta_gap")
class DeltaGapCalculator(BaseCalculator):
    """Delta Gap 计算器实现"""
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=63,
            name="Delta Gap",
            category="laboratory",
            description="Calculate delta gap from anion gap (anion gap - 12)",
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
                    min_value=5,
                    max_value=50,
                    description="Bicarbonate level in mEq/L"
                )
            ]
        )
    
    def validate_parameters(self, params: Dict[str, Any]) -> ValidationResult:
        """验证输入参数"""
        errors = []
        
        # 验证钠离子
        try:
            sodium = params.get("sodium")
            if sodium is None:
                errors.append("Sodium is required")
            else:
                sodium_val = float(sodium)
                if sodium_val < 120 or sodium_val > 160:
                    errors.append("Sodium must be between 120 and 160 mEq/L")
        except (ValueError, TypeError):
            errors.append("Sodium must be a valid number")
            
        # 验证氯离子
        try:
            chloride = params.get("chloride")
            if chloride is None:
                errors.append("Chloride is required")
            else:
                chloride_val = float(chloride)
                if chloride_val < 80 or chloride_val > 120:
                    errors.append("Chloride must be between 80 and 120 mEq/L")
        except (ValueError, TypeError):
            errors.append("Chloride must be a valid number")
            
        # 验证碳酸氢盐
        try:
            bicarbonate = params.get("bicarbonate")
            if bicarbonate is None:
                errors.append("Bicarbonate is required")
            else:
                bicarbonate_val = float(bicarbonate)
                if bicarbonate_val < 5 or bicarbonate_val > 50:
                    errors.append("Bicarbonate must be between 5 and 50 mEq/L")
        except (ValueError, TypeError):
            errors.append("Bicarbonate must be a valid number")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )
    
    def calculate(self, params: Dict[str, Any]) -> CalculationResult:
        """计算 Delta Gap"""
        # 验证参数
        validation = self.validate_parameters(params)
        if not validation.is_valid:
            raise ValueError(f"Invalid parameters: {', '.join(validation.errors)}")
        
        # 获取参数值
        sodium = float(params.get("sodium"))
        chloride = float(params.get("chloride"))
        bicarbonate = float(params.get("bicarbonate"))
        
        # 先计算阴离子间隙
        anion_gap = sodium - (chloride + bicarbonate)
        anion_gap_rounded = round_number(anion_gap)
        
        # 计算 Delta Gap
        delta_gap = anion_gap - 12.0
        delta_gap_rounded = round_number(delta_gap)
        
        # 构建解释说明
        explanation = (
            f"Delta Gap calculation:\n"
            f"Step 1: Calculate anion gap\n"
            f"Anion Gap = Na⁺ - (Cl⁻ + HCO₃⁻)\n"
            f"Anion Gap = {sodium} - ({chloride} + {bicarbonate})\n"
            f"Anion Gap = {sodium} - {chloride + bicarbonate}\n"
            f"Anion Gap = {anion_gap_rounded} mEq/L\n\n"
            f"Step 2: Calculate delta gap\n"
            f"Delta Gap = Anion Gap - 12\n"
            f"Delta Gap = {anion_gap_rounded} - 12\n"
            f"Delta Gap = {delta_gap_rounded} mEq/L"
        )
        
        # 添加临床意义
        if delta_gap_rounded < 0:
            clinical_note = "Negative delta gap suggests hyperchloremic acidosis"
        elif delta_gap_rounded > 6:
            clinical_note = "Elevated delta gap suggests high anion gap metabolic acidosis"
        else:
            clinical_note = "Normal delta gap range"
        
        return CalculationResult(
            value=delta_gap_rounded,
            unit="mEq/L",
            explanation=explanation,
            metadata={
                "sodium": sodium,
                "chloride": chloride,
                "bicarbonate": bicarbonate,
                "anion_gap": anion_gap_rounded,
                "clinical_note": clinical_note
            }
        )
