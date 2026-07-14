"""
Estimated Conception Date Calculator
预计受孕日期计算器 - 基于最后一次月经期计算
"""

from datetime import datetime, timedelta
from typing import Dict, Any
from medcalc import (
    BaseCalculator,
    CalculatorInfo,
    Parameter,
    ParameterType,
    ValidationResult,
    CalculationResult,
    register_calculator,
)


@register_calculator("estimated_conception")
class EstimatedConceptionCalculator(BaseCalculator):
    """预计受孕日期计算器实现"""

    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=68,
            name="Estimated Conception Date",
            category="obstetrics",
            description="Calculate estimated conception date based on last menstrual period",
            parameters=[
                Parameter(
                    name="menstrual_date",
                    type=ParameterType.TEXT,
                    required=True,
                    description="Last menstrual period date (MM/DD/YYYY format)",
                ),
                Parameter(
                    name="cycle_length",
                    type=ParameterType.NUMERIC,
                    required=False,
                    default=28,
                    min_value=14,
                    max_value=45,
                    unit="days",
                    description="Menstrual cycle length in days (default: 28)",
                ),
            ],
        )

    def validate_parameters(self, params: Dict[str, Any]) -> ValidationResult:
        """验证输入参数"""
        errors = []

        # 验证必需参数
        if "menstrual_date" not in params:
            errors.append("menstrual_date is required")
        else:
            # 验证日期格式
            try:
                datetime.strptime(params["menstrual_date"], "%m/%d/%Y")
            except ValueError:
                errors.append("menstrual_date must be in MM/DD/YYYY format")

        # 验证周期长度
        if "cycle_length" in params:
            cycle_length = params["cycle_length"]
            if not isinstance(cycle_length, (int, float)):
                errors.append("cycle_length must be a number")
            elif cycle_length < 14 or cycle_length > 45:
                errors.append("cycle_length must be between 14 and 45 days")

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    def calculate(self, params: Dict[str, Any]) -> CalculationResult:
        """执行预计受孕日期计算"""
        # 验证参数
        validation = self.validate_parameters(params)
        if not validation.is_valid:
            raise ValueError(f"Invalid parameters: {', '.join(validation.errors)}")

        # 获取参数
        menstrual_date_str = params["menstrual_date"]
        cycle_length = params.get("cycle_length", 28)

        # 解析日期
        menstrual_date = datetime.strptime(menstrual_date_str, "%m/%d/%Y")

        # 计算预计受孕日期（月经期后2周）
        conception_date = menstrual_date + timedelta(weeks=2)

        # 生成解释
        explanation = self._generate_explanation(menstrual_date_str, conception_date.strftime("%m/%d/%Y"), cycle_length)

        # 计算结果
        result_value = conception_date.strftime("%m/%d/%Y")

        return CalculationResult(
            value=result_value,
            unit="date",
            explanation=explanation,
            metadata={
                "menstrual_date": menstrual_date_str,
                "conception_date": result_value,
                "cycle_length": cycle_length,
                "calculation_method": "LMP + 2 weeks",
            },
        )

    def _generate_explanation(self, menstrual_date: str, conception_date: str, cycle_length: int) -> str:
        """生成计算解释"""
        explanation = "The patient's estimated date of conception based on their last period is computed by adding 2 weeks to the patient's last menstrual period date. "
        explanation += f"The patient's last menstrual period was {menstrual_date}. \n"
        explanation += f"Hence, the estimated date of conception after adding 2 weeks to the patient's last menstrual period date is {conception_date}. \n"

        return explanation
