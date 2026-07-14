"""
HOMA-IR Calculator
胰岛素抵抗指数计算器的 FastMCP 2.0 实现
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


@register_calculator("homa_ir")
class HOMAIRCalculator(BaseCalculator):
    """HOMA-IR 胰岛素抵抗指数计算器实现"""
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=31,
            name="HOMA-IR (Insulin Resistance Index)",
            category="laboratory",
            description="Calculate HOMA-IR using the formula: (insulin × glucose) / 405",
            parameters=[
                Parameter(
                    name="insulin",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="µIU/mL",
                    min_value=1,
                    max_value=100,
                    description="Fasting insulin level in µIU/mL"
                ),
                Parameter(
                    name="glucose", 
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="mg/dL",
                    min_value=50,
                    max_value=400,
                    description="Fasting glucose level in mg/dL"
                )
            ]
        )
    
    def validate_parameters(self, params: Dict[str, Any]) -> ValidationResult:
        """验证输入参数"""
        errors = []
        
        # 验证胰岛素
        if "insulin" not in params:
            errors.append("Insulin is required")
        else:
            try:
                insulin = float(params["insulin"])
                if insulin < 1 or insulin > 100:
                    errors.append("Insulin must be between 1 and 100 µIU/mL")
            except (ValueError, TypeError):
                errors.append("Insulin must be a valid number")
            
        # 验证葡萄糖
        if "glucose" not in params:
            errors.append("Glucose is required")
        else:
            try:
                glucose = float(params["glucose"])
                if glucose < 50 or glucose > 400:
                    errors.append("Glucose must be between 50 and 400 mg/dL")
            except (ValueError, TypeError):
                errors.append("Glucose must be a valid number")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )
    
    def calculate(self, params: Dict[str, Any]) -> CalculationResult:
        """计算 HOMA-IR"""
        # 验证参数
        validation = self.validate_parameters(params)
        if not validation.is_valid:
            raise ValueError(f"Invalid parameters: {', '.join(validation.errors)}")
        
        # 获取参数值
        insulin = float(params["insulin"])
        glucose = float(params["glucose"])
        
        # 计算 HOMA-IR
        # 公式: (insulin × glucose) / 405
        homa_ir = (insulin * glucose) / 405
        homa_ir_rounded = round_number(homa_ir)
        
        # 构建解释说明
        explanation = (
            f"HOMA-IR (Homeostatic Model Assessment of Insulin Resistance) calculation:\n"
            f"Formula: (Insulin × Glucose) / 405\n"
            f"Where:\n"
            f"- Insulin = {insulin} µIU/mL (fasting)\n"
            f"- Glucose = {glucose} mg/dL (fasting)\n\n"
            f"Calculation:\n"
            f"HOMA-IR = ({insulin} × {glucose}) / 405\n"
            f"HOMA-IR = {insulin * glucose} / 405\n"
            f"HOMA-IR = {homa_ir_rounded}"
        )
        
        # 添加临床意义
        if homa_ir_rounded < 1.0:
            clinical_note = "Normal insulin sensitivity"
        elif homa_ir_rounded < 2.5:
            clinical_note = "Early insulin resistance"
        elif homa_ir_rounded < 5.0:
            clinical_note = "Significant insulin resistance"
        else:
            clinical_note = "Severe insulin resistance"
        
        return CalculationResult(
            value=homa_ir_rounded,
            unit="",
            explanation=explanation,
            metadata={
                "insulin": insulin,
                "glucose": glucose,
                "clinical_note": clinical_note,
                "interpretation": "Higher values indicate greater insulin resistance"
            }
        )
