"""
APACHE II Score Calculator
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


@register_calculator("apache_ii")
class ApacheIICalculator(BaseCalculator):
    """APACHE II评分计算器实现"""
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=28,
            name="APACHE II Score",
            category="critical_care",
            description="Acute Physiology and Chronic Health Evaluation II score for ICU mortality prediction",
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
                    name="temperature",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="°C",
                    min_value=25,
                    max_value=45,
                    description="Rectal temperature in Celsius"
                ),
                Parameter(
                    name="systolic_bp",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="mmHg",
                    min_value=30,
                    max_value=300,
                    description="Systolic blood pressure in mmHg"
                ),
                Parameter(
                    name="diastolic_bp",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="mmHg",
                    min_value=20,
                    max_value=200,
                    description="Diastolic blood pressure in mmHg"
                ),
                Parameter(
                    name="heart_rate",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="bpm",
                    min_value=20,
                    max_value=250,
                    description="Heart rate in beats per minute"
                ),
                Parameter(
                    name="respiratory_rate",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="breaths/min",
                    min_value=5,
                    max_value=80,
                    description="Respiratory rate in breaths per minute"
                ),
                Parameter(
                    name="fio2",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="%",
                    min_value=21,
                    max_value=100,
                    description="Fraction of inspired oxygen percentage"
                ),
                Parameter(
                    name="pao2",
                    type=ParameterType.NUMERIC,
                    required=False,
                    unit="mmHg",
                    min_value=20,
                    max_value=500,
                    description="Partial pressure of oxygen (required if FiO2 < 50%)"
                ),
                Parameter(
                    name="aa_gradient",
                    type=ParameterType.NUMERIC,
                    required=False,
                    unit="mmHg",
                    min_value=0,
                    max_value=700,
                    description="Alveolar-arterial gradient (required if FiO2 >= 50%)"
                ),
                Parameter(
                    name="ph",
                    type=ParameterType.NUMERIC,
                    required=True,
                    min_value=6.5,
                    max_value=8.0,
                    description="Arterial pH"
                ),
                Parameter(
                    name="sodium",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="mmol/L",
                    min_value=100,
                    max_value=200,
                    description="Serum sodium in mmol/L"
                ),
                Parameter(
                    name="potassium",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="mmol/L",
                    min_value=1.0,
                    max_value=10.0,
                    description="Serum potassium in mmol/L"
                ),
                Parameter(
                    name="creatinine",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="mg/dL",
                    min_value=0.1,
                    max_value=15.0,
                    description="Serum creatinine in mg/dL"
                ),
                Parameter(
                    name="hematocrit",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="%",
                    min_value=10,
                    max_value=70,
                    description="Hematocrit percentage"
                ),
                Parameter(
                    name="wbc",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="×10³/mm³",
                    min_value=0.1,
                    max_value=100,
                    description="White blood cell count in thousands per cubic mm"
                ),
                Parameter(
                    name="gcs",
                    type=ParameterType.NUMERIC,
                    required=True,
                    min_value=3,
                    max_value=15,
                    description="Glasgow Coma Scale score"
                ),
                Parameter(
                    name="acute_renal_failure",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Presence of acute renal failure"
                ),
                Parameter(
                    name="chronic_renal_failure",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Presence of chronic renal failure"
                ),
                Parameter(
                    name="organ_failure_immunocompromise",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="History of severe organ insufficiency or immunocompromised state"
                ),
                Parameter(
                    name="surgery_type",
                    type=ParameterType.CHOICE,
                    required=False,
                    choices=["none", "elective", "emergency"],
                    default="none",
                    description="Type of surgery (none, elective, emergency)"
                )
            ]
        )
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> ValidationResult:
        """验证参数"""
        errors = []
        warnings = []
        
        # 必需参数列表
        required_params = [
            "age", "temperature", "systolic_bp", "diastolic_bp", "heart_rate", 
            "respiratory_rate", "fio2", "ph", "sodium", "potassium", 
            "creatinine", "hematocrit", "wbc", "gcs"
        ]
        
        # 检查必需参数
        for param_name in required_params:
            if param_name not in parameters:
                errors.append(f"Missing required parameter: {param_name}")
        
        if errors:
            return ValidationResult(is_valid=False, errors=errors)
        
        # 验证数值范围
        validations = [
            ("age", 0, 120),
            ("temperature", 25, 45),
            ("systolic_bp", 30, 300),
            ("diastolic_bp", 20, 200),
            ("heart_rate", 20, 250),
            ("respiratory_rate", 5, 80),
            ("fio2", 21, 100),
            ("ph", 6.5, 8.0),
            ("sodium", 100, 200),
            ("potassium", 1.0, 10.0),
            ("creatinine", 0.1, 15.0),
            ("hematocrit", 10, 70),
            ("wbc", 0.1, 100),
            ("gcs", 3, 15)
        ]
        
        for param_name, min_val, max_val in validations:
            if param_name in parameters:
                value = parameters[param_name]
                if value is not None:
                    if value < min_val:
                        errors.append(f"{param_name}: Value {value} is below minimum {min_val}")
                    if value > max_val:
                        errors.append(f"{param_name}: Value {value} is above maximum {max_val}")
        
        # 可选参数验证
        if "pao2" in parameters and parameters["pao2"] is not None:
            pao2 = parameters["pao2"]
            if pao2 < 20 or pao2 > 500:
                errors.append(f"pao2: Value {pao2} is out of range (20-500)")
        
        if "aa_gradient" in parameters and parameters["aa_gradient"] is not None:
            aa_gradient = parameters["aa_gradient"]
            if aa_gradient < 0 or aa_gradient > 700:
                errors.append(f"aa_gradient: Value {aa_gradient} is out of range (0-700)")
        
        # 验证选择类型参数
        surgery_type = parameters.get("surgery_type", "none")
        if surgery_type not in ["none", "elective", "emergency"]:
            errors.append(f"surgery_type: Invalid choice '{surgery_type}'. Must be one of: ['none', 'elective', 'emergency']")
        
        # FiO2相关验证
        fio2 = parameters.get("fio2")
        pao2 = parameters.get("pao2")
        aa_gradient = parameters.get("aa_gradient")
        
        if fio2 is not None:
            if fio2 < 50:
                if pao2 is None:
                    errors.append("PaO2 is required when FiO2 < 50%")
            else:
                if aa_gradient is None:
                    errors.append("A-a gradient is required when FiO2 >= 50%")
        
        # 肾功能验证
        acute_renal = parameters.get("acute_renal_failure", False)
        chronic_renal = parameters.get("chronic_renal_failure", False)
        
        if acute_renal and chronic_renal:
            errors.append("Patient cannot have both acute and chronic renal failure")
        
        # 器官衰竭和手术类型验证
        organ_failure = parameters.get("organ_failure_immunocompromise", False)
        surgery_type = parameters.get("surgery_type", "none")
        
        if organ_failure and surgery_type == "none":
            errors.append("Surgery type must be specified when organ failure/immunocompromise is present")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def calculate(self, parameters: Dict[str, Any]) -> CalculationResult:
        """计算APACHE II评分"""
        
        # 获取参数值
        age = parameters["age"]
        temperature = parameters["temperature"]
        systolic_bp = parameters["systolic_bp"]
        diastolic_bp = parameters["diastolic_bp"]
        heart_rate = parameters["heart_rate"]
        respiratory_rate = parameters["respiratory_rate"]
        fio2 = parameters["fio2"]
        pao2 = parameters.get("pao2")
        aa_gradient = parameters.get("aa_gradient")
        ph = parameters["ph"]
        sodium = parameters["sodium"]
        potassium = parameters["potassium"]
        creatinine = parameters["creatinine"]
        hematocrit = parameters["hematocrit"]
        wbc = parameters["wbc"]
        gcs = parameters["gcs"]
        acute_renal_failure = parameters.get("acute_renal_failure", False)
        chronic_renal_failure = parameters.get("chronic_renal_failure", False)
        organ_failure_immunocompromise = parameters.get("organ_failure_immunocompromise", False)
        surgery_type = parameters.get("surgery_type", "none")
        
        score = 0
        explanation_parts = []
        
        # 1. 年龄评分
        if age < 45:
            age_points = 0
        elif 45 <= age <= 54:
            age_points = 2
        elif 55 <= age <= 64:
            age_points = 3
        elif 65 <= age <= 74:
            age_points = 5
        else:  # >= 75
            age_points = 6
        
        score += age_points
        explanation_parts.append(f"Age {age} years: +{age_points} points")
        
        # 2. 器官衰竭/免疫缺陷史
        if organ_failure_immunocompromise:
            if surgery_type == "elective":
                organ_points = 2
            elif surgery_type == "emergency":
                organ_points = 5
            else:
                organ_points = 5  # nonoperative
        else:
            organ_points = 0
        
        score += organ_points
        if organ_points > 0:
            explanation_parts.append(f"Organ failure/immunocompromise ({surgery_type}): +{organ_points} points")
        
        # 3. 体温评分
        if temperature >= 41:
            temp_points = 4
        elif 39 <= temperature < 41:
            temp_points = 3
        elif 38.5 <= temperature < 39:
            temp_points = 1
        elif 36 <= temperature < 38.5:
            temp_points = 0
        elif 34 <= temperature < 36:
            temp_points = 1
        elif 32 <= temperature < 34:
            temp_points = 2
        elif 30 <= temperature < 32:
            temp_points = 3
        else:  # < 30
            temp_points = 4
        
        score += temp_points
        explanation_parts.append(f"Temperature {temperature}°C: +{temp_points} points")
        
        # 4. 平均动脉压
        map_value = (2 * diastolic_bp + systolic_bp) / 3
        
        if map_value >= 160:
            map_points = 4
        elif 130 <= map_value < 160:
            map_points = 3
        elif 110 <= map_value < 130:
            map_points = 2
        elif 70 <= map_value < 110:
            map_points = 0
        elif 50 <= map_value < 70:
            map_points = 2
        elif 40 <= map_value < 50:
            map_points = 3
        else:  # < 40
            map_points = 4
        
        score += map_points
        explanation_parts.append(f"Mean arterial pressure {round_number(map_value, 1)} mmHg: +{map_points} points")
        
        # 5. 心率评分
        if heart_rate >= 180:
            hr_points = 4
        elif 140 <= heart_rate < 180:
            hr_points = 3
        elif 110 <= heart_rate < 140:
            hr_points = 2
        elif 70 <= heart_rate < 110:
            hr_points = 0
        elif 55 <= heart_rate < 70:
            hr_points = 2
        elif 40 <= heart_rate < 55:
            hr_points = 3
        else:  # < 40
            hr_points = 4
        
        score += hr_points
        explanation_parts.append(f"Heart rate {heart_rate} bpm: +{hr_points} points")
        
        # 6. 呼吸频率评分
        if respiratory_rate >= 50:
            rr_points = 4
        elif 35 <= respiratory_rate < 50:
            rr_points = 3
        elif 25 <= respiratory_rate < 35:
            rr_points = 1
        elif 12 <= respiratory_rate < 25:
            rr_points = 0
        elif 10 <= respiratory_rate < 12:
            rr_points = 1
        elif 6 <= respiratory_rate < 10:
            rr_points = 2
        else:  # < 6
            rr_points = 4
        
        score += rr_points
        explanation_parts.append(f"Respiratory rate {respiratory_rate} breaths/min: +{rr_points} points")
        
        # 7. 氧合评分
        if fio2 >= 50:
            # 使用A-a梯度
            if aa_gradient >= 500:
                oxy_points = 4
            elif 350 <= aa_gradient < 500:
                oxy_points = 3
            elif 200 <= aa_gradient < 350:
                oxy_points = 2
            else:  # < 200
                oxy_points = 0
            explanation_parts.append(f"A-a gradient {aa_gradient} mmHg (FiO2 {fio2}%): +{oxy_points} points")
        else:
            # 使用PaO2
            if pao2 >= 70:
                oxy_points = 0
            elif 61 <= pao2 < 70:
                oxy_points = 1
            elif 55 <= pao2 < 61:
                oxy_points = 3
            else:  # < 55
                oxy_points = 4
            explanation_parts.append(f"PaO2 {pao2} mmHg (FiO2 {fio2}%): +{oxy_points} points")
        
        score += oxy_points
        
        # 8. pH评分
        if ph >= 7.7:
            ph_points = 4
        elif 7.6 <= ph < 7.7:
            ph_points = 3
        elif 7.5 <= ph < 7.6:
            ph_points = 1
        elif 7.33 <= ph < 7.5:
            ph_points = 0
        elif 7.25 <= ph < 7.33:
            ph_points = 2
        elif 7.15 <= ph < 7.25:
            ph_points = 3
        else:  # < 7.15
            ph_points = 4
        
        score += ph_points
        explanation_parts.append(f"Arterial pH {ph}: +{ph_points} points")
        
        # 9. 钠评分
        if sodium >= 180:
            na_points = 4
        elif 160 <= sodium < 180:
            na_points = 3
        elif 155 <= sodium < 160:
            na_points = 2
        elif 150 <= sodium < 155:
            na_points = 1
        elif 130 <= sodium < 150:
            na_points = 0
        elif 120 <= sodium < 130:
            na_points = 2
        elif 111 <= sodium < 120:
            na_points = 3
        else:  # < 111
            na_points = 4
        
        score += na_points
        explanation_parts.append(f"Serum sodium {sodium} mmol/L: +{na_points} points")
        
        # 10. 钾评分
        if potassium >= 7.0:
            k_points = 4
        elif 6.0 <= potassium < 7.0:
            k_points = 3
        elif 5.5 <= potassium < 6.0:
            k_points = 1
        elif 3.5 <= potassium < 5.5:
            k_points = 0
        elif 3.0 <= potassium < 3.5:
            k_points = 1
        elif 2.5 <= potassium < 3.0:
            k_points = 2
        else:  # < 2.5
            k_points = 4
        
        score += k_points
        explanation_parts.append(f"Serum potassium {potassium} mmol/L: +{k_points} points")
        
        # 11. 肌酐评分
        if creatinine >= 3.5 and acute_renal_failure:
            cr_points = 8
        elif 2.0 <= creatinine < 3.5 and acute_renal_failure:
            cr_points = 6
        elif creatinine >= 3.5 and chronic_renal_failure:
            cr_points = 4
        elif 1.5 <= creatinine < 2.0 and acute_renal_failure:
            cr_points = 4
        elif 2.0 <= creatinine < 3.5 and chronic_renal_failure:
            cr_points = 3
        elif 1.5 <= creatinine < 2.0 and chronic_renal_failure:
            cr_points = 2
        elif 0.6 <= creatinine < 1.5:
            cr_points = 0
        else:  # < 0.6
            cr_points = 2
        
        score += cr_points
        renal_status = ""
        if acute_renal_failure:
            renal_status = " (acute renal failure)"
        elif chronic_renal_failure:
            renal_status = " (chronic renal failure)"
        explanation_parts.append(f"Serum creatinine {creatinine} mg/dL{renal_status}: +{cr_points} points")
        
        # 12. 血细胞比容评分
        if hematocrit >= 60:
            hct_points = 4
        elif 50 <= hematocrit < 60:
            hct_points = 2
        elif 46 <= hematocrit < 50:
            hct_points = 1
        elif 30 <= hematocrit < 46:
            hct_points = 0
        elif 20 <= hematocrit < 30:
            hct_points = 2
        else:  # < 20
            hct_points = 4
        
        score += hct_points
        explanation_parts.append(f"Hematocrit {hematocrit}%: +{hct_points} points")
        
        # 13. 白细胞计数评分
        if wbc >= 40:
            wbc_points = 4
        elif 20 <= wbc < 40:
            wbc_points = 2
        elif 15 <= wbc < 20:
            wbc_points = 1
        elif 3 <= wbc < 15:
            wbc_points = 0
        elif 1 <= wbc < 3:
            wbc_points = 2
        else:  # < 1
            wbc_points = 4
        
        score += wbc_points
        explanation_parts.append(f"White blood cell count {wbc} ×10³/mm³: +{wbc_points} points")
        
        # 14. Glasgow昏迷评分
        gcs_points = 15 - gcs
        score += gcs_points
        explanation_parts.append(f"Glasgow Coma Scale {gcs}: +{gcs_points} points (15 - GCS)")
        
        # 生成解释
        explanation = "APACHE II Score calculation:\n\n"
        explanation += "\n".join([f"• {part}" for part in explanation_parts])
        explanation += f"\n\nTotal APACHE II Score: {score} points"
        
        # 添加风险解释
        if score < 10:
            risk_category = "Low risk"
            mortality_risk = "<10%"
        elif score < 15:
            risk_category = "Moderate risk"
            mortality_risk = "10-25%"
        elif score < 20:
            risk_category = "High risk"
            mortality_risk = "25-50%"
        elif score < 25:
            risk_category = "Very high risk"
            mortality_risk = "50-75%"
        else:
            risk_category = "Extremely high risk"
            mortality_risk = ">75%"
        
        explanation += f"\n\nRisk Category: {risk_category}"
        explanation += f"\nEstimated Hospital Mortality: {mortality_risk}"
        
        return CalculationResult(
            value=score,
            unit="points",
            explanation=explanation,
            metadata={
                "age_points": age_points,
                "organ_failure_points": organ_points,
                "temperature_points": temp_points,
                "map_points": map_points,
                "heart_rate_points": hr_points,
                "respiratory_rate_points": rr_points,
                "oxygenation_points": oxy_points,
                "ph_points": ph_points,
                "sodium_points": na_points,
                "potassium_points": k_points,
                "creatinine_points": cr_points,
                "hematocrit_points": hct_points,
                "wbc_points": wbc_points,
                "gcs_points": gcs_points,
                "risk_category": risk_category,
                "mortality_risk": mortality_risk,
                "map_value": round_number(map_value, 1)
            }
        )
