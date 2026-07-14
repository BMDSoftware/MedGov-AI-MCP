"""
Estimated Gestational Age Calculator
预计妊娠期计算器 - 基于最后一次月经期和当前日期计算
"""

from datetime import datetime
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


@register_calculator("estimated_gestational_age")
class EstimatedGestationalAgeCalculator(BaseCalculator):
    """预计妊娠期计算器实现"""
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=69,
            name="Estimated Gestational Age",
            category="obstetrics",
            description="Calculate estimated gestational age based on last menstrual period and current date",
            parameters=[
                Parameter(
                    name="menstrual_date",
                    type=ParameterType.TEXT,
                    required=True,
                    description="Last menstrual period date (MM/DD/YYYY format)"
                ),
                Parameter(
                    name="current_date",
                    type=ParameterType.TEXT,
                    required=True,
                    description="Current date or assessment date (MM/DD/YYYY format)"
                )
            ]
        )
    
    def validate_parameters(self, params: Dict[str, Any]) -> ValidationResult:
        """验证输入参数"""
        errors = []
        
        # 验证必需参数
        required_params = ["menstrual_date", "current_date"]
        for param in required_params:
            if param not in params:
                errors.append(f"{param} is required")
            else:
                # 验证日期格式
                try:
                    datetime.strptime(params[param], "%m/%d/%Y")
                except ValueError:
                    errors.append(f"{param} must be in MM/DD/YYYY format")
        
        # 验证日期逻辑（当前日期应该在月经日期之后）
        if "menstrual_date" in params and "current_date" in params:
            try:
                menstrual_date = datetime.strptime(params["menstrual_date"], "%m/%d/%Y")
                current_date = datetime.strptime(params["current_date"], "%m/%d/%Y")
                
                if current_date < menstrual_date:
                    errors.append("current_date must be after menstrual_date")
                
                # 检查是否超过正常妊娠期（约42周）
                delta = current_date - menstrual_date
                if delta.days > 294:  # 42 weeks = 294 days
                    errors.append("Time difference exceeds normal pregnancy duration (42 weeks)")
                    
            except ValueError:
                pass  # 日期格式错误已在上面检查
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )
    
    def calculate(self, params: Dict[str, Any]) -> CalculationResult:
        """执行预计妊娠期计算"""
        # 验证参数
        validation = self.validate_parameters(params)
        if not validation.is_valid:
            raise ValueError(f"Invalid parameters: {', '.join(validation.errors)}")
        
        # 获取参数
        menstrual_date_str = params["menstrual_date"]
        current_date_str = params["current_date"]
        
        # 解析日期
        menstrual_date = datetime.strptime(menstrual_date_str, "%m/%d/%Y")
        current_date = datetime.strptime(current_date_str, "%m/%d/%Y")
        
        # 计算时间差
        delta = current_date - menstrual_date
        total_days = delta.days
        
        # 计算周数和天数
        weeks = total_days // 7
        days = total_days % 7
        
        # 生成解释
        explanation = self._generate_explanation(
            menstrual_date_str, 
            current_date_str,
            weeks,
            days,
            total_days
        )
        
        # 格式化结果 - 返回元组格式以匹配参考实现
        result_value = (f"{weeks} weeks", f"{days} days")
        
        return CalculationResult(
            value=result_value,
            unit="gestational_age",
            explanation=explanation,
            metadata={
                "menstrual_date": menstrual_date_str,
                "current_date": current_date_str,
                "total_days": total_days,
                "weeks": weeks,
                "days": days,
                "calculation_method": "Current date - LMP date"
            }
        )
    
    def _generate_explanation(self, menstrual_date: str, current_date: str, 
                            weeks: int, days: int, total_days: int) -> str:
        """生成计算解释"""
        explanation = "To compute the estimated gestational age, we compute the number of weeks and days apart today's date is from the patient's last menstrual period date. "
        explanation += f"The current date is {current_date} and the patient's last menstrual period date was {menstrual_date}. "
        
        if weeks == 0:
            explanation += f"The gap between these two dates is {days} days. Hence, the estimated gestational age is {days} days. "
        elif days == 0:
            explanation += f"The gap between these two dates is {weeks} weeks. Hence, the estimated gestational age is {weeks} weeks. "
        else:
            explanation += f"The gap between these two dates is {weeks} weeks and {days} days. Hence, the estimated gestational age is {weeks} weeks and {days} days. "
        
        return explanation
