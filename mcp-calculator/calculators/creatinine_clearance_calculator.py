"""
Creatinine Clearance Calculator (Cockcroft-Gault Equation)
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


@register_calculator("creatinine_clearance")
class CreatinineClearanceCalculator(BaseCalculator):
    """肌酐清除率计算器实现 (Cockcroft-Gault 方程)"""
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=2,
            name="Creatinine Clearance (Cockcroft-Gault)",
            category="nephrology",
            description="Calculate creatinine clearance using the Cockcroft-Gault equation",
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
                    name="weight",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="kg",
                    min_value=1,
                    max_value=500,
                    description="Patient weight in kg"
                ),
                Parameter(
                    name="height",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="cm",
                    min_value=30,
                    max_value=300,
                    description="Patient height in cm"
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
        required_params = ["age", "sex", "weight", "height", "creatinine"]
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
        
        # 验证体重
        try:
            weight = float(params["weight"])
            if weight < 1 or weight > 500:
                errors.append("Weight must be between 1 and 500 kg")
            if weight > 200:
                warnings.append("Weight is very high, please verify")
        except (ValueError, TypeError):
            errors.append("Weight must be a valid number")
        
        # 验证身高
        try:
            height = float(params["height"])
            if height < 30 or height > 300:
                errors.append("Height must be between 30 and 300 cm")
        except (ValueError, TypeError):
            errors.append("Height must be a valid number")
        
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
        weight = float(params["weight"])
        height = float(params["height"])
        creatinine = float(params["creatinine"])
        
        # 计算BMI
        height_m = height / 100  # 转换为米
        bmi = weight / (height_m * height_m)
        
        # 确定体重状态
        if bmi < 18.5:
            weight_status = "underweight"
        elif 18.5 <= bmi <= 24.9:
            weight_status = "normal weight"
        else:
            weight_status = "overweight/obese"
        
        # 计算理想体重 (IBW)
        height_inches = height / 2.54  # 转换为英寸
        if sex == "Male":
            ibw = 50 + 2.3 * (height_inches - 60)
        else:
            ibw = 45.5 + 2.3 * (height_inches - 60)
        
        # 确定调整体重
        if bmi < 18.5:
            # 体重不足：使用实际体重
            adjusted_weight = weight
        elif 18.5 <= bmi <= 24.9:
            # 正常体重：使用理想体重和实际体重的较小值
            adjusted_weight = min(ibw, weight)
        else:
            # 超重/肥胖：使用调整体重公式
            adjusted_weight = ibw + 0.4 * (weight - ibw)
        
        # 性别系数
        gender_coefficient = 1.0 if sex == "Male" else 0.85
        
        # 计算肌酐清除率 (Cockcroft-Gault)
        creatinine_clearance = ((140 - age) * adjusted_weight * gender_coefficient) / (creatinine * 72)
        creatinine_clearance = round_number(creatinine_clearance)
        
        # 生成详细解释
        explanation = self._generate_explanation(
            age, sex, weight, height, creatinine, bmi, weight_status,
            ibw, adjusted_weight, gender_coefficient, creatinine_clearance
        )
        
        return CalculationResult(
            value=creatinine_clearance,
            unit="mL/min",
            explanation=explanation,
            metadata={
                "age": age,
                "sex": sex,
                "weight": weight,
                "height": height,
                "creatinine": creatinine,
                "bmi": round_number(bmi),
                "weight_status": weight_status,
                "ideal_body_weight": round_number(ibw),
                "adjusted_weight": round_number(adjusted_weight),
                "gender_coefficient": gender_coefficient
            },
            warnings=[]
        )
    
    def _generate_explanation(self, age: float, sex: str, weight: float, height: float, 
                            creatinine: float, bmi: float, weight_status: str,
                            ibw: float, adjusted_weight: float, gender_coefficient: float,
                            creatinine_clearance: float) -> str:
        """生成详细的计算解释"""
        
        explanation = "The formula for computing Cockcroft-Gault is given by:\n"
        explanation += "CrCl = ((140 - age) × adjusted weight × gender_coefficient) / (serum creatinine × 72)\n\n"
        explanation += f"Where the gender_coefficient is 1 if male, and 0.85 if female.\n"
        explanation += f"The serum creatinine concentration is in mg/dL.\n\n"
        
        explanation += f"Patient Information:\n"
        explanation += f"- Gender: {sex.lower()}, gender coefficient = {gender_coefficient}\n"
        explanation += f"- Age: {age} years\n"
        explanation += f"- Weight: {weight} kg\n"
        explanation += f"- Height: {height} cm ({height/2.54:.1f} inches)\n"
        explanation += f"- Serum creatinine: {creatinine} mg/dL\n\n"
        
        # BMI计算和体重状态
        explanation += f"BMI Calculation:\n"
        explanation += f"BMI = weight(kg) / [height(m)]² = {weight} / [{height/100:.2f}]² = {bmi:.1f} kg/m²\n"
        explanation += f"The patient's BMI is {bmi:.1f}, indicating they are {weight_status}.\n\n"
        
        # 理想体重计算
        height_inches = height / 2.54
        explanation += f"Ideal Body Weight (IBW) Calculation:\n"
        if sex == "Male":
            explanation += f"For males: IBW = 50 kg + 2.3 kg × (height in inches - 60)\n"
            explanation += f"IBW = 50 + 2.3 × ({height_inches:.1f} - 60) = {ibw:.1f} kg\n\n"
        else:
            explanation += f"For females: IBW = 45.5 kg + 2.3 kg × (height in inches - 60)\n"
            explanation += f"IBW = 45.5 + 2.3 × ({height_inches:.1f} - 60) = {ibw:.1f} kg\n\n"
        
        # 调整体重选择
        explanation += f"Adjusted Weight Selection:\n"
        if bmi < 18.5:
            explanation += f"Because the patient is underweight, we use the patient's actual weight "
            explanation += f"({weight} kg) as the adjusted weight for the Cockcroft-Gault equation.\n\n"
        elif 18.5 <= bmi <= 24.9:
            explanation += f"Because the patient has normal weight, we use the minimum of the ideal body weight "
            explanation += f"and the patient's actual weight.\n"
            explanation += f"Adjusted weight = min({ibw:.1f}, {weight}) = {adjusted_weight:.1f} kg\n\n"
        else:
            explanation += f"Because the patient is overweight/obese, we use the adjusted body weight formula:\n"
            explanation += f"ABW = IBW + 0.4 × (actual weight - IBW)\n"
            explanation += f"ABW = {ibw:.1f} + 0.4 × ({weight} - {ibw:.1f}) = {adjusted_weight:.1f} kg\n\n"
        
        # 最终计算
        explanation += f"Cockcroft-Gault Calculation:\n"
        explanation += f"CrCl = ((140 - {age}) × {adjusted_weight:.1f} × {gender_coefficient}) / ({creatinine} × 72)\n"
        explanation += f"CrCl = ({140 - age} × {adjusted_weight:.1f} × {gender_coefficient}) / {creatinine * 72}\n"
        explanation += f"CrCl = {creatinine_clearance} mL/min\n\n"
        explanation += f"The patient's creatinine clearance is {creatinine_clearance} mL/min."
        
        return explanation
