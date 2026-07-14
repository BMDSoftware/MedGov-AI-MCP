"""
Child-Pugh Score Calculator
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


@register_calculator("child_pugh")
class ChildPughCalculator(BaseCalculator):
    """Child-Pugh肝硬化评分计算器实现"""
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=15,
            name="Child-Pugh Score",
            category="hepatology",
            description="Assess severity of cirrhosis using Child-Pugh classification",
            parameters=[
                Parameter(
                    name="bilirubin",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="mg/dL",
                    min_value=0.1,
                    max_value=30.0,
                    description="Total bilirubin in mg/dL"
                ),
                Parameter(
                    name="albumin",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="g/dL",
                    min_value=1.0,
                    max_value=6.0,
                    description="Serum albumin in g/dL"
                ),
                Parameter(
                    name="inr",
                    type=ParameterType.NUMERIC,
                    required=True,
                    min_value=0.8,
                    max_value=10.0,
                    description="International Normalized Ratio (INR)"
                ),
                Parameter(
                    name="ascites",
                    type=ParameterType.CHOICE,
                    required=False,
                    choices=["Absent", "Slight", "Moderate"],
                    default="Absent",
                    description="Ascites severity"
                ),
                Parameter(
                    name="encephalopathy",
                    type=ParameterType.CHOICE,
                    required=False,
                    choices=["No Encephalopathy", "Grade 1-2", "Grade 3-4"],
                    default="No Encephalopathy",
                    description="Hepatic encephalopathy grade"
                )
            ]
        )
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> ValidationResult:
        """验证参数"""
        errors = []
        
        # 获取参数定义
        param_defs = {p.name: p for p in self.get_info().parameters}
        
        # 获取参数值
        bilirubin = parameters.get("bilirubin")
        albumin = parameters.get("albumin")
        inr = parameters.get("inr")
        
        # 检查必需参数
        required_params = ["bilirubin", "albumin", "inr"]
        for param_name in required_params:
            if param_name not in parameters:
                errors.append(f"Missing required parameter: {param_name}")
        
        # 验证数值范围
        if bilirubin is not None:
            error_msg = self.validate_numeric_range(bilirubin, param_defs["bilirubin"])
            if error_msg:
                errors.append(error_msg)
        
        if albumin is not None:
            error_msg = self.validate_numeric_range(albumin, param_defs["albumin"])
            if error_msg:
                errors.append(error_msg)
        
        if inr is not None:
            error_msg = self.validate_numeric_range(inr, param_defs["inr"])
            if error_msg:
                errors.append(error_msg)
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )
    
    def calculate(self, parameters: Dict[str, Any]) -> CalculationResult:
        """执行计算"""
        bilirubin = parameters.get("bilirubin")
        albumin = parameters.get("albumin")
        inr = parameters.get("inr")
        ascites = parameters.get("ascites", "Absent")
        encephalopathy = parameters.get("encephalopathy", "No Encephalopathy")
        
        # 计算Child-Pugh评分
        score = 0
        
        # 胆红素评分
        if bilirubin < 2:
            bilirubin_score = 1
        elif bilirubin <= 3:
            bilirubin_score = 2
        else:
            bilirubin_score = 3
        score += bilirubin_score
        
        # 白蛋白评分
        if albumin > 3.5:
            albumin_score = 1
        elif albumin >= 2.8:
            albumin_score = 2
        else:
            albumin_score = 3
        score += albumin_score
        
        # INR评分
        if inr < 1.7:
            inr_score = 1
        elif inr <= 2.3:
            inr_score = 2
        else:
            inr_score = 3
        score += inr_score
        
        # 腹水评分
        ascites_score_map = {"Absent": 1, "Slight": 2, "Moderate": 3}
        ascites_score = ascites_score_map[ascites]
        score += ascites_score
        
        # 肝性脑病评分
        encephalopathy_score_map = {"No Encephalopathy": 1, "Grade 1-2": 2, "Grade 3-4": 3}
        encephalopathy_score = encephalopathy_score_map[encephalopathy]
        score += encephalopathy_score
        
        # 生成解释
        explanation = self._generate_explanation(
            bilirubin, albumin, inr, ascites, encephalopathy,
            bilirubin_score, albumin_score, inr_score, ascites_score, encephalopathy_score, score
        )
        
        return CalculationResult(
            value=score,
            unit="points",
            explanation=explanation,
            metadata={
                "bilirubin": bilirubin,
                "albumin": albumin,
                "inr": inr,
                "ascites": ascites,
                "encephalopathy": encephalopathy,
                "bilirubin_score": bilirubin_score,
                "albumin_score": albumin_score,
                "inr_score": inr_score,
                "ascites_score": ascites_score,
                "encephalopathy_score": encephalopathy_score,
                "class": self._get_child_pugh_class(score)
            }
        )
    
    def _generate_explanation(self, bilirubin: float, albumin: float, inr: float,
                            ascites: str, encephalopathy: str, bilirubin_score: int,
                            albumin_score: int, inr_score: int, ascites_score: int,
                            encephalopathy_score: int, total_score: int) -> str:
        """生成计算解释"""
        explanation = """The criteria for the Child-Pugh Score are listed below:

1. Bilirubin (Total): <2 mg/dL = +1 point, 2-3 mg/dL = +2 points, >3 mg/dL = +3 points
2. Albumin: >3.5 g/dL = +1 point, 2.8-3.5 g/dL = +2 points, <2.8 g/dL = +3 points
3. INR: <1.7 = +1 point, 1.7-2.3 = +2 points, >2.3 = +3 points
4. Ascites: Absent = +1 point, Slight = +2 points, Moderate = +3 points
5. Encephalopathy: No Encephalopathy = +1 point, Grade 1-2 = +2 points, Grade 3-4 = +3 points

The Child-Pugh Score is calculated by summing the points for each criterion.\n\n"""
        
        explanation += "The current child pugh score is 0.\n"
        
        current_score = 0
        
        # INR评分解释
        explanation += f"The patient's INR is {inr}. "
        if inr < 1.7:
            explanation += f"Because the INR is less than 1.7, we add 1 to the score, making the current total {current_score} + 1 = {current_score + 1}.\n"
        elif inr <= 2.3:
            explanation += f"Because the INR is between 1.7 and 2.3, we add 2 to the score, making the current total {current_score} + 2 = {current_score + 2}.\n"
        else:
            explanation += f"Because the INR is greater than 2.3, we add 3 to the score, making the current total {current_score} + 3 = {current_score + 3}.\n"
        current_score += inr_score
        
        # 胆红素评分解释
        explanation += f"The patient's bilirubin is {bilirubin} mg/dL. "
        if bilirubin < 2:
            explanation += f"Because the Bilirubin concentration is less than 2 mg/dL, we add 1 to the score, making the current total {current_score} + 1 = {current_score + 1}.\n"
        elif bilirubin <= 3:
            explanation += f"Because the Bilirubin concentration is between 2 mg/dL and 3 mg/dL, we add 2 to the score, making the current total {current_score} + 2 = {current_score + 2}.\n"
        else:
            explanation += f"Because the Bilirubin concentration is greater than 3 mg/dL, we add 3 to the score, making the current total {current_score} + 3 = {current_score + 3}.\n"
        current_score += bilirubin_score
        
        # 白蛋白评分解释
        explanation += f"The patient's albumin is {albumin} g/dL. "
        if albumin > 3.5:
            explanation += f"Because the Albumin concentration is greater than 3.5 g/dL, we add 1 to the score, making the current total {current_score} + 1 = {current_score + 1}.\n"
        elif albumin >= 2.8:
            explanation += f"Because the Albumin concentration is between 2.8 g/dL and 3.5 g/dL, we add 2 to the score, making the current total {current_score} + 2 = {current_score + 2}.\n"
        else:
            explanation += f"Because the Albumin concentration is less than 2.8 g/dL, we add 3 to the score, making the current total {current_score} + 3 = {current_score + 3}.\n"
        current_score += albumin_score
        
        # 腹水评分解释
        if ascites == "Absent":
            explanation += f"Ascites is reported to be 'absent' and so we add 1 point to the score, making the current total {current_score} + 1 = {current_score + 1}.\n"
        elif ascites == "Slight":
            explanation += f"Ascites is reported to be 'slight' and so we add 2 points to the score, making the current total {current_score} + 2 = {current_score + 2}.\n"
        else:
            explanation += f"Ascites is reported to be 'moderate' and so we add 3 points to the score, making the current total {current_score} + 3 = {current_score + 3}.\n"
        current_score += ascites_score
        
        # 肝性脑病评分解释
        if encephalopathy == "No Encephalopathy":
            explanation += f"Encephalopathy state is reported to be 'no encephalopathy' and so we add 1 point to the score, making the current total {current_score} + 1 = {current_score + 1}.\n"
        elif encephalopathy == "Grade 1-2":
            explanation += f"Encephalopathy state is 'Grade 1-2 encephalopathy' and so we add 2 points to the score, making the current total {current_score} + 2 = {current_score + 2}.\n"
        else:
            explanation += f"Encephalopathy state is 'Grade 3-4 encephalopathy' and so we add 3 points to the score, making the current total {current_score} + 3 = {current_score + 3}.\n"
        current_score += encephalopathy_score
        
        explanation += f"The patient's child pugh score is {total_score}."
        
        return explanation
    
    def _get_child_pugh_class(self, score: int) -> str:
        """获取Child-Pugh分级"""
        if score <= 6:
            return "Class A"
        elif score <= 9:
            return "Class B"
        else:
            return "Class C"
