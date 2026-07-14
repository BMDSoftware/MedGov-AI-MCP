"""
Fractional Excretion of Sodium (FENa) Calculator
钠排泄分数计算器的 FastMCP 2.0 实现
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


@register_calculator("fena")
class FENaCalculator(BaseCalculator):
    """钠排泄分数计算器实现"""
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=40,
            name="Fractional Excretion of Sodium (FENa)",
            category="nephrology",
            description="Calculate FENa to help differentiate causes of acute kidney injury",
            parameters=[
                Parameter(
                    name="serum_sodium",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="mEq/L",
                    min_value=120,
                    max_value=160,
                    description="Serum sodium level in mEq/L"
                ),
                Parameter(
                    name="serum_creatinine", 
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="mg/dL",
                    min_value=0.5,
                    max_value=15,
                    description="Serum creatinine level in mg/dL"
                ),
                Parameter(
                    name="urine_sodium",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="mEq/L",
                    min_value=5,
                    max_value=200,
                    description="Urine sodium level in mEq/L"
                ),
                Parameter(
                    name="urine_creatinine",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="mg/dL",
                    min_value=10,
                    max_value=300,
                    description="Urine creatinine level in mg/dL"
                )
            ]
        )
    
    def validate_parameters(self, params: Dict[str, Any]) -> ValidationResult:
        """验证输入参数"""
        errors = []
        
        # 获取参数定义
        param_defs = {p.name: p for p in self.get_info().parameters}
        
        # 验证血清钠
        serum_sodium_def = param_defs["serum_sodium"]
        serum_sodium = params.get("serum_sodium")
        if serum_sodium is None:
            errors.append("Serum sodium is required")
        else:
            try:
                serum_sodium = float(serum_sodium)
                range_error = self.validate_numeric_range(serum_sodium, serum_sodium_def)
                if range_error:
                    errors.append(range_error)
            except (ValueError, TypeError):
                errors.append("Serum sodium must be a valid number")
            
        # 验证血清肌酐
        serum_creatinine_def = param_defs["serum_creatinine"]
        serum_creatinine = params.get("serum_creatinine")
        if serum_creatinine is None:
            errors.append("Serum creatinine is required")
        else:
            try:
                serum_creatinine = float(serum_creatinine)
                range_error = self.validate_numeric_range(serum_creatinine, serum_creatinine_def)
                if range_error:
                    errors.append(range_error)
            except (ValueError, TypeError):
                errors.append("Serum creatinine must be a valid number")
            
        # 验证尿钠
        urine_sodium_def = param_defs["urine_sodium"]
        urine_sodium = params.get("urine_sodium")
        if urine_sodium is None:
            errors.append("Urine sodium is required")
        else:
            try:
                urine_sodium = float(urine_sodium)
                range_error = self.validate_numeric_range(urine_sodium, urine_sodium_def)
                if range_error:
                    errors.append(range_error)
            except (ValueError, TypeError):
                errors.append("Urine sodium must be a valid number")
            
        # 验证尿肌酐
        urine_creatinine_def = param_defs["urine_creatinine"]
        urine_creatinine = params.get("urine_creatinine")
        if urine_creatinine is None:
            errors.append("Urine creatinine is required")
        else:
            try:
                urine_creatinine = float(urine_creatinine)
                range_error = self.validate_numeric_range(urine_creatinine, urine_creatinine_def)
                if range_error:
                    errors.append(range_error)
            except (ValueError, TypeError):
                errors.append("Urine creatinine must be a valid number")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )
    
    def calculate(self, params: Dict[str, Any]) -> CalculationResult:
        """计算钠排泄分数"""
        # 验证参数
        validation = self.validate_parameters(params)
        if not validation.is_valid:
            raise ValueError(f"Invalid parameters: {', '.join(validation.errors)}")
        
        # 获取参数值
        serum_sodium = float(params["serum_sodium"])
        serum_creatinine = float(params["serum_creatinine"])
        urine_sodium = float(params["urine_sodium"])
        urine_creatinine = float(params["urine_creatinine"])
        
        # 计算 FENa
        # 公式: FENa% = (serum_creatinine × urine_sodium) / (serum_sodium × urine_creatinine) × 100
        denominator = serum_sodium * urine_creatinine
        if denominator == 0:
            raise ValueError("Cannot calculate FENa: denominator equals zero")
        
        fena = (serum_creatinine * urine_sodium) / denominator * 100
        fena_rounded = round_number(fena)
        
        # 构建解释说明
        explanation = (
            f"Fractional Excretion of Sodium (FENa) calculation:\n"
            f"Formula: FENa% = (Serum Cr × Urine Na) / (Serum Na × Urine Cr) × 100\n"
            f"Where:\n"
            f"- Serum Cr = {serum_creatinine} mg/dL\n"
            f"- Urine Na = {urine_sodium} mEq/L\n"
            f"- Serum Na = {serum_sodium} mEq/L\n"
            f"- Urine Cr = {urine_creatinine} mg/dL\n\n"
            f"Calculation:\n"
            f"FENa% = ({serum_creatinine} × {urine_sodium}) / ({serum_sodium} × {urine_creatinine}) × 100\n"
            f"FENa% = {serum_creatinine * urine_sodium} / {denominator} × 100\n"
            f"FENa% = {fena_rounded}%"
        )
        
        # 添加临床意义
        if fena_rounded < 1:
            clinical_note = "FENa < 1%: Suggests prerenal azotemia (volume depletion, heart failure)"
        elif fena_rounded > 2:
            clinical_note = "FENa > 2%: Suggests intrinsic renal disease (acute tubular necrosis)"
        else:
            clinical_note = "FENa 1-2%: Intermediate range, consider clinical context"
        
        return CalculationResult(
            value=fena_rounded,
            unit="%",
            explanation=explanation,
            metadata={
                "serum_sodium": serum_sodium,
                "serum_creatinine": serum_creatinine,
                "urine_sodium": urine_sodium,
                "urine_creatinine": urine_creatinine,
                "clinical_note": clinical_note
            }
        )
