"""
QTc Hodges Calculator
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


@register_calculator("qtc_hodges")
class QTcHodgesCalculator(BaseCalculator):
    """QTc Hodges计算器实现"""
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=58,
            name="QTc Hodges Calculator",
            category="cardiology",
            description="Calculate corrected QT interval using Hodges formula",
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
        
        # 获取参数值
        qt_interval = parameters.get("qt_interval")
        heart_rate = parameters.get("heart_rate")
        
        # 验证QT间期范围
        if qt_interval is not None:
            if not (200 <= qt_interval <= 800):
                errors.append("QT interval must be between 200 and 800 msec")
        
        # 验证心率范围
        if heart_rate is not None:
            if not (30 <= heart_rate <= 250):
                errors.append("Heart rate must be between 30 and 250 bpm")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )
    
    def calculate(self, parameters: Dict[str, Any]) -> CalculationResult:
        """执行计算"""
        qt_interval = parameters.get("qt_interval")
        heart_rate = parameters.get("heart_rate")
        
        # 计算RR间期（秒）
        rr_interval_sec = round_number(60 / heart_rate)
        
        # 计算QTc: QTc = QT间期 + 1.75 * [(60/RR间期) - 60]
        qtc = round_number(qt_interval + 1.75 * ((60 / rr_interval_sec) - 60))
        
        # 生成解释
        explanation = self._generate_explanation(qt_interval, heart_rate, rr_interval_sec, qtc)
        
        return CalculationResult(
            value=qtc,
            unit="msec",
            explanation=explanation,
            metadata={
                "qt_interval": qt_interval,
                "heart_rate": heart_rate,
                "rr_interval": rr_interval_sec,
                "formula": "QTc = QT + 1.75 * [(60/RR) - 60]"
            }
        )
    
    def _generate_explanation(self, qt_interval: float, heart_rate: float, 
                            rr_interval_sec: float, qtc: float) -> str:
        """生成计算解释"""
        explanation = "The corrected QT interval using the Hodges formula is computed as QTc = QT interval + 1.75 * [(60 /rr_interval_sec) - 60], "
        explanation += "where QT interval is in msec, and RR interval is given as 60/(heart rate).\n\n"
        
        explanation += f"The patient's heart rate is {heart_rate} beats per minute.\n"
        explanation += f"The QT interval is {qt_interval} msec.\n"
        
        explanation += f"The RR interval is computed as 60/(heart rate), and so the RR interval is 60/{heart_rate} = {rr_interval_sec}.\n"
        
        explanation += f"Hence, plugging in these values, we will get {qt_interval} + 1.75 * [(60/{rr_interval_sec}) - 60] = {qtc}.\n"
        
        explanation += f"The patient's corrected QT interval (QTc) is {qtc} msec."
        
        return explanation
