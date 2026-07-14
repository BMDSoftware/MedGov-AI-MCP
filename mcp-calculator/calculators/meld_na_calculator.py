"""
MELD Na Score Calculator
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


@register_calculator("meld_na")
class MeldNaCalculator(BaseCalculator):
    """MELD Na评分计算器实现"""
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=23,
            name="MELD Na Score",
            category="hepatology",
            description="Calculate MELD Na score for end-stage liver disease severity assessment",
            parameters=[
                Parameter(
                    name="creatinine",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="mg/dL",
                    min_value=0.1,
                    max_value=20,
                    description="Serum creatinine in mg/dL"
                ),
                Parameter(
                    name="bilirubin",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="mg/dL",
                    min_value=0.1,
                    max_value=50,
                    description="Total bilirubin in mg/dL"
                ),
                Parameter(
                    name="inr",
                    type=ParameterType.NUMERIC,
                    required=True,
                    min_value=0.5,
                    max_value=10,
                    description="International Normalized Ratio (INR)"
                ),
                Parameter(
                    name="sodium",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="mEq/L",
                    min_value=100,
                    max_value=160,
                    description="Serum sodium in mEq/L"
                ),
                Parameter(
                    name="dialysis_twice",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Dialysis at least twice in the past week"
                ),
                Parameter(
                    name="cvvhd",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Continuous veno-venous hemodialysis in the past 24 hours"
                )
            ]
        )
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> ValidationResult:
        """验证输入参数"""
        errors = []
        
        # 获取参数值
        creatinine = parameters.get("creatinine")
        bilirubin = parameters.get("bilirubin")
        inr = parameters.get("inr")
        sodium = parameters.get("sodium")
        
        # 验证必需参数
        if creatinine is None:
            errors.append("creatinine is required")
        elif not isinstance(creatinine, (int, float)) or creatinine <= 0:
            errors.append("creatinine must be a positive number")
            
        if bilirubin is None:
            errors.append("bilirubin is required")
        elif not isinstance(bilirubin, (int, float)) or bilirubin <= 0:
            errors.append("bilirubin must be a positive number")
            
        if inr is None:
            errors.append("inr is required")
        elif not isinstance(inr, (int, float)) or inr <= 0:
            errors.append("inr must be a positive number")
            
        if sodium is None:
            errors.append("sodium is required")
        elif not isinstance(sodium, (int, float)) or sodium <= 0:
            errors.append("sodium must be a positive number")
            
        return ValidationResult(is_valid=len(errors) == 0, errors=errors)
    
    def calculate(self, parameters: Dict[str, Any]) -> CalculationResult:
        """计算MELD Na评分"""
        # 获取参数值
        creatinine = float(parameters.get("creatinine"))
        bilirubin = float(parameters.get("bilirubin"))
        inr = float(parameters.get("inr"))
        sodium = float(parameters.get("sodium"))
        dialysis_twice = parameters.get("dialysis_twice", False)
        cvvhd = parameters.get("cvvhd", False)
        
        # 应用限制条件
        original_values = {
            "creatinine": creatinine,
            "bilirubin": bilirubin,
            "inr": inr,
            "sodium": sodium
        }
        
        # 肌酐限制
        if creatinine < 1.0:
            creatinine = 1.0
        elif creatinine > 4.0:
            creatinine = 4.0
        elif dialysis_twice or cvvhd:
            creatinine = 4.0
            
        # 胆红素限制
        if bilirubin < 1.0:
            bilirubin = 1.0
            
        # INR限制
        if inr < 1.0:
            inr = 1.0
            
        # 钠限制
        if sodium < 125:
            sodium = 125
        elif sodium > 137:
            sodium = 137
        
        # 计算MELD(i)
        meld_i = 0.957 * math.log(creatinine) + 0.378 * math.log(bilirubin) + 1.120 * math.log(inr) + 0.643
        meld_i_rounded = round(meld_i, 1)
        meld_10 = round(meld_i_rounded * 10)
        
        # 计算最终MELD Na评分
        if meld_10 > 11:
            meld_na = round(meld_10 + 1.32 * (137 - sodium) - (0.033 * meld_10 * (137 - sodium)))
            if meld_na > 40:
                meld_na = 40
        else:
            meld_na = meld_10
        
        # 生成解释
        explanation = self._generate_explanation(
            original_values, creatinine, bilirubin, inr, sodium,
            dialysis_twice, cvvhd, meld_i, meld_i_rounded, meld_10, meld_na
        )
        
        # 解释严重程度
        severity = self._interpret_score(meld_na)
        
        return CalculationResult(
            value=meld_na,
            explanation=explanation,
            metadata={
                "original_creatinine": original_values["creatinine"],
                "original_bilirubin": original_values["bilirubin"],
                "original_inr": original_values["inr"],
                "original_sodium": original_values["sodium"],
                "adjusted_creatinine": creatinine,
                "adjusted_bilirubin": bilirubin,
                "adjusted_inr": inr,
                "adjusted_sodium": sodium,
                "dialysis_twice": dialysis_twice,
                "cvvhd": cvvhd,
                "meld_i": meld_i,
                "meld_i_rounded": meld_i_rounded,
                "meld_10": meld_10,
                "meld_na_score": meld_na,
                "severity": severity
            }
        )
    
    def _generate_explanation(self, original_values: Dict, creatinine: float, bilirubin: float, 
                            inr: float, sodium: float, dialysis_twice: bool, cvvhd: bool,
                            meld_i: float, meld_i_rounded: float, meld_10: int, meld_na: int) -> str:
        """生成计算解释"""
        explanation = """MELD Na Score Calculation:

The formula for computing the MELD Na is to first apply the following equation:
MELD(i) = 0.957 × ln(Cr) + 0.378 × ln(bilirubin) + 1.120 × ln(INR) + 0.643

If the MELD(i) is greater than 11 after rounding to the nearest tenth and multiplying by 10, we apply:
MELD = MELD(i) + 1.32 × (137 - Na) - [0.033 × MELD(i) × (137 - Na)]

The MELD Na score is capped at 40.

"""
        
        # 参数调整说明
        explanation += f"Original values: Creatinine {original_values['creatinine']} mg/dL, Bilirubin {original_values['bilirubin']} mg/dL, INR {original_values['inr']}, Sodium {original_values['sodium']} mEq/L\n\n"
        
        # 透析状态
        if dialysis_twice:
            explanation += "Patient has undergone dialysis at least twice in the past week.\n"
        if cvvhd:
            explanation += "Patient has undergone continuous veno-venous hemodialysis in the past 24 hours.\n"
        
        # 肌酐调整
        if original_values['creatinine'] < 1.0:
            explanation += f"Creatinine < 1.0 mg/dL, setting to 1.0 mg/dL.\n"
        elif original_values['creatinine'] > 4.0:
            explanation += f"Creatinine > 4.0 mg/dL, setting to 4.0 mg/dL.\n"
        elif dialysis_twice or cvvhd:
            explanation += f"Due to dialysis history, setting creatinine to 4.0 mg/dL.\n"
        
        # 胆红素调整
        if original_values['bilirubin'] < 1.0:
            explanation += f"Bilirubin < 1.0 mg/dL, setting to 1.0 mg/dL.\n"
        
        # INR调整
        if original_values['inr'] < 1.0:
            explanation += f"INR < 1.0, setting to 1.0.\n"
        
        # 钠调整
        if original_values['sodium'] < 125:
            explanation += f"Sodium < 125 mEq/L, setting to 125 mEq/L.\n"
        elif original_values['sodium'] > 137:
            explanation += f"Sodium > 137 mEq/L, setting to 137 mEq/L.\n"
        
        explanation += f"\nAdjusted values: Creatinine {creatinine} mg/dL, Bilirubin {bilirubin} mg/dL, INR {inr}, Sodium {sodium} mEq/L\n\n"
        
        # MELD(i)计算
        explanation += f"MELD(i) = 0.957 × ln({creatinine}) + 0.378 × ln({bilirubin}) + 1.120 × ln({inr}) + 0.643 = {meld_i:.3f}\n"
        explanation += f"Rounded to nearest tenth: {meld_i_rounded}\n"
        explanation += f"Multiplied by 10: {meld_10}\n\n"
        
        # 最终计算
        if meld_10 > 11:
            raw_meld = meld_10 + 1.32 * (137 - sodium) - (0.033 * meld_10 * (137 - sodium))
            explanation += f"Since MELD(i) > 11, applying second equation:\n"
            explanation += f"MELD = {meld_10} + 1.32 × (137 - {sodium}) - [0.033 × {meld_10} × (137 - {sodium})] = {raw_meld:.1f}\n"
            
            if raw_meld > 40:
                explanation += f"Score exceeds 40, capping at 40.\n"
            else:
                explanation += f"Final MELD Na score: {meld_na}\n"
        else:
            explanation += f"Since MELD(i) ≤ 11, final MELD Na score: {meld_na}\n"
        
        return explanation
    
    def _interpret_score(self, score: int) -> str:
        """解释MELD Na评分严重程度"""
        if score >= 40:
            return "Maximum severity (40)"
        elif score >= 30:
            return "Very high mortality risk"
        elif score >= 20:
            return "High mortality risk"
        elif score >= 15:
            return "Moderate mortality risk"
        elif score >= 10:
            return "Low-moderate mortality risk"
        else:
            return "Low mortality risk"
