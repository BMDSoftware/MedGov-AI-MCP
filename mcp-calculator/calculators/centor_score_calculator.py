"""
Centor Score Calculator
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


@register_calculator("centor_score")
class CentorScoreCalculator(BaseCalculator):
    """Centor 评分计算器实现"""
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=20,
            name="Centor Score",
            category="infectious_disease",
            description="Assess likelihood of streptococcal pharyngitis using clinical criteria",
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
                    name="temperature",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="°C",
                    min_value=35,
                    max_value=45,
                    description="Body temperature in Celsius"
                ),
                Parameter(
                    name="exudate_swelling_tonsils",
                    type=ParameterType.BOOLEAN,
                    required=True,
                    description="Presence of exudate or swelling on tonsils"
                ),
                Parameter(
                    name="tender_lymph_nodes",
                    type=ParameterType.BOOLEAN,
                    required=True,
                    description="Presence of tender/swollen anterior cervical lymph nodes"
                ),
                Parameter(
                    name="cough_absent",
                    type=ParameterType.BOOLEAN,
                    required=True,
                    description="Absence of cough (true if no cough present)"
                )
            ]
        )
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> ValidationResult:
        """验证参数"""
        errors = []
        
        # 获取参数值
        age = parameters.get("age")
        temperature = parameters.get("temperature")
        
        # 验证数值范围
        if age is not None:
            if not (1 <= age <= 120):
                errors.append("Age must be between 1 and 120 years")
        
        if temperature is not None:
            if not (35 <= temperature <= 45):
                errors.append("Temperature must be between 35 and 45°C")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )
    
    def calculate(self, parameters: Dict[str, Any]) -> CalculationResult:
        """执行计算"""
        age = parameters.get("age")
        temperature = parameters.get("temperature")
        exudate_swelling_tonsils = parameters.get("exudate_swelling_tonsils")
        tender_lymph_nodes = parameters.get("tender_lymph_nodes")
        cough_absent = parameters.get("cough_absent")
        
        # 计算 Centor 评分
        score = 0
        criteria_details = []
        
        # 年龄评分: 3-14岁=+1分，15-44岁=0分，≥45岁=-1分
        if 3 <= age <= 14:
            score += 1
            criteria_details.append(f"Age {age} years (3-14): +1 point")
        elif 15 <= age <= 44:
            criteria_details.append(f"Age {age} years (15-44): 0 points")
        elif age >= 45:
            score -= 1
            criteria_details.append(f"Age {age} years (≥45): -1 point")
        else:
            criteria_details.append(f"Age {age} years (<3): 0 points")
        
        # 体温 >38°C: +1分
        if temperature > 38:
            score += 1
            criteria_details.append(f"Temperature {temperature}°C (>38°C): +1 point")
        else:
            criteria_details.append(f"Temperature {temperature}°C (≤38°C): 0 points")
        
        # 扁桃体渗出或肿胀: +1分
        if exudate_swelling_tonsils:
            score += 1
            criteria_details.append("Exudate or swelling on tonsils: +1 point")
        else:
            criteria_details.append("No exudate or swelling on tonsils: 0 points")
        
        # 颈前淋巴结触痛/肿大: +1分
        if tender_lymph_nodes:
            score += 1
            criteria_details.append("Tender/swollen anterior cervical lymph nodes: +1 point")
        else:
            criteria_details.append("No tender/swollen anterior cervical lymph nodes: 0 points")
        
        # 无咳嗽: +1分
        if cough_absent:
            score += 1
            criteria_details.append("Cough absent: +1 point")
        else:
            criteria_details.append("Cough present: 0 points")
        
        # 生成解释和风险评估
        explanation = self._generate_explanation(criteria_details, score)
        risk_assessment = self._get_risk_assessment(score)
        
        return CalculationResult(
            value=score,
            unit="points",
            explanation=explanation,
            metadata={
                "age": age,
                "temperature": temperature,
                "exudate_swelling_tonsils": exudate_swelling_tonsils,
                "tender_lymph_nodes": tender_lymph_nodes,
                "cough_absent": cough_absent,
                "criteria_details": criteria_details,
                "risk_assessment": risk_assessment
            }
        )
    
    def _generate_explanation(self, criteria_details: list, score: int) -> str:
        """生成计算解释"""
        explanation = "The criteria listed in the Centor Score formula are:\n\n"
        explanation += "1. Age: 3-14 years = +1 point, 15-44 years = 0 points, ≥45 years = -1 point\n"
        explanation += "2. Exudate or swelling on tonsils: No = 0 points, Yes = +1 point\n"
        explanation += "3. Tender/swollen anterior cervical lymph nodes: No = 0 points, Yes = +1 point\n"
        explanation += "4. Temperature >38°C (100.4°F): No = 0 points, Yes = +1 point\n"
        explanation += "5. Cough: Cough present = 0 points, Cough absent = +1 point\n\n"
        explanation += "The Centor score is calculated by summing the points for each criterion.\n\n"
        
        explanation += "Assessment of each criterion:\n"
        for detail in criteria_details:
            explanation += f"• {detail}\n"
        
        explanation += f"\nTotal Centor Score: {score} points"
        
        return explanation
    
    def _get_risk_assessment(self, score: int) -> str:
        """获取风险评估"""
        if score <= 0:
            return "Very low risk of streptococcal pharyngitis (1-2.5%)"
        elif score == 1:
            return "Low risk of streptococcal pharyngitis (5-10%)"
        elif score == 2:
            return "Moderate risk of streptococcal pharyngitis (11-17%)"
        elif score == 3:
            return "Moderately high risk of streptococcal pharyngitis (28-35%)"
        elif score >= 4:
            return "High risk of streptococcal pharyngitis (51-53%)"
        else:
            return "Risk assessment not available"
