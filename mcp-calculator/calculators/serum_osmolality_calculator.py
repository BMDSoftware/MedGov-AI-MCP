"""
Serum Osmolality Calculator
血清渗透压计算器的 FastMCP 2.0 实现
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


@register_calculator("serum_osmolality")
class SerumOsmolalityCalculator(BaseCalculator):
    """血清渗透压计算器实现"""
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=30,
            name="Serum Osmolality",
            category="laboratory",
            description="Calculate serum osmolality using the formula: 2×Na + (BUN/2.8) + (Glucose/18)",
            parameters=[
                Parameter(
                    name="sodium",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="mmol/L",
                    min_value=120,
                    max_value=160,
                    description="Sodium level in mmol/L"
                ),
                Parameter(
                    name="bun", 
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="mg/dL",
                    min_value=5,
                    max_value=150,
                    description="Blood urea nitrogen (BUN) in mg/dL"
                ),
                Parameter(
                    name="glucose",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="mg/dL",
                    min_value=50,
                    max_value=500,
                    description="Glucose level in mg/dL"
                )
            ]
        )
    
    def validate_parameters(self, params: Dict[str, Any]) -> ValidationResult:
        """验证输入参数"""
        errors = []
        
        # 验证钠离子
        if "sodium" not in params:
            errors.append("Sodium is required")
        else:
            try:
                sodium = float(params["sodium"])
                if sodium < 120 or sodium > 160:
                    errors.append("Sodium must be between 120 and 160 mmol/L")
            except (ValueError, TypeError):
                errors.append("Sodium must be a valid number")
            
        # 验证BUN
        if "bun" not in params:
            errors.append("BUN is required")
        else:
            try:
                bun = float(params["bun"])
                if bun < 5 or bun > 150:
                    errors.append("BUN must be between 5 and 150 mg/dL")
            except (ValueError, TypeError):
                errors.append("BUN must be a valid number")
            
        # 验证葡萄糖
        if "glucose" not in params:
            errors.append("Glucose is required")
        else:
            try:
                glucose = float(params["glucose"])
                if glucose < 50 or glucose > 500:
                    errors.append("Glucose must be between 50 and 500 mg/dL")
            except (ValueError, TypeError):
                errors.append("Glucose must be a valid number")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )
    
    def calculate(self, params: Dict[str, Any]) -> CalculationResult:
        """计算血清渗透压"""
        # 验证参数
        validation = self.validate_parameters(params)
        if not validation.is_valid:
            raise ValueError(f"Invalid parameters: {', '.join(validation.errors)}")
        
        # 获取参数值
        sodium = float(params["sodium"])
        bun = float(params["bun"])
        glucose = float(params["glucose"])
        
        # 计算血清渗透压
        # 公式: 2 × Na + (BUN / 2.8) + (Glucose / 18)
        serum_osmolality = 2 * sodium + (bun / 2.8) + (glucose / 18)
        serum_osmolality_rounded = round_number(serum_osmolality)
        
        # 构建解释说明
        explanation = (
            f"Serum Osmolality calculation:\n"
            f"Formula: 2 × Na + (BUN / 2.8) + (Glucose / 18)\n"
            f"Where:\n"
            f"- Na = {sodium} mmol/L\n"
            f"- BUN = {bun} mg/dL\n"
            f"- Glucose = {glucose} mg/dL\n\n"
            f"Calculation:\n"
            f"Serum Osmolality = 2 × {sodium} + ({bun} / 2.8) + ({glucose} / 18)\n"
            f"Serum Osmolality = {2 * sodium} + {round_number(bun / 2.8)} + {round_number(glucose / 18)}\n"
            f"Serum Osmolality = {serum_osmolality_rounded} mOsm/kg"
        )
        
        # 添加临床意义
        if serum_osmolality_rounded < 280:
            clinical_note = "Below normal range (280-295 mOsm/kg) - possible hyponatremia or overhydration"
        elif serum_osmolality_rounded > 295:
            clinical_note = "Above normal range (280-295 mOsm/kg) - possible dehydration or hypernatremia"
        else:
            clinical_note = "Within normal range (280-295 mOsm/kg)"
        
        return CalculationResult(
            value=serum_osmolality_rounded,
            unit="mOsm/kg",
            explanation=explanation,
            metadata={
                "sodium": sodium,
                "bun": bun,
                "glucose": glucose,
                "clinical_note": clinical_note
            }
        )
