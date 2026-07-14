"""
CHA2DS2-VASc Score Calculator
"""

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


@register_calculator("cha2ds2_vasc")
class CHA2DS2VAScCalculator(BaseCalculator):
    """CHA2DS2-VASc评分计算器实现"""

    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=4,
            name="CHA2DS2-VASc Score",
            category="cardiology",
            description="Calculate stroke risk in atrial fibrillation using CHA2DS2-VASc score",
            parameters=[
                Parameter(
                    name="age",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="years",
                    min_value=18,
                    max_value=120,
                    description="Patient age in years",
                ),
                Parameter(
                    name="sex",
                    type=ParameterType.CHOICE,
                    required=True,
                    choices=["Male", "Female"],
                    description="Patient sex",
                ),
                Parameter(
                    name="chf",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="History of congestive heart failure",
                ),
                Parameter(
                    name="hypertension",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="History of hypertension",
                ),
                Parameter(
                    name="stroke",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="History of stroke",
                ),
                Parameter(
                    name="tia",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="History of transient ischemic attack (TIA)",
                ),
                Parameter(
                    name="thromboembolism",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="History of thromboembolism",
                ),
                Parameter(
                    name="vascular_disease",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="History of vascular disease (MI, PAD, aortic plaque)",
                ),
                Parameter(
                    name="diabetes",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="History of diabetes mellitus",
                ),
            ],
        )

    def validate_parameters(self, params: Dict[str, Any]) -> ValidationResult:
        errors = []
        warnings = []

        # 检查必需参数
        required_params = ["age", "sex"]
        for param in required_params:
            if param not in params:
                errors.append(f"Missing required parameter: {param}")

        if errors:
            return ValidationResult(is_valid=False, errors=errors)

        # 验证年龄
        try:
            age = float(params["age"])
            if age < 18 or age > 120:
                errors.append("Age must be between 18 and 120 years")
        except (ValueError, TypeError):
            errors.append("Age must be a valid number")

        # 验证性别
        if params["sex"] not in ["Male", "Female"]:
            errors.append("Sex must be 'Male' or 'Female'")

        # 验证布尔参数
        boolean_params = ["chf", "hypertension", "stroke", "tia", "thromboembolism", "vascular_disease", "diabetes"]
        for param in boolean_params:
            if param in params:
                value = params[param]
                if not isinstance(value, bool) and value not in [0, 1, "true", "false", "True", "False"]:
                    errors.append(f"{param} must be a boolean value (true/false)")

        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)

    def calculate(self, params: Dict[str, Any]) -> CalculationResult:
        # 获取参数值
        age = float(params["age"])
        sex = params["sex"]

        # 获取布尔参数（如果未提供则默认为False）
        chf = self._get_boolean_param(params, "chf", False)
        hypertension = self._get_boolean_param(params, "hypertension", False)
        stroke = self._get_boolean_param(params, "stroke", False)
        tia = self._get_boolean_param(params, "tia", False)
        thromboembolism = self._get_boolean_param(params, "thromboembolism", False)
        vascular_disease = self._get_boolean_param(params, "vascular_disease", False)
        diabetes = self._get_boolean_param(params, "diabetes", False)

        # 计算评分
        score = 0
        score_breakdown = []

        # 年龄评分 (根据原始calculator_engine逻辑)
        if age >= 75:
            score += 2
            score_breakdown.append("Age ≥75 years: +2 points")
        elif age >= 65:
            score += 1
            score_breakdown.append("Age 65-74 years: +1 point")
        else:
            score_breakdown.append("Age <65 years: 0 points")

        # 性别评分
        if sex == "Female":
            score += 1
            score_breakdown.append("Female sex: +1 point")
        else:
            score_breakdown.append("Male sex: 0 points")

        # CHF评分
        if chf:
            score += 1
            score_breakdown.append("Congestive heart failure: +1 point")
        else:
            score_breakdown.append("No congestive heart failure: 0 points")

        # 高血压评分
        if hypertension:
            score += 1
            score_breakdown.append("Hypertension: +1 point")
        else:
            score_breakdown.append("No hypertension: 0 points")

        # 卒中/TIA/血栓栓塞评分
        if stroke or tia or thromboembolism:
            score += 2
            conditions = []
            if stroke:
                conditions.append("stroke")
            if tia:
                conditions.append("TIA")
            if thromboembolism:
                conditions.append("thromboembolism")
            score_breakdown.append(f"History of {'/'.join(conditions)}: +2 points")
        else:
            score_breakdown.append("No stroke/TIA/thromboembolism: 0 points")

        # 血管疾病评分
        if vascular_disease:
            score += 1
            score_breakdown.append("Vascular disease: +1 point")
        else:
            score_breakdown.append("No vascular disease: 0 points")

        # 糖尿病评分
        if diabetes:
            score += 1
            score_breakdown.append("Diabetes: +1 point")
        else:
            score_breakdown.append("No diabetes: 0 points")

        # 生成详细解释
        explanation = self._generate_explanation(
            age, sex, chf, hypertension, stroke, tia, thromboembolism, vascular_disease, diabetes, score
        )

        return CalculationResult(
            value=score,
            unit="points",
            explanation=explanation,
            metadata={
                "age": age,
                "sex": sex,
                "chf": chf,
                "hypertension": hypertension,
                "stroke": stroke,
                "tia": tia,
                "thromboembolism": thromboembolism,
                "vascular_disease": vascular_disease,
                "diabetes": diabetes,
                "score_breakdown": score_breakdown,
            },
            warnings=[],
        )

    def _get_boolean_param(self, params: Dict[str, Any], param_name: str, default: bool) -> bool:
        """获取布尔参数值，处理各种输入格式"""
        if param_name not in params:
            return default

        value = params[param_name]
        if isinstance(value, bool):
            return value
        elif isinstance(value, (int, float)):
            return bool(value)
        elif isinstance(value, str):
            return value.lower() in ["true", "1", "yes"]
        else:
            return default

    def _generate_explanation(
        self,
        age: float,
        sex: str,
        chf: bool,
        hypertension: bool,
        stroke: bool,
        tia: bool,
        thromboembolism: bool,
        vascular_disease: bool,
        diabetes: bool,
        score: int,
    ) -> str:
        """生成详细的计算解释（完全还原原始版本）"""

        explanation = ""

        # 年龄解释
        if age >= 75:
            explanation += f"Because the age is greater than 74, two points added to the score, making the current total {score - 2} + 2 = {score}.\n"
        elif age >= 65:
            explanation += f"Because the age is between 65 and 74, one point added to the score, making the current total {score - 1} + 1 = {score}.\n"
        else:
            explanation += f"Because the age is less than 65 years, no points are added to the current total, keeping the total at {score}.\n"

        # 性别解释
        explanation += f"The patient's gender is {sex.lower()} "
        if sex.lower() == "female":
            explanation += (
                f"and so one point is added to the score, making the current total {score - 1} + 1 = {score}.\n"
            )
        else:
            explanation += f"and so no points are added to the current total, keeping the total at {score}.\n"

        # CHF解释
        explanation += f"The patient history for congestive heart failure is {'present' if chf else 'absent'}. "
        if chf:
            explanation += f"Because the patient has congestive heart failure, one point is added to the score, making the current total {score - 1} + 1 = {score}.\n"
        else:
            explanation += f"Because the patient does not have congestive heart failure, no points are added to the current total, keeping the total at {score}.\n"

        # 高血压解释
        explanation += f"The patient history for hypertension is {'present' if hypertension else 'absent'}. "
        if hypertension:
            explanation += f"Because the patient has hypertension, one point is added to the score, making the current total {score - 1} + 1 = {score}.\n"
        else:
            explanation += f"Because the patient does not have hypertension, no points are added to the current total, keeping the total at {score}.\n"

        # 卒中解释
        explanation += f"One criteria of the CHA2DS2-VASc score is to check if the patient has had any history of stroke, transient ischemic attacks (TIA), or thromboembolism. "
        if stroke or tia or thromboembolism:
            explanation += f"Because at least one of stroke, tia, or thromboembolism is present, two points are added to the score, making the current total {score - 2} + 2 = {score}.\n"
        else:
            explanation += f"Because all of stroke, tia, or thromboembolism are absent, no points are added to score, keeping the score at {score}.\n"

        # 血管疾病解释
        explanation += f"Based on the patient note, the patient history for vascular disease is {'present' if vascular_disease else 'absent'}. "
        if vascular_disease:
            explanation += f"Because the patient has vascular disease, one point is added to the score, making the current total {score - 1} + 1 = {score}. "
        else:
            explanation += f"Because the patient does not have vascular disease, no points are added to score, keeping the score at {score}. "

        # 糖尿病解释
        explanation += (
            f"Based on the patient note, the patient history for diabetes is {'present' if diabetes else 'absent'}. "
        )
        if diabetes:
            explanation += f"Because the patient has diabetes, one point is added to the score, making the current total {score - 1} + 1 = {score}.\n"
        else:
            explanation += f"Because the patient does not have diabetes, no points are added to score, keeping the score at {score}.\n"

        explanation += f"The patient's CHA2DS2-VASc Score is {score}.\n"

        return explanation
