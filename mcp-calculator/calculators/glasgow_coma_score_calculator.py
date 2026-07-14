"""
Glasgow Coma Score Calculator
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


@register_calculator("glasgow_coma_score")
class GlasgowComaScoreCalculator(BaseCalculator):
    """格拉斯哥昏迷评分计算器实现"""
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=21,
            name="Glasgow Coma Score (GCS)",
            category="critical_care",
            description="Calculate Glasgow Coma Score to assess level of consciousness",
            parameters=[
                Parameter(
                    name="best_eye_response",
                    type=ParameterType.CHOICE,
                    required=True,
                    choices=[
                        "eyes open spontaneously",
                        "eye opening to verbal command", 
                        "eye opening to pain",
                        "no eye opening",
                        "not testable"
                    ],
                    description="Best eye response observed"
                ),
                Parameter(
                    name="best_verbal_response",
                    type=ParameterType.CHOICE,
                    required=True,
                    choices=[
                        "oriented",
                        "confused",
                        "inappropriate words",
                        "incomprehensible sounds", 
                        "no verbal response",
                        "not testable"
                    ],
                    description="Best verbal response observed"
                ),
                Parameter(
                    name="best_motor_response",
                    type=ParameterType.CHOICE,
                    required=True,
                    choices=[
                        "obeys commands",
                        "localizes pain",
                        "withdrawal from pain",
                        "flexion to pain",
                        "extension to pain",
                        "no motor response"
                    ],
                    description="Best motor response observed"
                )
            ]
        )
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> ValidationResult:
        """验证输入参数"""
        errors = []
        
        # 验证必需参数
        if "best_eye_response" not in parameters:
            errors.append("best_eye_response is required")
        if "best_verbal_response" not in parameters:
            errors.append("best_verbal_response is required")
        if "best_motor_response" not in parameters:
            errors.append("best_motor_response is required")
            
        return ValidationResult(is_valid=len(errors) == 0, errors=errors)
    
    def calculate(self, parameters: Dict[str, Any]) -> CalculationResult:
        """计算格拉斯哥昏迷评分"""
        # 评分字典
        glasgow_dictionary = {
            "best_eye_response": {
                "eyes open spontaneously": 4, 
                "eye opening to verbal command": 3, 
                "eye opening to pain": 2, 
                "no eye opening": 1, 
                "not testable": 4
            },
            "best_verbal_response": {
                "oriented": 5, 
                "confused": 4, 
                "inappropriate words": 3, 
                "incomprehensible sounds": 2, 
                "no verbal response": 1, 
                "not testable": 4
            },
            "best_motor_response": {
                "obeys commands": 6, 
                "localizes pain": 5, 
                "withdrawal from pain": 4, 
                "flexion to pain": 3, 
                "extension to pain": 2, 
                "no motor response": 1
            }
        }
        
        # 获取参数值
        eye_response = parameters["best_eye_response"]
        verbal_response = parameters["best_verbal_response"]
        motor_response = parameters["best_motor_response"]
        
        # 计算各项评分
        eye_score = glasgow_dictionary["best_eye_response"][eye_response]
        verbal_score = glasgow_dictionary["best_verbal_response"][verbal_response]
        motor_score = glasgow_dictionary["best_motor_response"][motor_response]
        
        # 计算总分
        total_score = eye_score + verbal_score + motor_score
        
        # 生成解释
        explanation = self._generate_explanation(
            eye_response, verbal_response, motor_response,
            eye_score, verbal_score, motor_score, total_score
        )
        
        # 解释严重程度
        severity = self._interpret_score(total_score)
        
        return CalculationResult(
            value=total_score,
            explanation=explanation,
            metadata={
                "eye_response": eye_response,
                "verbal_response": verbal_response,
                "motor_response": motor_response,
                "eye_score": eye_score,
                "verbal_score": verbal_score,
                "motor_score": motor_score,
                "total_score": total_score,
                "severity": severity
            }
        )
    
    def _generate_explanation(self, eye_response: str, verbal_response: str, motor_response: str,
                            eye_score: int, verbal_score: int, motor_score: int, total_score: int) -> str:
        """生成计算解释"""
        explanation = """The Glasgow Coma Scale (GCS) for assessing a patient's level of consciousness:

1. Best Eye Response: Spontaneously = +4 points, To verbal command = +3 points, To pain = +2 points, No eye opening = +1 point
2. Best Verbal Response: Oriented = +5 points, Confused = +4 points, Inappropriate words = +3 points, Incomprehensible sounds = +2 points, No verbal response = +1 point
3. Best Motor Response: Obeys commands = +6 points, Localizes pain = +5 points, Withdrawal from pain = +4 points, Flexion to pain = +3 points, Extension to pain = +2 points, No motor response = +1 point

For each criteria, if a patient's value is not testable, we assume the best possible score for that component.

"""
        
        current_total = 0
        
        # 眼部反应
        eye_point = "points" if eye_score == 0 or eye_score > 1 else "point"
        if eye_response == 'not testable':
            explanation += f"Best eye response is '{eye_response}', assuming spontaneous eye opening. Adding {eye_score} {eye_point}: {current_total} + {eye_score} = {current_total + eye_score}.\n"
        else:
            explanation += f"Best eye response is '{eye_response}', adding {eye_score} {eye_point}: {current_total} + {eye_score} = {current_total + eye_score}.\n"
        current_total += eye_score
        
        # 言语反应
        verbal_point = "points" if verbal_score == 0 or verbal_score > 1 else "point"
        if verbal_response == 'not testable':
            explanation += f"Best verbal response is '{verbal_response}', assuming oriented response. Adding {verbal_score} {verbal_point}: {current_total} + {verbal_score} = {current_total + verbal_score}.\n"
        else:
            explanation += f"Best verbal response is '{verbal_response}', adding {verbal_score} {verbal_point}: {current_total} + {verbal_score} = {current_total + verbal_score}.\n"
        current_total += verbal_score
        
        # 运动反应
        motor_point = "points" if motor_score == 0 or motor_score > 1 else "point"
        explanation += f"Best motor response is '{motor_response}', adding {motor_score} {motor_point}: {current_total} + {motor_score} = {current_total + motor_score}.\n"
        current_total += motor_score
        
        explanation += f"\nTotal Glasgow Coma Score: {total_score}"
        
        return explanation
    
    def _interpret_score(self, score: int) -> str:
        """解释GCS评分严重程度"""
        if score >= 13:
            return "Mild brain injury"
        elif score >= 9:
            return "Moderate brain injury"
        else:
            return "Severe brain injury"
