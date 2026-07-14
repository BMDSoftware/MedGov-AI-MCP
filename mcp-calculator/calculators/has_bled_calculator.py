"""
HAS-BLED Score Calculator
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


@register_calculator("has_bled")
class HasBledCalculator(BaseCalculator):
    """HAS-BLED出血风险评分计算器实现"""
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=25,
            name="HAS-BLED Score",
            category="cardiology",
            description="Calculate HAS-BLED score to assess bleeding risk in anticoagulation therapy",
            parameters=[
                Parameter(
                    name="age",
                    type=ParameterType.NUMERIC,
                    required=True,
                    min_value=18,
                    max_value=120,
                    description="Patient age in years"
                ),
                Parameter(
                    name="hypertension",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Uncontrolled hypertension (>160 mmHg systolic)"
                ),
                Parameter(
                    name="renal_disease",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Renal disease (dialysis, transplant, Cr >2.26 mg/dL)"
                ),
                Parameter(
                    name="liver_disease",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Liver disease (cirrhosis or bilirubin >2x normal with AST/ALT/AP >3x normal)"
                ),
                Parameter(
                    name="stroke_history",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="History of stroke"
                ),
                Parameter(
                    name="prior_bleeding",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Prior major bleeding or predisposition to bleeding"
                ),
                Parameter(
                    name="labile_inr",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Labile INR (unstable/high INRs, time in therapeutic range <60%)"
                ),
                Parameter(
                    name="medications_for_bleeding",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Medication usage predisposing to bleeding (aspirin, clopidogrel, NSAIDs)"
                ),
                Parameter(
                    name="alcoholic_drinks",
                    type=ParameterType.NUMERIC,
                    required=True,
                    min_value=0,
                    max_value=50,
                    description="Number of alcoholic drinks per week"
                )
            ]
        )
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> ValidationResult:
        """验证输入参数"""
        errors = []
        
        # 获取参数值
        age = parameters.get("age")
        alcoholic_drinks = parameters.get("alcoholic_drinks")
        
        # 验证必需参数
        if age is None:
            errors.append("age is required")
        elif not isinstance(age, (int, float)) or age < 18 or age > 120:
            errors.append("age must be between 18 and 120 years")
            
        if alcoholic_drinks is None:
            errors.append("alcoholic_drinks is required")
        elif not isinstance(alcoholic_drinks, (int, float)) or alcoholic_drinks < 0:
            errors.append("alcoholic_drinks must be a non-negative number")
            
        return ValidationResult(is_valid=len(errors) == 0, errors=errors)
    
    def calculate(self, parameters: Dict[str, Any]) -> CalculationResult:
        """计算HAS-BLED评分"""
        # 获取参数值
        age = float(parameters["age"])
        hypertension = parameters.get("hypertension", False)
        renal_disease = parameters.get("renal_disease", False)
        liver_disease = parameters.get("liver_disease", False)
        stroke_history = parameters.get("stroke_history", False)
        prior_bleeding = parameters.get("prior_bleeding", False)
        labile_inr = parameters.get("labile_inr", False)
        medications_for_bleeding = parameters.get("medications_for_bleeding", False)
        alcoholic_drinks = float(parameters["alcoholic_drinks"])
        
        # 计算评分
        score = 0
        score_breakdown = {}
        
        # 年龄 >65岁
        if age > 65:
            score += 1
            score_breakdown["age"] = 1
        else:
            score_breakdown["age"] = 0
            
        # 高血压
        if hypertension:
            score += 1
            score_breakdown["hypertension"] = 1
        else:
            score_breakdown["hypertension"] = 0
            
        # 肾脏疾病
        if renal_disease:
            score += 1
            score_breakdown["renal_disease"] = 1
        else:
            score_breakdown["renal_disease"] = 0
            
        # 肝脏疾病
        if liver_disease:
            score += 1
            score_breakdown["liver_disease"] = 1
        else:
            score_breakdown["liver_disease"] = 0
            
        # 卒中史
        if stroke_history:
            score += 1
            score_breakdown["stroke_history"] = 1
        else:
            score_breakdown["stroke_history"] = 0
            
        # 既往出血史
        if prior_bleeding:
            score += 1
            score_breakdown["prior_bleeding"] = 1
        else:
            score_breakdown["prior_bleeding"] = 0
            
        # 不稳定INR
        if labile_inr:
            score += 1
            score_breakdown["labile_inr"] = 1
        else:
            score_breakdown["labile_inr"] = 0
            
        # 出血倾向药物
        if medications_for_bleeding:
            score += 1
            score_breakdown["medications_for_bleeding"] = 1
        else:
            score_breakdown["medications_for_bleeding"] = 0
            
        # 酒精使用 ≥8次/周
        if alcoholic_drinks >= 8:
            score += 1
            score_breakdown["alcohol"] = 1
        else:
            score_breakdown["alcohol"] = 0
        
        # 生成解释
        explanation = self._generate_explanation(
            age, hypertension, renal_disease, liver_disease, stroke_history,
            prior_bleeding, labile_inr, medications_for_bleeding, alcoholic_drinks,
            score, score_breakdown
        )
        
        # 解释风险等级
        risk_level = self._interpret_score(score)
        
        return CalculationResult(
            value=score,
            explanation=explanation,
            metadata={
                "age": age,
                "hypertension": hypertension,
                "renal_disease": renal_disease,
                "liver_disease": liver_disease,
                "stroke_history": stroke_history,
                "prior_bleeding": prior_bleeding,
                "labile_inr": labile_inr,
                "medications_for_bleeding": medications_for_bleeding,
                "alcoholic_drinks": alcoholic_drinks,
                "score_breakdown": score_breakdown,
                "total_score": score,
                "risk_level": risk_level
            }
        )
    
    def _generate_explanation(self, age: float, hypertension: bool, renal_disease: bool,
                            liver_disease: bool, stroke_history: bool, prior_bleeding: bool,
                            labile_inr: bool, medications_for_bleeding: bool, alcoholic_drinks: float,
                            score: int, score_breakdown: Dict) -> str:
        """生成计算解释"""
        explanation = """HAS-BLED Score for Bleeding Risk Assessment

The criteria for the HAS-BLED score are:

1. Hypertension (Uncontrolled, >160 mmHg systolic): +1 point
2. Renal disease (Dialysis, transplant, Cr >2.26 mg/dL or >200 µmol/L): +1 point
3. Liver disease (Cirrhosis or bilirubin >2x normal with AST/ALT/AP >3x normal): +1 point
4. Stroke history: +1 point
5. Prior major bleeding or predisposition to bleeding: +1 point
6. Labile INR (Unstable/high INRs, time in therapeutic range <60%): +1 point
7. Age >65: +1 point
8. Medication usage predisposing to bleeding (Aspirin, clopidogrel, NSAIDs): +1 point
9. Alcohol use (≥8 drinks/week): +1 point

Calculation:
"""
        
        current_score = 0
        
        # 年龄
        if age > 65:
            explanation += f"Age {age} years (>65): +1 point. Current score: {current_score} + 1 = {current_score + 1}\n"
            current_score += 1
        else:
            explanation += f"Age {age} years (≤65): 0 points. Current score: {current_score}\n"
        
        # 高血压
        if hypertension:
            explanation += f"Hypertension present: +1 point. Current score: {current_score} + 1 = {current_score + 1}\n"
            current_score += 1
        else:
            explanation += f"Hypertension absent: 0 points. Current score: {current_score}\n"
        
        # 肾脏疾病
        if renal_disease:
            explanation += f"Renal disease present: +1 point. Current score: {current_score} + 1 = {current_score + 1}\n"
            current_score += 1
        else:
            explanation += f"Renal disease absent: 0 points. Current score: {current_score}\n"
        
        # 肝脏疾病
        if liver_disease:
            explanation += f"Liver disease present: +1 point. Current score: {current_score} + 1 = {current_score + 1}\n"
            current_score += 1
        else:
            explanation += f"Liver disease absent: 0 points. Current score: {current_score}\n"
        
        # 卒中史
        if stroke_history:
            explanation += f"Stroke history present: +1 point. Current score: {current_score} + 1 = {current_score + 1}\n"
            current_score += 1
        else:
            explanation += f"Stroke history absent: 0 points. Current score: {current_score}\n"
        
        # 既往出血史
        if prior_bleeding:
            explanation += f"Prior bleeding present: +1 point. Current score: {current_score} + 1 = {current_score + 1}\n"
            current_score += 1
        else:
            explanation += f"Prior bleeding absent: 0 points. Current score: {current_score}\n"
        
        # 不稳定INR
        if labile_inr:
            explanation += f"Labile INR present: +1 point. Current score: {current_score} + 1 = {current_score + 1}\n"
            current_score += 1
        else:
            explanation += f"Labile INR absent: 0 points. Current score: {current_score}\n"
        
        # 出血倾向药物
        if medications_for_bleeding:
            explanation += f"Bleeding-predisposing medications present: +1 point. Current score: {current_score} + 1 = {current_score + 1}\n"
            current_score += 1
        else:
            explanation += f"Bleeding-predisposing medications absent: 0 points. Current score: {current_score}\n"
        
        # 酒精使用
        if alcoholic_drinks >= 8:
            explanation += f"Alcohol use {alcoholic_drinks} drinks/week (≥8): +1 point. Current score: {current_score} + 1 = {current_score + 1}\n"
            current_score += 1
        else:
            explanation += f"Alcohol use {alcoholic_drinks} drinks/week (<8): 0 points. Current score: {current_score}\n"
        
        explanation += f"\nTotal HAS-BLED score: {score}"
        
        return explanation
    
    def _interpret_score(self, score: int) -> str:
        """解释HAS-BLED评分风险等级"""
        if score >= 3:
            return "High bleeding risk"
        elif score == 2:
            return "Moderate bleeding risk"
        elif score == 1:
            return "Low-moderate bleeding risk"
        else:
            return "Low bleeding risk"
