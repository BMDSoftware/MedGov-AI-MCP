"""
Wells Criteria for Deep Vein Thrombosis (DVT) Calculator
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


@register_calculator("wells_dvt")
class WellsDVTCalculator(BaseCalculator):
    """Wells深静脉血栓标准计算器实现"""
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=16,
            name="Wells Criteria for Deep Vein Thrombosis (DVT)",
            category="cardiology",
            description="Assess the probability of deep vein thrombosis using Wells criteria",
            parameters=[
                Parameter(
                    name="active_cancer",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Active cancer (treatment or palliation within 6 months)"
                ),
                Parameter(
                    name="bedridden_for_atleast_3_days",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Bedridden recently >3 days"
                ),
                Parameter(
                    name="major_surgery_in_last_12_weeks",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Major surgery within 12 weeks"
                ),
                Parameter(
                    name="calf_swelling_3cm",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Calf swelling >3 cm compared to the other leg"
                ),
                Parameter(
                    name="collateral_superficial_veins",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Collateral (nonvaricose) superficial veins present"
                ),
                Parameter(
                    name="leg_swollen",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Entire leg swollen"
                ),
                Parameter(
                    name="localized_tenderness_on_deep_venuous_system",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Localized tenderness along the deep venous system"
                ),
                Parameter(
                    name="pitting_edema_on_symptomatic_leg",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Pitting edema, confined to symptomatic leg"
                ),
                Parameter(
                    name="paralysis_paresis_immobilization_in_lower_extreme",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Paralysis, paresis, or recent plaster immobilization of the lower extremity"
                ),
                Parameter(
                    name="previous_dvt",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Previously documented DVT"
                ),
                Parameter(
                    name="alternative_to_dvt_diagnosis",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Alternative diagnosis to DVT as likely or more likely"
                )
            ]
        )
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> ValidationResult:
        """验证参数"""
        # Wells DVT标准只需要布尔参数，无需特殊验证
        return ValidationResult(is_valid=True, errors=[])
    
    def calculate(self, parameters: Dict[str, Any]) -> CalculationResult:
        """执行计算"""
        # 获取所有参数值，默认为False
        active_cancer = parameters.get("active_cancer", False)
        bedridden_for_atleast_3_days = parameters.get("bedridden_for_atleast_3_days", False)
        major_surgery_in_last_12_weeks = parameters.get("major_surgery_in_last_12_weeks", False)
        calf_swelling_3cm = parameters.get("calf_swelling_3cm", False)
        collateral_superficial_veins = parameters.get("collateral_superficial_veins", False)
        leg_swollen = parameters.get("leg_swollen", False)
        localized_tenderness_on_deep_venuous_system = parameters.get("localized_tenderness_on_deep_venuous_system", False)
        pitting_edema_on_symptomatic_leg = parameters.get("pitting_edema_on_symptomatic_leg", False)
        paralysis_paresis_immobilization_in_lower_extreme = parameters.get("paralysis_paresis_immobilization_in_lower_extreme", False)
        previous_dvt = parameters.get("previous_dvt", False)
        alternative_to_dvt_diagnosis = parameters.get("alternative_to_dvt_diagnosis", False)
        
        # 计算总分
        score = 0
        
        # 每个标准加1分（除了特殊处理的）
        if active_cancer:
            score += 1
        
        # 卧床≥3天或近12周内大手术：两个条件满足任一即可得1分
        if bedridden_for_atleast_3_days or major_surgery_in_last_12_weeks:
            score += 1
            
        if calf_swelling_3cm:
            score += 1
            
        if collateral_superficial_veins:
            score += 1
            
        if leg_swollen:
            score += 1
            
        if localized_tenderness_on_deep_venuous_system:
            score += 1
            
        if pitting_edema_on_symptomatic_leg:
            score += 1
            
        if paralysis_paresis_immobilization_in_lower_extreme:
            score += 1
            
        if previous_dvt:
            score += 1
            
        # 替代诊断更可能：减2分
        if alternative_to_dvt_diagnosis:
            score -= 2
        
        # 生成解释
        explanation = self._generate_explanation(parameters, score)
        
        # 风险分层
        if score <= 0:
            risk_category = "Low probability"
        elif score <= 2:
            risk_category = "Moderate probability"
        else:
            risk_category = "High probability"
        
        return CalculationResult(
            value=score,
            unit="points",
            explanation=explanation,
            metadata={
                "risk_category": risk_category,
                "criteria_met": self._get_criteria_met(parameters),
                "formula": "Wells DVT Score = Sum of applicable criteria points"
            }
        )
    
    def _get_criteria_met(self, parameters: Dict[str, Any]) -> Dict[str, bool]:
        """获取满足的标准"""
        return {
            "active_cancer": parameters.get("active_cancer", False),
            "bedridden_or_surgery": (parameters.get("bedridden_for_atleast_3_days", False) or 
                                   parameters.get("major_surgery_in_last_12_weeks", False)),
            "calf_swelling_3cm": parameters.get("calf_swelling_3cm", False),
            "collateral_superficial_veins": parameters.get("collateral_superficial_veins", False),
            "leg_swollen": parameters.get("leg_swollen", False),
            "localized_tenderness": parameters.get("localized_tenderness_on_deep_venuous_system", False),
            "pitting_edema": parameters.get("pitting_edema_on_symptomatic_leg", False),
            "paralysis_paresis_immobilization": parameters.get("paralysis_paresis_immobilization_in_lower_extreme", False),
            "previous_dvt": parameters.get("previous_dvt", False),
            "alternative_diagnosis": parameters.get("alternative_to_dvt_diagnosis", False)
        }
    
    def _generate_explanation(self, parameters: Dict[str, Any], score: int) -> str:
        """生成计算解释"""
        explanation = "The criteria for the Wells' Criteria for Deep Vein Thrombosis (DVT) score are listed below:\n\n"
        explanation += "1. Active cancer (treatment or palliation within 6 months): No = 0 points, Yes = +1 point\n"
        explanation += "2. Bedridden recently >3 days or major surgery within 12 weeks: No = 0 points, Yes = +1 point\n"
        explanation += "3. Calf swelling >3 cm compared to the other leg: No = 0 points, Yes = +1 point\n"
        explanation += "4. Collateral (nonvaricose) superficial veins present: No = 0 points, Yes = +1 point\n"
        explanation += "5. Entire leg swollen: No = 0 points, Yes = +1 point\n"
        explanation += "6. Localized tenderness along the deep venous system: No = 0 points, Yes = +1 point\n"
        explanation += "7. Pitting edema, confined to symptomatic leg: No = 0 points, Yes = +1 point\n"
        explanation += "8. Paralysis, paresis, or recent plaster immobilization: No = 0 points, Yes = +1 point\n"
        explanation += "9. Previously documented DVT: No = 0 points, Yes = +1 point\n"
        explanation += "10. Alternative diagnosis to DVT as likely or more likely: No = 0 points, Yes = -2 points\n\n"
        
        explanation += "The total score is calculated by summing the points for each criterion.\n\n"
        
        # 详细计算过程
        current_score = 0
        explanation += f"The current Well's DVT Score is {current_score}.\n"
        
        # 检查每个标准
        criteria_details = [
            ("active_cancer", "active cancer", 1),
            ("calf_swelling_3cm", "calf swelling >3 cm compared to the other leg", 1),
            ("collateral_superficial_veins", "collateral (nonvaricose) superficial veins present", 1),
            ("leg_swollen", "entire leg swollen", 1),
            ("localized_tenderness_on_deep_venuous_system", "localized tenderness along the deep venous system", 1),
            ("pitting_edema_on_symptomatic_leg", "pitting edema, confined to symptomatic leg", 1),
            ("paralysis_paresis_immobilization_in_lower_extreme", "paralysis, paresis, or recent plaster immobilization of the lower extremity", 1),
            ("previous_dvt", "previously documented DVT", 1),
            ("alternative_to_dvt_diagnosis", "alternative diagnosis to DVT as likely or more likely", -2)
        ]
        
        # 特殊处理卧床/手术标准
        bedridden = parameters.get("bedridden_for_atleast_3_days", False)
        surgery = parameters.get("major_surgery_in_last_12_weeks", False)
        
        if bedridden or surgery:
            explanation += f"Based on the Well's DVT rule, at least one of the issues, 'bedridden recently >3 days' or 'major surgery within 12 weeks' must be true for this criteria to be met for the score to increase by 1. Because this is the case, we increase the score by one making the total {current_score} + 1 = {current_score + 1}.\n"
            current_score += 1
        else:
            explanation += f"Based on the Well's DVT rule, at least one of the issues, 'bedridden recently >3 days' or 'major surgery within 12 weeks' must be true for this criteria to be met for the score to increase by 1. This is not the case for this patient, and so the score remains unchanged at {current_score}.\n"
        
        # 处理其他标准
        for param_name, description, points in criteria_details:
            param_value = parameters.get(param_name, False)
            param_status = "present" if param_value else "absent"
            explanation += f"From the patient's note, the issue, '{description},' is {param_status}. "
            
            if param_value:
                if points == -2:
                    explanation += f"By the Well's DVT rule, we decrease the score by 2 and so total is {current_score} - 2 = {current_score - 2}.\n"
                    current_score -= 2
                else:
                    explanation += f"By Well's DVT rule, a point should be given, and so we increment the score by one, making the total {current_score} + 1 = {current_score + 1}.\n"
                    current_score += 1
            else:
                explanation += f"By the Well's DVT rule, a point should not be given, and so the score remains unchanged and so total remains at {current_score}.\n"
        
        explanation += f"The Well's DVT score for the patient is {score}."
        
        return explanation
