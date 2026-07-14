"""
QTc Rautaharju Calculator
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


@register_calculator("qtc_rautaharju")
class QTcRautaharjuCalculator(BaseCalculator):
    """QTc Rautaharju计算器实现"""
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=59,
            name="QTc Rautaharju Calculator",
            category="cardiology",
            description="Calculate corrected QT interval using Rautaharju formula",
            parameters=[
                Parameter(
                    name="qt_interval",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="msec",
                    min_value=200,
                    max_value=800,
                    description="QT interval in milliseconds"
                ),
                Parameter(
                    name="heart_rate",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="bpm",
                    min_value=30,
                    max_value=250,
                    description="Heart rate in beats per minute"
                )
            ]
        )
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> ValidationResult:
        """验证参数"""
        errors = []
        info = self.get_info()
        param_defs = {p.name: p for p in info.parameters}
        
        # 获取参数值
        qt_interval = self.get_param_value(parameters, "qt_interval", param_defs["qt_interval"])
        heart_rate = self.get_param_value(parameters, "heart_rate", param_defs["heart_rate"])
        
        # 验证QT间期范围
        if qt_interval is not None:
            error_msg = self.validate_numeric_range(qt_interval, param_defs["qt_interval"])
            if error_msg:
                errors.append(error_msg)
        
        # 验证心率范围
        if heart_rate is not None:
            error_msg = self.validate_numeric_range(heart_rate, param_defs["heart_rate"])
            if error_msg:
                errors.append(error_msg)
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )
    
    def calculate(self, parameters: Dict[str, Any]) -> CalculationResult:
        """执行计算"""
        info = self.get_info()
        param_defs = {p.name: p for p in info.parameters}
        
        qt_interval = self.get_param_value(parameters, "qt_interval", param_defs["qt_interval"])
        heart_rate = self.get_param_value(parameters, "heart_rate", param_defs["heart_rate"])
        
        # 计算QTc: QTc = QT间期 * (120 + 心率) / 180
        qtc = round_number(qt_interval * (120 + heart_rate) / 180)
        
        # 生成解释
        explanation = self._generate_explanation(qt_interval, heart_rate, qtc)
        
        return CalculationResult(
            value=qtc,
            unit="msec",
            explanation=explanation,
            metadata={
                "qt_interval": qt_interval,
                "heart_rate": heart_rate,
                "formula": "QTc = QT * (120 + HR) / 180"
            }
        )
    
    def _generate_explanation(self, qt_interval: float, heart_rate: float, qtc: float) -> str:
        """生成计算解释"""
        explanation = "The corrected QT interval using the Rautaharju formula is computed as QTc = QT interval x (120 + HR) / 180, "
        explanation += "where QT interval is in msec, and HR is the heart rate in beats per minute.\n\n"
        
        explanation += f"The QT interval is {qt_interval} msec.\n"
        explanation += f"The patient's heart rate is {heart_rate} beats per minute.\n"
        
        explanation += f"Hence, plugging in these values, we will get {qt_interval} x (120 + {heart_rate}) / 180 = {qtc}.\n"
        explanation += f"The patient's corrected QT interval (QTc) is {qtc} msec."
        
        return explanation
