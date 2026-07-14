"""
Estimated Due Date Calculator
"""

from typing import Dict, Any
from datetime import datetime, timedelta
from medcalc import (
    BaseCalculator,
    CalculatorInfo,
    Parameter,
    ParameterType,
    ValidationResult,
    CalculationResult,
    register_calculator,
)


@register_calculator("estimated_due_date")
class EstimatedDueDateCalculator(BaseCalculator):
    """预计分娩日期计算器实现"""

    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=13,
            name="Estimated Due Date",
            category="obstetrics",
            description="Calculate estimated due date using Naegele's Rule based on last menstrual period",
            parameters=[
                Parameter(
                    name="menstrual_date",
                    type=ParameterType.TEXT,
                    required=True,
                    description="Last menstrual period date in MM/DD/YYYY format",
                ),
                Parameter(
                    name="cycle_length",
                    type=ParameterType.NUMERIC,
                    required=False,
                    default=28,
                    min_value=14,
                    max_value=45,
                    description="Menstrual cycle length in days (default: 28, normal range: 14-45)",
                ),
            ],
        )

    def validate_parameters(self, params: Dict[str, Any]) -> ValidationResult:
        """验证参数"""
        errors = []

        # 验证末次月经日期
        menstrual_date = params.get("menstrual_date")
        if not menstrual_date:
            errors.append("menstrual_date is required")
        else:
            try:
                datetime.strptime(str(menstrual_date), "%m/%d/%Y")
            except ValueError:
                errors.append("menstrual_date must be in MM/DD/YYYY format")

        # 验证周期长度
        cycle_length = params.get("cycle_length", 28)
        try:
            cycle_length = int(cycle_length)
            if cycle_length < 14 or cycle_length > 45:
                errors.append("cycle_length must be between 14 and 45 days")
        except (ValueError, TypeError):
            errors.append("cycle_length must be a valid number")

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    def calculate(self, params: Dict[str, Any]) -> CalculationResult:
        """计算预计分娩日期"""
        # 验证参数
        validation = self.validate_parameters(params)
        if not validation.is_valid:
            raise ValueError(f"Invalid parameters: {', '.join(validation.errors)}")

        # 获取参数
        menstrual_date_str = str(params["menstrual_date"])
        cycle_length = int(params.get("cycle_length", 28))

        # 按照参考文件的算法实现
        input_date = datetime.strptime(menstrual_date_str, "%m/%d/%Y")
        base_due_date = input_date + timedelta(weeks=40)

        # 根据周期调整日期
        if cycle_length == 28:
            final_due_date = base_due_date
        elif cycle_length < 28:
            cycle_length_gap = abs(cycle_length - 28)
            final_due_date = base_due_date - timedelta(days=cycle_length_gap)
        elif cycle_length > 28:
            cycle_length_gap = abs(cycle_length - 28)
            final_due_date = base_due_date + timedelta(days=cycle_length_gap)

        # 生成解释
        explanation = self._generate_explanation(menstrual_date_str, cycle_length, base_due_date, final_due_date)

        return CalculationResult(
            value=final_due_date.strftime("%m/%d/%Y"),
            unit="date",
            explanation=explanation,
            metadata={
                "method": "Naegele's Rule",
                "menstrual_date": menstrual_date_str,
                "cycle_length": cycle_length,
                "gestational_weeks": 40,
            },
        )

    def _generate_explanation(
        self, menstrual_date_str: str, cycle_length: int, base_due_date: datetime, final_due_date: datetime
    ) -> str:
        """生成计算解释"""
        explanation = (
            "The patient's estimated due date based on their last period is computed by using Naegele's Rule. "
        )
        explanation += "Using Naegele's Rule, we add 40 weeks to the patient's last menstrual period date. We then add or subtract days from the patient's estimated due date depending on how many more or less days a patient's cycle length is from the standard 28 days. \n"
        explanation += f"The patient's last menstrual period was {menstrual_date_str}. \n"
        explanation += f"The date after adding 40 weeks to the patient's last menstrual period date is {base_due_date.strftime('%m/%d/%Y')}. \n"

        if cycle_length == 28:
            explanation += f"Because the patient's cycle length is 28 days, we do not make any changes to the date. Hence, the patient's estimated due date is {final_due_date.strftime('%m/%d/%Y')}. \n"
        elif cycle_length < 28:
            cycle_length_gap = abs(cycle_length - 28)
            explanation += f"Because the patient's cycle length is {cycle_length} days, this means that we must subtract {cycle_length_gap} days from the patient's estimate due date. Hence, the patient's estimated due date is {final_due_date.strftime('%m/%d/%Y')}. \n"
        elif cycle_length > 28:
            cycle_length_gap = abs(cycle_length - 28)
            explanation += f"Because the patient's cycle length is {cycle_length} days, this means that we must add {cycle_length_gap} days to the patient's estimate due date. Hence, the patient's estimated due date is {final_due_date.strftime('%m/%d/%Y')}. \n"

        return explanation
