"""
Caprini Score Calculator
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


@register_calculator("caprini")
class CapriniCalculator(BaseCalculator):
    """Caprini静脉血栓栓塞评分计算器实现"""
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=36,
            name="Caprini Score",
            category="cardiology",
            description="Caprini risk assessment model for venous thromboembolism",
            parameters=[
                Parameter(
                    name="age",
                    type=ParameterType.NUMERIC,
                    required=True,
                    min_value=0,
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
                    name="surgery_type",
                    type=ParameterType.CHOICE,
                    required=False,
                    choices=["none", "minor", "major", "laparoscopic", "arthroscopic", "elective_major_lower_extremity_arthroplasty"],
                    default="none",
                    description="Type of surgery"
                ),
                Parameter(
                    name="major_surgery",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Major surgery in the last month"
                ),
                Parameter(
                    name="chf",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Congestive heart failure in the last month"
                ),
                Parameter(
                    name="sepsis",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Sepsis in the last month"
                ),
                Parameter(
                    name="pneumonia",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Pneumonia in the last month"
                ),
                Parameter(
                    name="immobilizing_plaster_cast",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Immobilizing plaster cast in the last month"
                ),
                Parameter(
                    name="hip_pelvis_leg_fracture",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Hip, pelvis, or leg fracture in the last month"
                ),
                Parameter(
                    name="stroke",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Stroke in the last month"
                ),
                Parameter(
                    name="multiple_trauma",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Multiple trauma in the last month"
                ),
                Parameter(
                    name="acute_spinal_cord_injury",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Acute spinal cord injury causing paralysis in the last month"
                ),
                Parameter(
                    name="varicose_veins",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Varicose veins"
                ),
                Parameter(
                    name="current_swollen_legs",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Current swollen legs"
                ),
                Parameter(
                    name="current_central_venous",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Current central venous access"
                ),
                Parameter(
                    name="previous_dvt",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Previous DVT documented"
                ),
                Parameter(
                    name="previous_pe",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Previous pulmonary embolism documented"
                ),
                Parameter(
                    name="family_history_thrombosis",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Family history of thrombosis"
                ),
                Parameter(
                    name="positive_factor_v",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Positive Factor V Leiden"
                ),
                Parameter(
                    name="positive_prothrombin",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Positive prothrombin 20210A"
                ),
                Parameter(
                    name="serum_homocysteine",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Elevated serum homocysteine"
                ),
                Parameter(
                    name="positive_lupus_anticoagulant",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Positive lupus anticoagulant"
                ),
                Parameter(
                    name="elevated_anticardiolipin_antibody",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Elevated anticardiolipin antibody"
                ),
                Parameter(
                    name="heparin_induced_thrombocytopenia",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Heparin-induced thrombocytopenia"
                ),
                Parameter(
                    name="congenital_acquired_thrombophilia",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Other congenital or acquired thrombophilia"
                ),
                Parameter(
                    name="mobility",
                    type=ParameterType.CHOICE,
                    required=False,
                    choices=["normal", "bed_rest", "confined_bed_72h"],
                    default="normal",
                    description="Mobility status: normal (0), bed_rest = 'on bed rest' (1), confined_bed_72h = 'confined to bed >72 hours' (2)"
                ),
                Parameter(
                    name="inflammatory_bowel_disease",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="History of inflammatory bowel disease"
                ),
                Parameter(
                    name="acute_myocardial_infarction",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Acute myocardial infarction"
                ),
                Parameter(
                    name="copd",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Chronic obstructive pulmonary disease"
                ),
                Parameter(
                    name="malignancy",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Present or previous malignancy"
                ),
                Parameter(
                    name="bmi",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="kg/m²",
                    min_value=10,
                    max_value=80,
                    description="Body mass index in kg/m²"
                )
            ]
        )
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> ValidationResult:
        """验证参数"""
        errors = []
        
        # 验证必需参数
        if "age" not in parameters or parameters["age"] is None:
            errors.append("Age is required")
        elif not isinstance(parameters["age"], (int, float)) or parameters["age"] < 0 or parameters["age"] > 120:
            errors.append("Age must be between 0 and 120")
            
        if "sex" not in parameters or parameters["sex"] is None:
            errors.append("Sex is required")
        elif parameters["sex"] not in ["Male", "Female"]:
            errors.append("Sex must be 'Male' or 'Female'")
            
        if "bmi" not in parameters or parameters["bmi"] is None:
            errors.append("BMI is required")
        elif not isinstance(parameters["bmi"], (int, float)) or parameters["bmi"] < 10 or parameters["bmi"] > 80:
            errors.append("BMI must be between 10 and 80")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )
    
    def calculate(self, parameters: Dict[str, Any]) -> CalculationResult:
        """计算Caprini评分"""
        
        # 获取参数值 - 直接从字典获取，使用默认值
        age = parameters.get("age")
        sex = parameters.get("sex")
        surgery_type = parameters.get("surgery_type", "none")
        major_surgery = parameters.get("major_surgery", False)
        chf = parameters.get("chf", False)
        sepsis = parameters.get("sepsis", False)
        pneumonia = parameters.get("pneumonia", False)
        immobilizing_plaster_cast = parameters.get("immobilizing_plaster_cast", False)
        hip_pelvis_leg_fracture = parameters.get("hip_pelvis_leg_fracture", False)
        stroke = parameters.get("stroke", False)
        multiple_trauma = parameters.get("multiple_trauma", False)
        acute_spinal_cord_injury = parameters.get("acute_spinal_cord_injury", False)
        varicose_veins = parameters.get("varicose_veins", False)
        current_swollen_legs = parameters.get("current_swollen_legs", False)
        current_central_venous = parameters.get("current_central_venous", False)
        previous_dvt = parameters.get("previous_dvt", False)
        previous_pe = parameters.get("previous_pe", False)
        family_history_thrombosis = parameters.get("family_history_thrombosis", False)
        positive_factor_v = parameters.get("positive_factor_v", False)
        positive_prothrombin = parameters.get("positive_prothrombin", False)
        serum_homocysteine = parameters.get("serum_homocysteine", False)
        positive_lupus_anticoagulant = parameters.get("positive_lupus_anticoagulant", False)
        elevated_anticardiolipin_antibody = parameters.get("elevated_anticardiolipin_antibody", False)
        heparin_induced_thrombocytopenia = parameters.get("heparin_induced_thrombocytopenia", False)
        congenital_acquired_thrombophilia = parameters.get("congenital_acquired_thrombophilia", False)
        mobility = parameters.get("mobility", "normal")
        inflammatory_bowel_disease = parameters.get("inflammatory_bowel_disease", False)
        acute_myocardial_infarction = parameters.get("acute_myocardial_infarction", False)
        copd = parameters.get("copd", False)
        malignancy = parameters.get("malignancy", False)
        bmi = parameters.get("bmi")
        
        score = 0
        explanation_parts = []
        
        # 1. 年龄评分
        if age <= 40:
            age_points = 0
        elif 41 <= age <= 60:
            age_points = 1
        elif 61 <= age <= 74:
            age_points = 2
        else:  # >= 75
            age_points = 3
        
        score += age_points
        explanation_parts.append(f"Age {age} years: +{age_points} points")
        
        # 2. 性别评分
        if sex == "Female":
            score += 1
            explanation_parts.append("Female sex: +1 point")
        else:
            explanation_parts.append("Male sex: 0 points")
        
        # 3. 手术类型评分
        surgery_points = {
            "none": 0,
            "minor": 1,
            "major": 2,
            "laparoscopic": 2,
            "arthroscopic": 2,
            "elective_major_lower_extremity_arthroplasty": 5
        }
        surgery_score = surgery_points[surgery_type]
        score += surgery_score
        if surgery_score > 0:
            explanation_parts.append(f"Surgery type ({surgery_type}): +{surgery_score} points")
        
        # 4. 近期事件（≤1个月）
        recent_events = [
            (major_surgery, "Major surgery", 1),
            (chf, "Congestive heart failure", 1),
            (sepsis, "Sepsis", 1),
            (pneumonia, "Pneumonia", 1),
            (immobilizing_plaster_cast, "Immobilizing plaster cast", 2),
            (hip_pelvis_leg_fracture, "Hip/pelvis/leg fracture", 5),
            (stroke, "Stroke", 5),
            (multiple_trauma, "Multiple trauma", 5),
            (acute_spinal_cord_injury, "Acute spinal cord injury", 5)
        ]
        
        for condition, name, points in recent_events:
            if condition:
                score += points
                explanation_parts.append(f"{name} (≤1 month): +{points} points")
        
        # 5. 静脉疾病或凝血障碍
        venous_conditions = [
            (varicose_veins, "Varicose veins", 1),
            (current_swollen_legs, "Current swollen legs", 1),
            (current_central_venous, "Current central venous access", 2),
            (previous_dvt, "Previous DVT", 3),
            (previous_pe, "Previous PE", 3),
            (family_history_thrombosis, "Family history of thrombosis", 3),
            (positive_factor_v, "Positive Factor V Leiden", 3),
            (positive_prothrombin, "Positive prothrombin 20210A", 3),
            (serum_homocysteine, "Elevated serum homocysteine", 3),
            (positive_lupus_anticoagulant, "Positive lupus anticoagulant", 3),
            (elevated_anticardiolipin_antibody, "Elevated anticardiolipin antibody", 3),
            (heparin_induced_thrombocytopenia, "Heparin-induced thrombocytopenia", 3),
            (congenital_acquired_thrombophilia, "Other thrombophilia", 3)
        ]
        
        for condition, name, points in venous_conditions:
            if condition:
                score += points
                explanation_parts.append(f"{name}: +{points} points")
        
        # 6. 活动能力
        mobility_points = {
            "normal": 0,
            "bed_rest": 1,
            "confined_bed_72h": 2
        }
        mobility_score = mobility_points[mobility]
        score += mobility_score
        if mobility_score > 0:
            explanation_parts.append(f"Mobility ({mobility}): +{mobility_score} points")
        
        # 7. 其他病史
        other_conditions = [
            (inflammatory_bowel_disease, "Inflammatory bowel disease", 1),
            (acute_myocardial_infarction, "Acute myocardial infarction", 1),
            (copd, "COPD", 1),
            (malignancy, "Malignancy", 2)
        ]
        
        for condition, name, points in other_conditions:
            if condition:
                score += points
                explanation_parts.append(f"{name}: +{points} points")
        
        # 8. BMI评分（匹配原始代码：≥25加1分）
        if bmi >= 25:
            score += 1
            explanation_parts.append(f"BMI {bmi} ≥25 kg/m²: + 1 points (matches original code)")
        else:
            explanation_parts.append(f"BMI {bmi} <25 kg/m²: 0 points")
        
        # 生成解释
        explanation = "Caprini Score calculation:\n\n"
        explanation += "\n".join([f"• {part}" for part in explanation_parts])
        explanation += f"\n\nTotal Caprini Score: {score} points"
        
        # 添加风险分层和预防建议
        if score == 0:
            risk_level = "Very low risk"
            vte_risk = "<0.5%"
            recommendation = "Early ambulation"
        elif score == 1 or score == 2:
            risk_level = "Low risk"
            vte_risk = "~1.5%"
            recommendation = "Mechanical prophylaxis (compression stockings/IPC)"
        elif score == 3 or score == 4:
            risk_level = "Moderate risk"
            vte_risk = "~3%"
            recommendation = "Mechanical prophylaxis ± pharmacologic prophylaxis"
        elif score >= 5:
            risk_level = "High risk"
            vte_risk = ">6%"
            recommendation = "Mechanical + pharmacologic prophylaxis"
        
        explanation += f"\n\nRisk Level: {risk_level}"
        explanation += f"\nVTE Risk: {vte_risk}"
        explanation += f"\nRecommendation: {recommendation}"
        
        return CalculationResult(
            value=score,
            unit="points",
            explanation=explanation,
            metadata={
                "risk_level": risk_level,
                "vte_risk": vte_risk,
                "recommendation": recommendation,
                "age_points": age_points,
                "sex_points": 1 if sex == "Female" else 0,
                "surgery_points": surgery_score,
                "mobility_points": mobility_score,
                "bmi_points": 2 if bmi >= 25 else 0
            }
        )
