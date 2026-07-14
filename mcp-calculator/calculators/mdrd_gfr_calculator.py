"""
MDRD GFR Calculator
"""

import math
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


@register_calculator("mdrd_gfr")
class MDRDGFRCalculator(BaseCalculator):
    """MDRD肾小球滤过率计算器实现"""
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=9,
            name="MDRD GFR Equation",
            category="nephrology",
            description="Estimate glomerular filtration rate using the MDRD equation",
            parameters=[
                Parameter(
                    name="age",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="years",
                    min_value=18,
                    max_value=120,
                    description="Age in years"
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
                    description="Serum creatinine in mg/dL"
                ),
                Parameter(
                    name="race",
                    type=ParameterType.CHOICE,
                    required=False,
                    choices=["Black", "Non-Black"],
                    default="Non-Black",
                    description="Patient race"
                )
            ]
        )
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> ValidationResult:
        """验证参数"""
        errors = []
        
        # 获取参数值（直接从字典获取）
        age = parameters.get("age")
        creatinine = parameters.get("creatinine")
        sex = parameters.get("sex")
        
        # 检查必需参数
        if age is None:
            errors.append("Missing required parameter: age")
        if creatinine is None:
            errors.append("Missing required parameter: creatinine")
        if sex is None:
            errors.append("Missing required parameter: sex")
        
        # 验证数值范围
        if age is not None:
            if not isinstance(age, (int, float)) or age < 18 or age > 120:
                errors.append("Age must be between 18 and 120 years")
        
        if creatinine is not None:
            if not isinstance(creatinine, (int, float)) or creatinine < 0.1 or creatinine > 20.0:
                errors.append("Creatinine must be between 0.1 and 20.0 mg/dL")
        
        # 验证性别
        if sex is not None and sex not in ["Male", "Female"]:
            errors.append("Sex must be 'Male' or 'Female'")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )
    
    def calculate(self, parameters: Dict[str, Any]) -> CalculationResult:
        """执行计算"""
        age = parameters.get("age")
        sex = parameters.get("sex")
        creatinine = parameters.get("creatinine")
        race = parameters.get("race", "Non-Black")
        
        # 确定系数
        race_coefficient = 1.212 if race == "Black" else 1.0
        gender_coefficient = 0.742 if sex == "Female" else 1.0
        
        # 计算MDRD GFR: GFR = 175 × Cr^(-1.154) × 年龄^(-0.203) × 种族系数 × 性别系数
        gfr = round_number(
            175 * 
            math.exp(math.log(creatinine) * -1.154) * 
            math.exp(math.log(age) * -0.203) * 
            race_coefficient * 
            gender_coefficient
        )
        
        # 生成解释
        explanation = self._generate_explanation(age, sex, creatinine, race, 
                                               race_coefficient, gender_coefficient, gfr)
        
        return CalculationResult(
            value=gfr,
            unit="mL/min/1.73m²",
            explanation=explanation,
            metadata={
                "age": age,
                "sex": sex,
                "creatinine": creatinine,
                "race": race,
                "race_coefficient": race_coefficient,
                "gender_coefficient": gender_coefficient,
                "formula": "GFR = 175 × Cr^(-1.154) × Age^(-0.203) × Race × Gender"
            }
        )
    
    def _generate_explanation(self, age: float, sex: str, creatinine: float, race: str,
                            race_coefficient: float, gender_coefficient: float, gfr: float) -> str:
        """生成计算解释"""
        explanation = f"Patient age: {age} years\n"
        explanation += f"Serum creatinine: {creatinine} mg/dL\n\n"
        
        if race == "Black":
            explanation += "The patient is Black, so the race coefficient is 1.212.\n"
        else:
            explanation += "The patient is not Black, so the race coefficient is defaulted to 1.0.\n"
        
        if sex == "Female":
            explanation += "The patient is female, so the gender coefficient is 0.742.\n"
        else:
            explanation += "The patient is male, so the gender coefficient is 1.\n"
        
        explanation += f"\nThe patient's estimated GFR is calculated using the MDRD equation as:\n"
        explanation += f"GFR = 175 * creatinine^(-1.154) * age^(-0.203) * race_coefficient * gender_coefficient. The creatinine concentration is in mg/dL.\n"
        explanation += f"Plugging in these values will give us: 175 * {creatinine}^(-1.154) * {age}^(-0.203) * {race_coefficient} * {gender_coefficient} = {gfr}.\n"
        explanation += f"Hence, the patient's GFR is {gfr} mL/min/1.73m²."
        
        return explanation
    

