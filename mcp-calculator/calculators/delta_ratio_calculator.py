"""
Delta Ratio Calculator
Delta Ratio 计算器的 FastMCP 2.0 实现
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


@register_calculator("delta_ratio")
class DeltaRatioCalculator(BaseCalculator):
    """Delta Ratio 计算器实现"""
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=64,
            name="Delta Ratio",
            category="laboratory",
            description="Calculate delta ratio: delta gap / (24 - bicarbonate)",
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
                    max_value=35,
                    description="Bicarbonate level in mEq/L"
                )
            ]
        )
    
    def validate_parameters(self, params: Dict[str, Any]) -> ValidationResult:
        """验证输入参数"""
        errors = []
        
        # 获取参数定义
        param_defs = {p.name: p for p in self.get_info().parameters}
        
        # 检查必需参数
        for param_name, param_def in param_defs.items():
            if param_def.required and param_name not in params:
                errors.append(f"Missing required parameter: {param_name}")
        
        if errors:
            return ValidationResult(is_valid=False, errors=errors)
        
        # 验证数值范围
        if "sodium" in params:
            try:
                sodium = float(params["sodium"])
                if not (120 <= sodium <= 160):
                    errors.append("Sodium must be between 120 and 160 mEq/L")
            except (ValueError, TypeError):
                errors.append("Sodium must be a valid number")
                
        if "chloride" in params:
            try:
                chloride = float(params["chloride"])
                if not (80 <= chloride <= 120):
                    errors.append("Chloride must be between 80 and 120 mEq/L")
            except (ValueError, TypeError):
                errors.append("Chloride must be a valid number")
                
        if "bicarbonate" in params:
            try:
                bicarbonate = float(params["bicarbonate"])
                if not (5 <= bicarbonate <= 35):
                    errors.append("Bicarbonate must be between 5 and 35 mEq/L")
            except (ValueError, TypeError):
                errors.append("Bicarbonate must be a valid number")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )
    
    def calculate(self, params: Dict[str, Any]) -> CalculationResult:
        """计算 Delta Ratio"""
        # 验证参数
        validation = self.validate_parameters(params)
        if not validation.is_valid:
            raise ValueError(f"Invalid parameters: {', '.join(validation.errors)}")
        
        # 获取参数值
        sodium = float(params["sodium"])
        chloride = float(params["chloride"])
        bicarbonate = float(params["bicarbonate"])
        
        # 先计算阴离子间隙
        anion_gap = sodium - (chloride + bicarbonate)
        anion_gap_rounded = round_number(anion_gap)
        
        # 计算 Delta Gap
        delta_gap = anion_gap - 12.0
        delta_gap_rounded = round_number(delta_gap)
        
        # 计算 Delta Ratio
        denominator = 24 - bicarbonate
        if denominator == 0:
            raise ValueError("Cannot calculate delta ratio: denominator (24 - bicarbonate) equals zero")
        
        delta_ratio = delta_gap / denominator
        delta_ratio_rounded = round_number(delta_ratio)
        
        # 构建解释说明
        explanation = (
            f"Delta Ratio calculation:\n"
            f"Step 1: Calculate anion gap\n"
            f"Anion Gap = Na+ - (Cl- + HCO3-)\n"
            f"Anion Gap = {sodium} - ({chloride} + {bicarbonate})\n"
            f"Anion Gap = {anion_gap_rounded} mEq/L\n\n"
            f"Step 2: Calculate delta gap\n"
            f"Delta Gap = Anion Gap - 12\n"
            f"Delta Gap = {anion_gap_rounded} - 12 = {delta_gap_rounded} mEq/L\n\n"
            f"Step 3: Calculate delta ratio\n"
            f"Delta Ratio = Delta Gap / (24 - HCO3-)\n"
            f"Delta Ratio = {delta_gap_rounded} / (24 - {bicarbonate})\n"
            f"Delta Ratio = {delta_gap_rounded} / {denominator}\n"
            f"Delta Ratio = {delta_ratio_rounded}"
        )
        
        # 添加临床意义
        if delta_ratio_rounded < 1:
            clinical_note = "Delta ratio < 1: suggests hyperchloremic normal anion gap acidosis"
        elif delta_ratio_rounded > 2:
            clinical_note = "Delta ratio > 2: suggests metabolic alkalosis or chronic respiratory acidosis"
        else:
            clinical_note = "Delta ratio 1-2: suggests pure anion gap acidosis"
        
        return CalculationResult(
            value=delta_ratio_rounded,
            unit="",
            explanation=explanation,
            metadata={
                "sodium": sodium,
                "chloride": chloride,
                "bicarbonate": bicarbonate,
                "anion_gap": anion_gap_rounded,
                "delta_gap": delta_gap_rounded,
                "clinical_note": clinical_note
            }
        )
