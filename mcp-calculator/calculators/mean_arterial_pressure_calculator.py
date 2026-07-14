"""
Mean Arterial Pressure (MAP) Calculator
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


@register_calculator("mean_arterial_pressure")
class MeanArterialPressureCalculator(BaseCalculator):
    """平均动脉压计算器实现"""
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=5,
            name="Mean Arterial Pressure (MAP)",
            category="cardiovascular",
            description="Calculate mean arterial pressure from systolic and diastolic blood pressure",
            parameters=[
                Parameter(
                    name="systolic_bp",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="mmHg",
                    min_value=50,
                    max_value=300,
                    description="Systolic blood pressure in mmHg"
                ),
                Parameter(
                    name="diastolic_bp", 
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="mmHg",
                    min_value=30,
                    max_value=200,
                    description="Diastolic blood pressure in mmHg"
                )
            ]
        )
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> ValidationResult:
        """验证参数"""
        errors = []
        
        # 获取参数值
        systolic_bp = parameters.get("systolic_bp")
        diastolic_bp = parameters.get("diastolic_bp")
        
        # 检查必需参数
        if systolic_bp is None:
            errors.append("Missing required parameter: systolic_bp")
        if diastolic_bp is None:
            errors.append("Missing required parameter: diastolic_bp")
            
        # 验证数值范围
        if systolic_bp is not None:
            if not (50 <= systolic_bp <= 300):
                errors.append("Systolic blood pressure must be between 50 and 300 mmHg")
        
        if diastolic_bp is not None:
            if not (30 <= diastolic_bp <= 200):
                errors.append("Diastolic blood pressure must be between 30 and 200 mmHg")
        
        # 验证收缩压应大于舒张压
        if systolic_bp is not None and diastolic_bp is not None:
            if systolic_bp <= diastolic_bp:
                errors.append("Systolic blood pressure must be greater than diastolic blood pressure")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )
    
    def calculate(self, parameters: Dict[str, Any]) -> CalculationResult:
        """执行计算"""
        systolic_bp = parameters["systolic_bp"]
        diastolic_bp = parameters["diastolic_bp"]
        
        # 计算平均动脉压: MAP = (2/3) × 舒张压 + (1/3) × 收缩压
        map_value = round_number(2 * diastolic_bp / 3 + systolic_bp / 3)
        
        # 生成解释
        explanation = self._generate_explanation(systolic_bp, diastolic_bp, map_value)
        
        return CalculationResult(
            value=map_value,
            unit="mmHg",
            explanation=explanation,
            metadata={
                "systolic_bp": systolic_bp,
                "diastolic_bp": diastolic_bp,
                "formula": "MAP = (2/3) × Diastolic BP + (1/3) × Systolic BP"
            }
        )
    
    def _generate_explanation(self, systolic_bp: float, diastolic_bp: float, map_value: float) -> str:
        """生成计算解释"""
        explanation = f"The mean arterial pressure is computed by the formula 2/3 * (diastolic blood pressure) + 1/3 * (systolic blood pressure). "
        explanation += f"Plugging in the values, we get 2/3 * {diastolic_bp} mmHg + 1/3 * {systolic_bp} mmHg = {map_value} mmHg.\n"
        explanation += f"Hence, the patient's mean arterial pressure is {map_value} mmHg."
        
        return explanation
    

