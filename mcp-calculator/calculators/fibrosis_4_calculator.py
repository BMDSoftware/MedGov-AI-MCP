"""
Fibrosis-4 (FIB-4) Index Calculator
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


@register_calculator("fibrosis_4")
class Fibrosis4Calculator(BaseCalculator):
    """纤维化-4 (FIB-4) 指数计算器实现"""
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=19,
            name="Fibrosis-4 (FIB-4) Index",
            category="hepatology",
            description="Calculate FIB-4 index to assess liver fibrosis using age, AST, ALT, and platelet count",
            parameters=[
                Parameter(
                    name="age",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="years",
                    min_value=18,
                    max_value=120,
                    description="Patient age in years"
                ),
                Parameter(
                    name="ast",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="U/L",
                    min_value=5,
                    max_value=1000,
                    description="Aspartate aminotransferase (AST) level in U/L"
                ),
                Parameter(
                    name="alt",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="U/L",
                    min_value=5,
                    max_value=1000,
                    description="Alanine aminotransferase (ALT) level in U/L"
                ),
                Parameter(
                    name="platelet_count",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="×10⁹/L",
                    min_value=10,
                    max_value=1000,
                    description="Platelet count in ×10⁹/L"
                )
            ]
        )
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> ValidationResult:
        """验证参数"""
        errors = []
        
        # 获取参数值并转换为浮点数
        try:
            age = float(parameters.get("age", 0)) if parameters.get("age") is not None else None
        except (ValueError, TypeError):
            errors.append("Age must be a valid number")
            age = None
            
        try:
            ast = float(parameters.get("ast", 0)) if parameters.get("ast") is not None else None
        except (ValueError, TypeError):
            errors.append("AST level must be a valid number")
            ast = None
            
        try:
            alt = float(parameters.get("alt", 0)) if parameters.get("alt") is not None else None
        except (ValueError, TypeError):
            errors.append("ALT level must be a valid number")
            alt = None
            
        try:
            platelet_count = float(parameters.get("platelet_count", 0)) if parameters.get("platelet_count") is not None else None
        except (ValueError, TypeError):
            errors.append("Platelet count must be a valid number")
            platelet_count = None
        
        # 检查必需参数
        if age is None:
            errors.append("Missing required parameter: age")
        if ast is None:
            errors.append("Missing required parameter: ast")
        if alt is None:
            errors.append("Missing required parameter: alt")
        if platelet_count is None:
            errors.append("Missing required parameter: platelet_count")
            
        # 验证数值范围
        if age is not None:
            if age < 18 or age > 120:
                errors.append("Age must be between 18 and 120 years")
        
        if ast is not None:
            if ast < 5 or ast > 1000:
                errors.append("AST level must be between 5 and 1000 U/L")
        
        if alt is not None:
            if alt < 5 or alt > 1000:
                errors.append("ALT level must be between 5 and 1000 U/L")
        
        if platelet_count is not None:
            if platelet_count < 10 or platelet_count > 1000:
                errors.append("Platelet count must be between 10 and 1000 ×10⁹/L")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )
    
    def calculate(self, parameters: Dict[str, Any]) -> CalculationResult:
        """执行计算"""
        # 获取参数值并转换为浮点数
        age = float(parameters.get("age"))
        ast = float(parameters.get("ast"))
        alt = float(parameters.get("alt"))
        platelet_count = float(parameters.get("platelet_count"))
        
        # 计算 FIB-4: (年龄 × AST) / (血小板计数(十亿/L) × √ALT)
        # 血小板计数已经是 ×10⁹/L 单位，所以直接使用
        fib4_score = round_number((age * ast) / (platelet_count * math.sqrt(alt)))
        
        # 生成解释和风险评估
        explanation = self._generate_explanation(age, ast, alt, platelet_count, fib4_score)
        risk_assessment = self._get_risk_assessment(fib4_score)
        
        return CalculationResult(
            value=fib4_score,
            unit="",
            explanation=explanation,
            metadata={
                "age": age,
                "ast": ast,
                "alt": alt,
                "platelet_count": platelet_count,
                "formula": "FIB-4 = (Age × AST) / (Platelet count (×10⁹/L) × √ALT)",
                "risk_assessment": risk_assessment
            }
        )
    
    def _generate_explanation(self, age: float, ast: float, alt: float, platelet_count: float, fib4_score: float) -> str:
        """生成计算解释"""
        explanation = "The formula for computing Fibrosis-4 is FIB-4 = (Age × AST) / (Platelet count (in ×10⁹/L) × √ALT), "
        explanation += "where platelet count is in billions per L, and the units for AST and ALT are both U/L.\n"
        
        explanation += f"The patient's age is {age} years.\n"
        explanation += f"The patient's concentration of AST is {ast} U/L.\n"
        explanation += f"The patient's concentration of ALT is {alt} U/L.\n"
        explanation += f"The patient's platelet count is {platelet_count} ×10⁹/L.\n"
        
        sqrt_alt = round_number(math.sqrt(alt))
        explanation += f"Plugging these values into the formula, we get ({age} × {ast}) / ({platelet_count} × √{alt}) = "
        explanation += f"({age} × {ast}) / ({platelet_count} × {sqrt_alt}) = {fib4_score}.\n"
        explanation += f"Hence, the Fibrosis-4 score is {fib4_score}."
        
        return explanation
    
    def _get_risk_assessment(self, fib4_score: float) -> str:
        """获取风险评估"""
        if fib4_score < 1.45:
            return "Low risk of advanced fibrosis (F3-F4)"
        elif fib4_score <= 3.25:
            return "Intermediate risk of advanced fibrosis - further evaluation recommended"
        else:
            return "High risk of advanced fibrosis (F3-F4)"
