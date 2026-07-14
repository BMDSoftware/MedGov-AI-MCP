"""
Glasgow-Blatchford Bleeding Score Calculator
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


@register_calculator("glasgow_bleeding_score")
class GlasgowBleedingScoreCalculator(BaseCalculator):
    """Glasgow-Blatchford出血评分计算器实现"""
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=27,
            name="Glasgow-Blatchford Bleeding Score",
            category="critical_care",
            description="Assess severity of gastrointestinal bleeding using Glasgow-Blatchford Score",
            parameters=[
                Parameter(
                    name="hemoglobin",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="g/dL",
                    min_value=3.0,
                    max_value=20.0,
                    description="Hemoglobin level in g/dL"
                ),
                Parameter(
                    name="bun",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="mg/dL",
                    min_value=5.0,
                    max_value=150.0,
                    description="Blood urea nitrogen (BUN) level in mg/dL"
                ),
                Parameter(
                    name="sys_bp",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="mmHg",
                    min_value=60,
                    max_value=200,
                    description="Systolic blood pressure in mmHg"
                ),
                Parameter(
                    name="sex",
                    type=ParameterType.CHOICE,
                    required=True,
                    choices=["Male", "Female"],
                    description="Patient sex"
                ),
                Parameter(
                    name="heart_rate",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="bpm",
                    min_value=40,
                    max_value=200,
                    description="Heart rate in beats per minute"
                ),
                Parameter(
                    name="melena_present",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Presence of melena"
                ),
                Parameter(
                    name="syncope",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Recent syncope"
                ),
                Parameter(
                    name="hepatic_disease_history",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="History of hepatic disease"
                ),
                Parameter(
                    name="cardiac_failure",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Presence of cardiac failure"
                )
            ]
        )
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> ValidationResult:
        """验证参数"""
        errors = []
        
        # 验证血红蛋白范围
        if "hemoglobin" in parameters:
            hemoglobin = parameters["hemoglobin"]
            if hemoglobin < 3.0 or hemoglobin > 20.0:
                errors.append("Hemoglobin must be between 3.0 and 20.0 g/dL")
        else:
            errors.append("Missing required parameter: hemoglobin")
        
        # 验证BUN范围
        if "bun" in parameters:
            bun = parameters["bun"]
            if bun < 5.0 or bun > 150.0:
                errors.append("BUN must be between 5.0 and 150.0 mg/dL")
        else:
            errors.append("Missing required parameter: bun")
        
        # 验证血压范围
        if "sys_bp" in parameters:
            sys_bp = parameters["sys_bp"]
            if sys_bp < 60 or sys_bp > 200:
                errors.append("Systolic BP must be between 60 and 200 mmHg")
        else:
            errors.append("Missing required parameter: sys_bp")
        
        # 验证性别选择
        if "sex" in parameters:
            sex = parameters["sex"]
            if sex not in ["Male", "Female"]:
                errors.append("Sex must be either 'Male' or 'Female'")
        else:
            errors.append("Missing required parameter: sex")
        
        # 验证心率范围
        if "heart_rate" in parameters:
            heart_rate = parameters["heart_rate"]
            if heart_rate < 40 or heart_rate > 200:
                errors.append("Heart rate must be between 40 and 200 bpm")
        else:
            errors.append("Missing required parameter: heart_rate")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )
    
    def calculate(self, parameters: Dict[str, Any]) -> CalculationResult:
        """执行计算"""
        hemoglobin = parameters["hemoglobin"]
        bun = parameters["bun"]
        sys_bp = parameters["sys_bp"]
        sex = parameters["sex"]
        heart_rate = parameters["heart_rate"]
        melena_present = parameters.get("melena_present", False)
        syncope = parameters.get("syncope", False)
        hepatic_disease_history = parameters.get("hepatic_disease_history", False)
        cardiac_failure = parameters.get("cardiac_failure", False)
        
        score = 0
        
        # 计算血红蛋白评分
        if sex == "Male":
            if 12 < hemoglobin <= 13:
                score += 1
            elif 10 <= hemoglobin < 12:
                score += 3
            elif hemoglobin < 10:
                score += 6
        else:  # Female
            if 10 < hemoglobin <= 12:
                score += 1
            elif hemoglobin <= 10:
                score += 6
        
        # 计算BUN评分
        if 18.2 <= bun < 22.4:
            score += 2
        elif 22.4 <= bun < 28:
            score += 3
        elif 28 <= bun < 70:
            score += 4
        elif bun >= 70:
            score += 6
        
        # 计算收缩压评分
        if 100 <= sys_bp < 110:
            score += 1
        elif 90 <= sys_bp < 100:
            score += 2
        elif sys_bp < 90:
            score += 3
        
        # 计算心率评分
        if heart_rate >= 100:
            score += 1
        
        # 计算其他临床特征评分
        if melena_present:
            score += 1
        if syncope:
            score += 2
        if hepatic_disease_history:
            score += 2
        if cardiac_failure:
            score += 2
        
        # 生成解释
        explanation = self._generate_explanation(
            hemoglobin=hemoglobin,
            bun=bun,
            sys_bp=sys_bp,
            sex=sex,
            heart_rate=heart_rate,
            melena_present=melena_present,
            syncope=syncope,
            hepatic_disease_history=hepatic_disease_history,
            cardiac_failure=cardiac_failure,
            score=score
        )
        
        return CalculationResult(
            value=score,
            unit="points",
            explanation=explanation,
            metadata={
                "hemoglobin": hemoglobin,
                "bun": bun,
                "systolic_bp": sys_bp,
                "heart_rate": heart_rate,
                "sex": sex,
                "melena_present": melena_present,
                "syncope": syncope,
                "hepatic_disease_history": hepatic_disease_history,
                "cardiac_failure": cardiac_failure
            }
        )
    
    def _generate_explanation(self, hemoglobin: float, bun: float, sys_bp: float, sex: str,
                            heart_rate: float, melena_present: bool, syncope: bool,
                            hepatic_disease_history: bool, cardiac_failure: bool, score: int) -> str:
        """生成详细的计算解释"""
        explanation_parts = ["The Glasgow-Blatchford Score (GBS) for assessing the severity of gastrointestinal bleeding is calculated as follows:"]
        
        current_score = 0
        
        # 血红蛋白解释
        if sex == "Male":
            if 12 < hemoglobin <= 13:
                current_score += 1
                explanation_parts.append(f"Because the patient is a male and the hemoglobin concentration is between 12 and 13 g/dL, we add one point, making the current score {current_score - 1} + 1 = {current_score}.")
            elif 10 <= hemoglobin < 12:
                current_score += 3
                explanation_parts.append(f"Because the patient is a male and the hemoglobin concentration is between 10 and 12 g/dL, we add three points, making the current score {current_score - 3} + 3 = {current_score}.")
            elif hemoglobin < 10:
                current_score += 6
                explanation_parts.append(f"Because the patient is a male and the hemoglobin concentration is less than 10 g/dL, we add six points, making the current score {current_score - 6} + 6 = {current_score}.")
            else:
                explanation_parts.append(f"Because the patient is a male and the hemoglobin concentration is greater than 13 g/dL, we do not add any points, keeping the current score at {current_score}.")
        else:  # Female
            if 10 < hemoglobin <= 12:
                current_score += 1
                explanation_parts.append(f"Because the patient is a female and the hemoglobin concentration is between 10 and 12 g/dL, we add one point, making the current score {current_score - 1} + 1 = {current_score}.")
            elif hemoglobin < 10:
                current_score += 6
                explanation_parts.append(f"Because the patient is a female and the hemoglobin concentration is less than 10 mg/dL, we add six points, making the current score {current_score - 6} + 6 = {current_score}.")
            else:
                explanation_parts.append(f"Because the patient is a female and the hemoglobin concentration is greater than 12 mg/dL, we do not add any points, keeping the current score at {current_score}.")
        
        # BUN解释
        if 18.2 <= bun < 22.4:
            current_score += 2
            explanation_parts.append(f"The BUN concentration is between 18.2 and 22.4 mg/dL, and so we add two points, making the current score {current_score - 2} + 2 = {current_score}.")
        elif 22.4 <= bun < 28:
            current_score += 3
            explanation_parts.append(f"The BUN concentration is between 22.4 and 28 mg/dL, and so we add three points, making the current score {current_score - 3} + 3 = {current_score}.")
        elif 28 <= bun < 70:
            current_score += 4
            explanation_parts.append(f"The BUN concentration is between 28 and 70 mg/dL, and so we add four points, making the current score {current_score - 4} + 4 = {current_score}.")
        elif bun >= 70:
            current_score += 6
            explanation_parts.append(f"The BUN concentration is greater than 70 mg/dL, and so we add six points, making the current score {current_score - 6} + 6 = {current_score}.")
        elif bun < 18.2:
            explanation_parts.append(f"The BUN concentration is less than 18.2 mg/dL, and so we do not make any changes to the score, keeping the score at {current_score}.")
        
        # 收缩压解释
        explanation_parts.append(f"The patient's blood pressure is {sys_bp} mm Hg.")
        if 100 <= sys_bp < 110:
            current_score += 1
            explanation_parts.append(f"Because the patient's systolic blood pressure is between 100 and 110 mm Hg, we increase the score by one point, making the current score {current_score - 1} + 1 = {current_score}.")
        elif 90 <= sys_bp < 100:
            current_score += 2
            explanation_parts.append(f"Because the patient's systolic blood pressure is between 90 and 100 mm Hg, we increase the score by two points, making the current score {current_score - 2} + 2 = {current_score}.")
        elif sys_bp < 90:
            current_score += 3
            explanation_parts.append(f"Because the patient's systolic blood pressure is less than 90 mm Hg, we increase the score by three points, making the current score {current_score - 3} + 3 = {current_score}.")
        elif sys_bp >= 110:
            explanation_parts.append(f"Because the patient's systolic blood pressure is greater than or equal to 110 mm Hg, we do not add points to the score, keeping the current score at {current_score}.")
        
        # 心率解释
        explanation_parts.append(f"The patient's heart rate is {heart_rate} beats per minute.")
        if heart_rate >= 100:
            current_score += 1
            explanation_parts.append(f"Because the heart rate is greater or equal to than 100 beats per minute, we increase the score by one point, making the current score {current_score - 1} + 1 = {current_score}.")
        else:
            explanation_parts.append(f"Because the heart rate is less than 100 beats per minute, we do not change the score, keeping the current score at {current_score}.")
        
        # 临床特征评分
        if melena_present:
            current_score += 1
            explanation_parts.append(f"The patient has melena and so we add one point to the current total, making the current total {current_score - 1} + 1 = {current_score}.")
        
        if syncope:
            current_score += 2
            explanation_parts.append(f"The patient has a recent syncope, and so we add two points to the current total, making the current total {current_score - 2} + 2 = {current_score}.")
        
        if hepatic_disease_history:
            current_score += 2
            explanation_parts.append(f"The patient has a hepatic disease history, and so we add two points to the current total, making the current total {current_score - 2} + 2 = {current_score}.")
        
        if cardiac_failure:
            current_score += 2
            explanation_parts.append(f"The patient has cardiac failure, and so we add two points to the current total, making the current total {current_score - 2} + 2 = {current_score}.")
        
        explanation_parts.append(f"The patient's Glasgow Bleeding Score is {score}.")
        return "\n\n".join(explanation_parts)


