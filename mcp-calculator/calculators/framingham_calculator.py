"""
Framingham Risk Score Calculator
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


@register_calculator("framingham")
class FraminghamCalculator(BaseCalculator):
    """Framingham冠心病风险评分计算器实现"""
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=46,
            name="Framingham Risk Score",
            category="cardiology",
            description="Framingham 10-year coronary heart disease risk assessment",
            parameters=[
                Parameter(
                    name="age",
                    type=ParameterType.NUMERIC,
                    required=True,
                    min_value=30,
                    max_value=79,
                    description="Patient age in years (30-79)"
                ),
                Parameter(
                    name="sex",
                    type=ParameterType.CHOICE,
                    required=True,
                    choices=["Male", "Female"],
                    description="Patient sex"
                ),
                Parameter(
                    name="total_cholesterol",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="mg/dL",
                    min_value=100,
                    max_value=400,
                    description="Total cholesterol in mg/dL"
                ),
                Parameter(
                    name="hdl_cholesterol",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="mg/dL",
                    min_value=20,
                    max_value=100,
                    description="HDL cholesterol in mg/dL"
                ),
                Parameter(
                    name="systolic_bp",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="mmHg",
                    min_value=90,
                    max_value=200,
                    description="Systolic blood pressure in mmHg"
                ),
                Parameter(
                    name="bp_medication",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Currently taking blood pressure medication"
                ),
                Parameter(
                    name="smoker",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Current smoker"
                ),
                Parameter(
                    name="diabetes",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Diabetes mellitus"
                )
            ]
        )
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> ValidationResult:
        """验证参数"""
        errors = []
        info = self.get_info()
        
        # 基础验证 - 检查所有必需参数
        for param in info.parameters:
            if param.required and param.name not in parameters:
                errors.append(f"Missing required parameter: {param.name}")
            
            # 如果参数存在，验证其值
            if param.name in parameters:
                value = parameters[param.name]
                
                # 数值范围验证
                if param.type == ParameterType.NUMERIC:
                    try:
                        num_value = float(value)
                        range_error = self.validate_numeric_range(num_value, param)
                        if range_error:
                            errors.append(range_error)
                    except (ValueError, TypeError):
                        errors.append(f"Parameter {param.name} must be a number")
                
                # 选择项验证
                elif param.type == ParameterType.CHOICE:
                    if param.choices and value not in param.choices:
                        errors.append(f"Parameter {param.name} must be one of: {param.choices}")
        
        # 年龄范围验证
        age = parameters.get("age")
        if age is not None and (age < 30 or age > 79):
            errors.append("Age must be between 30 and 79 years for Framingham risk calculation")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )
    
    def calculate(self, parameters: Dict[str, Any]) -> CalculationResult:
        """计算Framingham风险评分"""
        
        # 获取参数定义
        info = self.get_info()
        param_defs = {p.name: p for p in info.parameters}
        
        # 获取参数值
        age = self.get_param_value(parameters, "age", param_defs["age"])
        sex = self.get_param_value(parameters, "sex", param_defs["sex"])
        total_cholesterol = self.get_param_value(parameters, "total_cholesterol", param_defs["total_cholesterol"])
        hdl_cholesterol = self.get_param_value(parameters, "hdl_cholesterol", param_defs["hdl_cholesterol"])
        systolic_bp = self.get_param_value(parameters, "systolic_bp", param_defs["systolic_bp"])
        bp_medication = self.get_param_value(parameters, "bp_medication", param_defs["bp_medication"])
        smoker = self.get_param_value(parameters, "smoker", param_defs["smoker"])
        diabetes = self.get_param_value(parameters, "diabetes", param_defs["diabetes"])
        
        # 转换布尔值为数值
        bp_med = 1 if bp_medication else 0
        smoking = 1 if smoker else 0
        dm = 1 if diabetes else 0
        
        # 计算年龄限制（用于年龄×吸烟交互项）
        if sex == "Male":
            age_smoke = min(age, 70)
        else:
            age_smoke = min(age, 78)
        
        # 计算风险评分
        if sex == "Male":
            # 男性Framingham风险评分公式
            risk_score = (
                52.00961 * math.log(age) +
                20.014077 * math.log(total_cholesterol) +
                -0.905964 * math.log(hdl_cholesterol) +
                1.305784 * math.log(systolic_bp) +
                0.241549 * bp_med +
                12.096316 * smoking +
                -4.605038 * (math.log(age) * math.log(total_cholesterol)) +
                -2.84367 * (math.log(age_smoke) * smoking) +
                -2.93323 * (math.log(age) * math.log(age)) +
                -172.300168
            )
            # 男性10年CHD风险
            risk_percentage = (1 - 0.9402 ** math.exp(risk_score)) * 100
        else:
            # 女性Framingham风险评分公式
            risk_score = (
                31.764001 * math.log(age) +
                22.465206 * math.log(total_cholesterol) +
                -1.187731 * math.log(hdl_cholesterol) +
                2.552905 * math.log(systolic_bp) +
                0.420251 * bp_med +
                13.07543 * smoking +
                -5.060998 * (math.log(age) * math.log(total_cholesterol)) +
                -2.996945 * (math.log(age_smoke) * smoking) +
                -146.5933061
            )
            # 女性10年CHD风险
            risk_percentage = (1 - 0.98767 ** math.exp(risk_score)) * 100
        
        # 四舍五入到小数点后1位
        risk_percentage = round_number(risk_percentage, 1)
        
        # 生成解释
        explanation_parts = [
            f"Patient: {age}-year-old {sex.lower()}",
            f"Total cholesterol: {total_cholesterol} mg/dL",
            f"HDL cholesterol: {hdl_cholesterol} mg/dL",
            f"Systolic blood pressure: {systolic_bp} mmHg",
            f"Blood pressure medication: {'Yes' if bp_medication else 'No'}",
            f"Current smoker: {'Yes' if smoker else 'No'}",
            f"Diabetes: {'Yes' if diabetes else 'No'}"
        ]
        
        explanation = "Framingham 10-year Coronary Heart Disease Risk calculation:\n\n"
        explanation += "\n".join([f"• {part}" for part in explanation_parts])
        explanation += f"\n\nCalculated risk score: {round_number(risk_score, 3)}"
        explanation += f"\n10-year CHD risk: {risk_percentage}%"
        
        # 添加风险分层
        if risk_percentage < 10:
            risk_category = "Low risk"
            recommendation = "Lifestyle modifications, reassess in 4-6 years"
        elif risk_percentage < 20:
            risk_category = "Intermediate risk"
            recommendation = "Consider additional risk factors, lifestyle modifications, possible statin therapy"
        else:
            risk_category = "High risk"
            recommendation = "Aggressive risk factor modification, statin therapy recommended"
        
        explanation += f"\n\nRisk Category: {risk_category}"
        explanation += f"\nRecommendation: {recommendation}"
        
        return CalculationResult(
            value=risk_percentage,
            unit="%",
            explanation=explanation,
            metadata={
                "risk_score": round_number(risk_score, 3),
                "risk_category": risk_category,
                "recommendation": recommendation,
                "sex": sex,
                "age_smoke_interaction": age_smoke,
                "risk_factors": {
                    "age": age,
                    "total_cholesterol": total_cholesterol,
                    "hdl_cholesterol": hdl_cholesterol,
                    "systolic_bp": systolic_bp,
                    "bp_medication": bp_medication,
                    "smoker": smoker,
                    "diabetes": diabetes
                }
            }
        )
