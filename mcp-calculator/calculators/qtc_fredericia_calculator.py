"""
QTc Fredericia Calculator
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


@register_calculator("qtc_fredericia")
class QTcFredericiaCalculator(BaseCalculator):
    """QTc Fredericia校正计算器实现"""
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=56,
            name="QTc Fredericia Calculator",
            category="cardiology",
            description="Calculate corrected QT interval using Fredericia formula",
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
        
        # 获取参数定义
        param_defs = {p.name: p for p in self.get_info().parameters}
        
        # 检查必需参数
        for param_name, param_def in param_defs.items():
            if param_def.required and param_name not in parameters:
                errors.append(f"Missing required parameter: {param_name}")
        
        if errors:
            return ValidationResult(is_valid=False, errors=errors)
        
        # 验证数值范围
        for param_name, param_def in param_defs.items():
            if param_name in parameters:
                value = parameters[param_name]
                
                # 验证数值类型和范围
                if param_def.type == ParameterType.NUMERIC:
                    try:
                        value = float(value)
                        
                        # 验证范围
                        if param_def.min_value is not None and value < param_def.min_value:
                            errors.append(f"{param_name} must be >= {param_def.min_value}, got {value}")
                        if param_def.max_value is not None and value > param_def.max_value:
                            errors.append(f"{param_name} must be <= {param_def.max_value}, got {value}")
                            
                    except (ValueError, TypeError):
                        errors.append(f"Invalid {param_name}: must be a number")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )
    
    def calculate(self, parameters: Dict[str, Any]) -> CalculationResult:
        """计算QTc Fredericia校正"""
        
        # 获取参数值
        param_defs = {p.name: p for p in self.get_info().parameters}
        qt_interval = self.get_param_value(parameters, "qt_interval", param_defs["qt_interval"])
        heart_rate = self.get_param_value(parameters, "heart_rate", param_defs["heart_rate"])
        
        # 计算RR间期（秒）
        rr_interval = 60 / heart_rate
        
        # 使用Fredericia公式计算QTc
        # QTc = QT / (RR)^(1/3)
        qtc_fredericia = qt_interval / (rr_interval ** (1/3))
        
        # 四舍五入到整数
        qtc_fredericia = round_number(qtc_fredericia, 0)
        rr_interval_rounded = round_number(rr_interval, 3)
        
        # 生成解释
        explanation = "QTc Fredericia calculation:\n\n"
        explanation += f"• QT interval: {qt_interval} msec\n"
        explanation += f"• Heart rate: {heart_rate} bpm\n"
        explanation += f"• RR interval: 60/{heart_rate} = {rr_interval_rounded} seconds\n\n"
        explanation += f"Fredericia formula: QTc = QT / (RR)^(1/3)\n"
        explanation += f"QTc = {qt_interval} / ({rr_interval_rounded})^(1/3) = {qtc_fredericia} msec"
        
        # 添加QTc解释
        if qtc_fredericia < 350:
            interpretation = "Short QTc"
            clinical_significance = "May indicate short QT syndrome or other conditions"
        elif qtc_fredericia <= 440:
            interpretation = "Normal QTc"
            clinical_significance = "Normal corrected QT interval"
        elif qtc_fredericia <= 500:
            interpretation = "Prolonged QTc"
            clinical_significance = "Borderline prolonged - monitor for arrhythmia risk"
        else:
            interpretation = "Significantly prolonged QTc"
            clinical_significance = "High risk for torsades de pointes and sudden cardiac death"
        
        explanation += f"\n\nInterpretation: {interpretation}"
        explanation += f"\nClinical significance: {clinical_significance}"
        
        # 添加与其他公式的比较说明
        explanation += "\n\nNote: Fredericia formula (QTc = QT/RR^(1/3)) is considered more accurate than Bazett formula at extreme heart rates"
        
        return CalculationResult(
            value=qtc_fredericia,
            unit="msec",
            explanation=explanation,
            metadata={
                "qt_interval": qt_interval,
                "heart_rate": heart_rate,
                "rr_interval": rr_interval_rounded,
                "interpretation": interpretation,
                "clinical_significance": clinical_significance,
                "formula": "Fredericia",
                "normal_range": "350-440 msec"
            }
        )
