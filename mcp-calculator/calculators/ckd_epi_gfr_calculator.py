"""
CKD-EPI 2021 Creatinine GFR Calculator
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


@register_calculator("ckd_epi_gfr")
class CKDEPIGFRCalculator(BaseCalculator):
    """CKD-EPI 2021肾小球滤过率计算器实现"""
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=3,
            name="CKD-EPI 2021 Creatinine GFR",
            category="nephrology",
            description="Calculate estimated GFR using the 2021 CKD-EPI creatinine equation",
            parameters=[
                Parameter(
                    name="age",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="years",
                    min_value=1,
                    max_value=120,
                    description="Patient age in years"
                ),
                Parameter(
                    name="sex",
                    type=ParameterType.CHOICE,
                    required=True,
                    choices=["Male", "Female"],
                    description="Patient sex"
                ),
                Parameter(
                    name="creatinine",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="mg/dL",
                    min_value=0.1,
                    max_value=20.0,
                    description="Serum creatinine concentration in mg/dL"
                )
            ]
        )
    
    def validate_parameters(self, params: Dict[str, Any]) -> ValidationResult:
        errors = []
        warnings = []
        
        # 检查必需参数
        required_params = ["age", "sex", "creatinine"]
        for param in required_params:
            if param not in params:
                errors.append(f"Missing required parameter: {param}")
        
        if errors:
            return ValidationResult(is_valid=False, errors=errors)
        
        # 验证年龄
        try:
            age = float(params["age"])
            if age < 1 or age > 120:
                errors.append("Age must be between 1 and 120 years")
        except (ValueError, TypeError):
            errors.append("Age must be a valid number")
        
        # 验证性别
        if params["sex"] not in ["Male", "Female"]:
            errors.append("Sex must be 'Male' or 'Female'")
        
        # 验证肌酐
        try:
            creatinine = float(params["creatinine"])
            if creatinine < 0.1 or creatinine > 20.0:
                errors.append("Creatinine must be between 0.1 and 20.0 mg/dL")
            if creatinine > 10.0:
                warnings.append("Creatinine level is very high")
        except (ValueError, TypeError):
            errors.append("Creatinine must be a valid number")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def calculate(self, params: Dict[str, Any]) -> CalculationResult:
        # 获取参数值
        age = float(params["age"])
        sex = params["sex"]
        creatinine = float(params["creatinine"])
        
        # 确定系数A和B
        if sex == "Female":
            if creatinine <= 0.7:
                a = 0.7
                b = -0.241
            else:
                a = 0.7
                b = -1.2
        else:  # Male
            if creatinine <= 0.9:
                a = 0.9
                b = -0.302
            else:
                a = 0.9
                b = -1.2
        
        # 性别系数
        gender_coefficient = 1.012 if sex == "Female" else 1.0
        
        # 计算GFR (CKD-EPI 2021)
        gfr = 142 * (creatinine / a) ** b * (0.9938 ** age) * gender_coefficient
        gfr = round_number(gfr)
        
        # 生成详细解释
        explanation = self._generate_explanation(
            age, sex, creatinine, a, b, gender_coefficient, gfr
        )
        
        return CalculationResult(
            value=gfr,
            unit="mL/min/1.73 m²",
            explanation=explanation,
            metadata={
                "age": age,
                "sex": sex,
                "creatinine": creatinine,
                "coefficient_a": a,
                "coefficient_b": b,
                "gender_coefficient": gender_coefficient
            },
            warnings=[]
        )
    
    def _generate_explanation(self, age: float, sex: str, creatinine: float,
                            a: float, b: float, gender_coefficient: float,
                            gfr: float) -> str:
        """生成详细的计算解释"""
        
        explanation = "The 2021 CKD-EPI equation for estimating GFR is:\n"
        explanation += "GFR = 142 × (Scr/A)^B × 0.9938^age × gender_coefficient\n\n"
        explanation += "Where:\n"
        explanation += "- Scr is serum creatinine concentration in mg/dL\n"
        explanation += "- A and B are coefficients based on sex and creatinine level\n"
        explanation += "- gender_coefficient is 1.012 for females, 1.0 for males\n\n"
        
        explanation += f"Patient Information:\n"
        explanation += f"- Age: {age} years\n"
        explanation += f"- Sex: {sex}\n"
        explanation += f"- Serum creatinine: {creatinine} mg/dL\n\n"
        
        # 性别系数
        explanation += f"Gender coefficient: {sex} → {gender_coefficient}\n\n"
        
        # 系数A和B的确定
        explanation += f"Coefficient determination:\n"
        if sex == "Female":
            if creatinine <= 0.7:
                explanation += f"Female with creatinine ≤ 0.7 mg/dL → A = {a}, B = {b}\n\n"
            else:
                explanation += f"Female with creatinine > 0.7 mg/dL → A = {a}, B = {b}\n\n"
        else:  # Male
            if creatinine <= 0.9:
                explanation += f"Male with creatinine ≤ 0.9 mg/dL → A = {a}, B = {b}\n\n"
            else:
                explanation += f"Male with creatinine > 0.9 mg/dL → A = {a}, B = {b}\n\n"
        
        # 计算过程
        explanation += f"Calculation:\n"
        explanation += f"GFR = 142 × ({creatinine}/{a})^{b} × 0.9938^{age} × {gender_coefficient}\n"
        
        # 分步计算
        scr_ratio = creatinine / a
        age_factor = 0.9938 ** age
        explanation += f"    = 142 × {scr_ratio:.4f}^{b} × {age_factor:.4f} × {gender_coefficient}\n"
        explanation += f"    = {gfr} mL/min/1.73 m²\n\n"
        
        explanation += f"The estimated GFR is {gfr} mL/min/1.73 m²."
        
        return explanation
