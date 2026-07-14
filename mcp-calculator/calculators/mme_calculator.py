"""
MME (Morphine Milligram Equivalent) Calculator
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


@register_calculator("mme")
class MMECalculator(BaseCalculator):
    """吗啡毫克当量计算器实现"""
    
    # MME转换因子字典
    MME_CONVERSION_FACTORS = {
        "codeine": 0.15,
        "fentanyl_buccal": 0.13,
        "fentanyl_patch": 2.4,
        "hydrocodone": 1.0,
        "hydromorphone": 5.0,
        "methadone": 4.7,
        "morphine": 1.0,
        "oxycodone": 1.5,
        "oxymorphone": 3.0,
        "tapentadol": 0.4,
        "tramadol": 0.2,
        "buprenorphine": 10.0
    }
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=49,
            name="MME (Morphine Milligram Equivalent) Calculator",
            category="pharmacology",
            description="Calculate total daily morphine milligram equivalents for opioid medications",
            parameters=[
                Parameter(
                    name="codeine_dose",
                    type=ParameterType.NUMERIC,
                    required=False,
                    unit="mg",
                    min_value=0,
                    max_value=1000,
                    description="Codeine dose per administration (mg)"
                ),
                Parameter(
                    name="codeine_frequency",
                    type=ParameterType.NUMERIC,
                    required=False,
                    min_value=0,
                    max_value=24,
                    description="Codeine doses per day"
                ),
                Parameter(
                    name="hydrocodone_dose",
                    type=ParameterType.NUMERIC,
                    required=False,
                    unit="mg",
                    min_value=0,
                    max_value=100,
                    description="Hydrocodone dose per administration (mg)"
                ),
                Parameter(
                    name="hydrocodone_frequency",
                    type=ParameterType.NUMERIC,
                    required=False,
                    min_value=0,
                    max_value=24,
                    description="Hydrocodone doses per day"
                ),
                Parameter(
                    name="oxycodone_dose",
                    type=ParameterType.NUMERIC,
                    required=False,
                    unit="mg",
                    min_value=0,
                    max_value=200,
                    description="Oxycodone dose per administration (mg)"
                ),
                Parameter(
                    name="oxycodone_frequency",
                    type=ParameterType.NUMERIC,
                    required=False,
                    min_value=0,
                    max_value=24,
                    description="Oxycodone doses per day"
                ),
                Parameter(
                    name="morphine_dose",
                    type=ParameterType.NUMERIC,
                    required=False,
                    unit="mg",
                    min_value=0,
                    max_value=500,
                    description="Morphine dose per administration (mg)"
                ),
                Parameter(
                    name="morphine_frequency",
                    type=ParameterType.NUMERIC,
                    required=False,
                    min_value=0,
                    max_value=24,
                    description="Morphine doses per day"
                ),
                Parameter(
                    name="hydromorphone_dose",
                    type=ParameterType.NUMERIC,
                    required=False,
                    unit="mg",
                    min_value=0,
                    max_value=100,
                    description="Hydromorphone dose per administration (mg)"
                ),
                Parameter(
                    name="hydromorphone_frequency",
                    type=ParameterType.NUMERIC,
                    required=False,
                    min_value=0,
                    max_value=24,
                    description="Hydromorphone doses per day"
                ),
                Parameter(
                    name="fentanyl_patch_dose",
                    type=ParameterType.NUMERIC,
                    required=False,
                    unit="mg",
                    min_value=0,
                    max_value=300,
                    description="Fentanyl patch dose (mg)"
                ),
                Parameter(
                    name="fentanyl_patch_frequency",
                    type=ParameterType.NUMERIC,
                    required=False,
                    min_value=0,
                    max_value=24,
                    description="Fentanyl patch doses per day"
                ),
                Parameter(
                    name="tramadol_dose",
                    type=ParameterType.NUMERIC,
                    required=False,
                    unit="mg",
                    min_value=0,
                    max_value=400,
                    description="Tramadol dose per administration (mg)"
                ),
                Parameter(
                    name="tramadol_frequency",
                    type=ParameterType.NUMERIC,
                    required=False,
                    min_value=0,
                    max_value=24,
                    description="Tramadol doses per day"
                ),
                Parameter(
                    name="tapentadol_dose",
                    type=ParameterType.NUMERIC,
                    required=False,
                    unit="mg",
                    min_value=0,
                    max_value=500,
                    description="Tapentadol dose per administration (mg)"
                ),
                Parameter(
                    name="tapentadol_frequency",
                    type=ParameterType.NUMERIC,
                    required=False,
                    min_value=0,
                    max_value=24,
                    description="Tapentadol doses per day"
                ),
                Parameter(
                    name="methadone_dose",
                    type=ParameterType.NUMERIC,
                    required=False,
                    unit="mg",
                    min_value=0,
                    max_value=200,
                    description="Methadone dose per administration (mg)"
                ),
                Parameter(
                    name="methadone_frequency",
                    type=ParameterType.NUMERIC,
                    required=False,
                    min_value=0,
                    max_value=24,
                    description="Methadone doses per day"
                ),
                Parameter(
                    name="oxymorphone_dose",
                    type=ParameterType.NUMERIC,
                    required=False,
                    unit="mg",
                    min_value=0,
                    max_value=100,
                    description="Oxymorphone dose per administration (mg)"
                ),
                Parameter(
                    name="oxymorphone_frequency",
                    type=ParameterType.NUMERIC,
                    required=False,
                    min_value=0,
                    max_value=24,
                    description="Oxymorphone doses per day"
                ),
                Parameter(
                    name="buprenorphine_dose",
                    type=ParameterType.NUMERIC,
                    required=False,
                    unit="mg",
                    min_value=0,
                    max_value=32,
                    description="Buprenorphine dose per administration (mg)"
                ),
                Parameter(
                    name="buprenorphine_frequency",
                    type=ParameterType.NUMERIC,
                    required=False,
                    min_value=0,
                    max_value=24,
                    description="Buprenorphine doses per day"
                ),
                Parameter(
                    name="fentanyl_buccal_dose",
                    type=ParameterType.NUMERIC,
                    required=False,
                    unit="µg",
                    min_value=0,
                    max_value=1600,
                    description="Fentanyl buccal dose per administration (µg)"
                ),
                Parameter(
                    name="fentanyl_buccal_frequency",
                    type=ParameterType.NUMERIC,
                    required=False,
                    min_value=0,
                    max_value=24,
                    description="Fentanyl buccal doses per day"
                )
            ]
        )
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> ValidationResult:
        """验证参数"""
        errors = []
        
        # 获取参数定义
        param_defs = {p.name: p for p in self.get_info().parameters}
        
        # 验证参数类型和范围
        for param_name, value in parameters.items():
            if param_name in param_defs:
                param_def = param_defs[param_name]
                if value is not None:
                    # 验证数值类型
                    try:
                        value = float(value)
                        if value < 0:
                            errors.append(f"Parameter {param_name} must be non-negative")
                        # 验证范围
                        error = self.validate_numeric_range(value, param_def)
                        if error:
                            errors.append(error)
                    except (ValueError, TypeError):
                        errors.append(f"Parameter {param_name} must be a number")
        
        # 检查是否至少提供了一种药物
        has_medication = False
        medication_pairs = [
            ("codeine_dose", "codeine_frequency"),
            ("hydrocodone_dose", "hydrocodone_frequency"),
            ("oxycodone_dose", "oxycodone_frequency"),
            ("morphine_dose", "morphine_frequency"),
            ("hydromorphone_dose", "hydromorphone_frequency"),
            ("fentanyl_patch_dose", "fentanyl_patch_frequency"),
            ("fentanyl_buccal_dose", "fentanyl_buccal_frequency"),
            ("tramadol_dose", "tramadol_frequency"),
            ("tapentadol_dose", "tapentadol_frequency"),
            ("methadone_dose", "methadone_frequency"),
            ("oxymorphone_dose", "oxymorphone_frequency"),
            ("buprenorphine_dose", "buprenorphine_frequency")
        ]
        
        for dose_param, freq_param in medication_pairs:
            dose = parameters.get(dose_param)
            freq = parameters.get(freq_param)
            if dose is not None and dose > 0:
                has_medication = True
                if freq is None or freq <= 0:
                    errors.append(f"If {dose_param} is provided, {freq_param} must also be provided and greater than 0")
        
        if not has_medication:
            errors.append("At least one opioid medication dose must be provided")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )
    
    def calculate(self, parameters: Dict[str, Any]) -> CalculationResult:
        """计算MME总量"""
        
        total_mme = 0
        explanation_parts = []
        medication_details = []
        
        # 处理常规阿片类药物（需要剂量和频次）
        medications = [
            ("codeine", "codeine_dose", "codeine_frequency", "mg"),
            ("hydrocodone", "hydrocodone_dose", "hydrocodone_frequency", "mg"),
            ("oxycodone", "oxycodone_dose", "oxycodone_frequency", "mg"),
            ("morphine", "morphine_dose", "morphine_frequency", "mg"),
            ("hydromorphone", "hydromorphone_dose", "hydromorphone_frequency", "mg"),
            ("tramadol", "tramadol_dose", "tramadol_frequency", "mg"),
            ("tapentadol", "tapentadol_dose", "tapentadol_frequency", "mg"),
            ("methadone", "methadone_dose", "methadone_frequency", "mg"),
            ("oxymorphone", "oxymorphone_dose", "oxymorphone_frequency", "mg"),
            ("buprenorphine", "buprenorphine_dose", "buprenorphine_frequency", "mg")
        ]
        
        for med_name, dose_param, freq_param, unit in medications:
            dose = parameters.get(dose_param, 0)
            frequency = parameters.get(freq_param, 0)
            
            if dose > 0 and frequency > 0:
                daily_dose = dose * frequency
                conversion_factor = self.MME_CONVERSION_FACTORS[med_name]
                med_mme = daily_dose * conversion_factor
                total_mme += med_mme
                
                medication_details.append({
                    "name": med_name.title(),
                    "dose": dose,
                    "frequency": frequency,
                    "daily_dose": daily_dose,
                    "conversion_factor": conversion_factor,
                    "mme": round_number(med_mme, 1),
                    "unit": unit
                })
                
                explanation_parts.append(
                    f"• {med_name.title()}: {dose} {unit} × {frequency} doses/day = {daily_dose} {unit}/day"
                )
                explanation_parts.append(
                    f"  MME: {daily_dose} {unit}/day × {conversion_factor} = {round_number(med_mme, 1)} MME/day"
                )
        
        # 处理芬太尼贴片（特殊处理：按原始算法逻辑）
        fentanyl_patch_dose = parameters.get("fentanyl_patch_dose", 0)
        fentanyl_patch_frequency = parameters.get("fentanyl_patch_frequency", 0)
        if fentanyl_patch_dose > 0 and fentanyl_patch_frequency > 0:
            # 按原始算法：dose_per_day * mme_conversion_factor * dose_in_mg
            # 这里dose已经是mg单位，所以直接计算
            conversion_factor = self.MME_CONVERSION_FACTORS["fentanyl_patch"]
            med_mme = fentanyl_patch_frequency * conversion_factor * fentanyl_patch_dose
            total_mme += med_mme
            
            daily_dose = fentanyl_patch_dose * fentanyl_patch_frequency
            
            medication_details.append({
                "name": "Fentanyl Patch",
                "dose": fentanyl_patch_dose,
                "frequency": fentanyl_patch_frequency,
                "daily_dose": daily_dose,
                "conversion_factor": conversion_factor,
                "mme": round_number(med_mme, 1),
                "unit": "mg"
            })
            
            explanation_parts.append(
                f"• Fentanyl Patch: {fentanyl_patch_dose} mg × {fentanyl_patch_frequency} doses/day = {daily_dose} mg/day"
            )
            explanation_parts.append(
                f"  MME: {fentanyl_patch_frequency} doses/day × {conversion_factor} × {fentanyl_patch_dose} mg = {round_number(med_mme, 1)} MME/day"
            )
        
        # 处理芬太尼颊粘膜（特殊处理：单位为µg）
        fentanyl_buccal_dose = parameters.get("fentanyl_buccal_dose", 0)
        fentanyl_buccal_frequency = parameters.get("fentanyl_buccal_frequency", 0)
        if fentanyl_buccal_dose > 0 and fentanyl_buccal_frequency > 0:
            # 按原始算法：dose_per_day * mme_conversion_factor * dose_in_µg
            # 这里dose已经是µg单位，所以直接计算
            conversion_factor = self.MME_CONVERSION_FACTORS["fentanyl_buccal"]
            med_mme = fentanyl_buccal_frequency * conversion_factor * fentanyl_buccal_dose
            total_mme += med_mme
            
            daily_dose = fentanyl_buccal_dose * fentanyl_buccal_frequency
            
            medication_details.append({
                "name": "Fentanyl Buccal",
                "dose": fentanyl_buccal_dose,
                "frequency": fentanyl_buccal_frequency,
                "daily_dose": daily_dose,
                "conversion_factor": conversion_factor,
                "mme": round_number(med_mme, 1),
                "unit": "µg"
            })
            
            explanation_parts.append(
                f"• Fentanyl Buccal: {fentanyl_buccal_dose} µg × {fentanyl_buccal_frequency} doses/day = {daily_dose} µg/day"
            )
            explanation_parts.append(
                f"  MME: {fentanyl_buccal_frequency} doses/day × {conversion_factor} × {fentanyl_buccal_dose} µg = {round_number(med_mme, 1)} MME/day"
            )
        
        # 四舍五入总MME
        total_mme = round_number(total_mme, 1)
        
        # 生成解释
        explanation = "Morphine Milligram Equivalent (MME) calculation:\n\n"
        explanation += "Opioid medications and their MME conversion factors:\n"
        
        if explanation_parts:
            explanation += "\n".join(explanation_parts)
            explanation += f"\n\nTotal daily MME: {total_mme} MME/day"
        else:
            explanation += "No opioid medications provided"
        
        # 添加风险评估
        if total_mme >= 90:
            risk_level = "High risk"
            recommendation = "Consider dose reduction, alternative therapies, or specialist consultation"
        elif total_mme >= 50:
            risk_level = "Increased risk"
            recommendation = "Monitor closely, consider dose optimization"
        elif total_mme > 0:
            risk_level = "Standard monitoring"
            recommendation = "Continue standard monitoring and assessment"
        else:
            risk_level = "No opioids"
            recommendation = "No opioid-related monitoring needed"
        
        explanation += f"\n\nRisk Assessment:"
        explanation += f"\n• Risk Level: {risk_level}"
        explanation += f"\n• Recommendation: {recommendation}"
        
        # 添加CDC指导原则
        explanation += "\n\nCDC Guidelines:"
        explanation += "\n• <50 MME/day: Standard monitoring"
        explanation += "\n• 50-90 MME/day: Increased caution and monitoring"
        explanation += "\n• ≥90 MME/day: High risk, consider alternatives"
        
        return CalculationResult(
            value=total_mme,
            unit="MME/day",
            explanation=explanation,
            metadata={
                "risk_level": risk_level,
                "recommendation": recommendation,
                "medication_details": medication_details,
                "cdc_threshold_50": total_mme >= 50,
                "cdc_threshold_90": total_mme >= 90
            }
        )
