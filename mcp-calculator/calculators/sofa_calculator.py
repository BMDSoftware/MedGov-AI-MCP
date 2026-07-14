"""
SOFA (Sequential Organ Failure Assessment) Calculator
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


@register_calculator("sofa")
class SOFACalculator(BaseCalculator):
    """SOFA序贯器官衰竭评估计算器实现"""
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=43,
            name="SOFA Score (Sequential Organ Failure Assessment)",
            category="critical_care",
            description="Sequential Organ Failure Assessment score for evaluating organ dysfunction in ICU patients",
            parameters=[
                Parameter(
                    name="pao2",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="mmHg",
                    min_value=20,
                    max_value=500,
                    description="Partial pressure of oxygen in mmHg"
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
                    name="mechanical_ventilation",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Patient on mechanical ventilation"
                ),
                Parameter(
                    name="cpap",
                    type=ParameterType.BOOLEAN,
                    required=False,
                    default=False,
                    description="Patient on continuous positive airway pressure"
                ),
                Parameter(
                    name="platelets",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="×10³/µL",
                    min_value=1,
                    max_value=1000,
                    description="Platelet count in thousands per microliter"
                ),
                Parameter(
                    name="gcs",
                    type=ParameterType.NUMERIC,
                    required=False,
                    min_value=3,
                    max_value=15,
                    default=15,
                    description="Glasgow Coma Scale score"
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
                    name="systolic_bp",
                    type=ParameterType.NUMERIC,
                    required=False,
                    unit="mmHg",
                    min_value=30,
                    max_value=300,
                    description="Systolic blood pressure in mmHg"
                ),
                Parameter(
                    name="diastolic_bp",
                    type=ParameterType.NUMERIC,
                    required=False,
                    unit="mmHg",
                    min_value=20,
                    max_value=200,
                    description="Diastolic blood pressure in mmHg"
                ),
                Parameter(
                    name="dopamine",
                    type=ParameterType.NUMERIC,
                    required=False,
                    unit="µg/kg/min",
                    min_value=0,
                    max_value=50,
                    default=0,
                    description="Dopamine dose in µg/kg/min"
                ),
                Parameter(
                    name="dobutamine",
                    type=ParameterType.NUMERIC,
                    required=False,
                    unit="µg/kg/min",
                    min_value=0,
                    max_value=50,
                    default=0,
                    description="Dobutamine dose in µg/kg/min"
                ),
                Parameter(
                    name="epinephrine",
                    type=ParameterType.NUMERIC,
                    required=False,
                    unit="µg/kg/min",
                    min_value=0,
                    max_value=5,
                    default=0,
                    description="Epinephrine dose in µg/kg/min"
                ),
                Parameter(
                    name="norepinephrine",
                    type=ParameterType.NUMERIC,
                    required=False,
                    unit="µg/kg/min",
                    min_value=0,
                    max_value=5,
                    default=0,
                    description="Norepinephrine dose in µg/kg/min"
                ),
                Parameter(
                    name="creatinine",
                    type=ParameterType.NUMERIC,
                    required=False,
                    unit="mg/dL",
                    min_value=0.1,
                    max_value=15,
                    description="Serum creatinine in mg/dL"
                ),
                Parameter(
                    name="urine_output",
                    type=ParameterType.NUMERIC,
                    required=False,
                    unit="mL/day",
                    min_value=0,
                    max_value=5000,
                    description="Urine output in mL/day"
                )
            ]
        )
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> ValidationResult:
        """验证参数"""
        errors = []
        warnings = []
        
        # 获取参数定义
        param_defs = {p.name: p for p in self.get_info().parameters}
        
        # 检查必需参数
        for param_name, param_def in param_defs.items():
            if param_def.required and param_name not in parameters:
                errors.append(f"Missing required parameter: {param_name}")
        
        # 验证数值范围
        for param_name, value in parameters.items():
            if param_name in param_defs:
                param_def = param_defs[param_name]
                if param_def.type == ParameterType.NUMERIC:
                    if not isinstance(value, (int, float)):
                        errors.append(f"Parameter '{param_name}' must be numeric")
                    else:
                        if param_def.min_value is not None and value < param_def.min_value:
                            errors.append(f"Parameter '{param_name}' ({value}) is below minimum value ({param_def.min_value})")
                        if param_def.max_value is not None and value > param_def.max_value:
                            errors.append(f"Parameter '{param_name}' ({value}) is above maximum value ({param_def.max_value})")
                elif param_def.type == ParameterType.BOOLEAN:
                    if not isinstance(value, bool):
                        errors.append(f"Parameter '{param_name}' must be boolean")
        
        # 肾功能评估需要肌酐或尿量之一
        creatinine = parameters.get("creatinine")
        urine_output = parameters.get("urine_output")
        
        if creatinine is None and urine_output is None:
            errors.append("Either creatinine or urine output is required for renal assessment")
        
        # 心血管评估需要血压或血管活性药物
        systolic_bp = parameters.get("systolic_bp")
        diastolic_bp = parameters.get("diastolic_bp")
        dopamine = parameters.get("dopamine", 0)
        dobutamine = parameters.get("dobutamine", 0)
        epinephrine = parameters.get("epinephrine", 0)
        norepinephrine = parameters.get("norepinephrine", 0)
        
        has_bp = systolic_bp is not None and diastolic_bp is not None
        has_vasopressors = any([dopamine > 0, dobutamine > 0, epinephrine > 0, norepinephrine > 0])
        
        if not has_bp and not has_vasopressors:
            errors.append("Blood pressure or vasopressor information is required for cardiovascular assessment")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def calculate(self, parameters: Dict[str, Any]) -> CalculationResult:
        """计算SOFA评分"""
        
        # 获取参数值
        pao2 = parameters["pao2"]
        fio2 = parameters["fio2"]
        mechanical_ventilation = parameters.get("mechanical_ventilation", False)
        cpap = parameters.get("cpap", False)
        platelets = parameters["platelets"]
        gcs = parameters.get("gcs", 15)
        bilirubin = parameters["bilirubin"]
        systolic_bp = parameters.get("systolic_bp")
        diastolic_bp = parameters.get("diastolic_bp")
        dopamine = parameters.get("dopamine", 0)
        dobutamine = parameters.get("dobutamine", 0)
        epinephrine = parameters.get("epinephrine", 0)
        norepinephrine = parameters.get("norepinephrine", 0)
        creatinine = parameters.get("creatinine")
        urine_output = parameters.get("urine_output")
        
        total_score = 0
        explanation_parts = []
        organ_scores = {}
        
        # 1. 呼吸系统 (PaO2/FiO2比值)
        pao2_fio2_ratio = round_number(pao2 / (fio2 / 100), 1)
        respiratory_support = mechanical_ventilation or cpap
        
        if pao2_fio2_ratio >= 400:
            resp_score = 0
        elif 300 <= pao2_fio2_ratio < 400:
            resp_score = 1
        elif 200 <= pao2_fio2_ratio < 300:
            resp_score = 2
        elif 100 <= pao2_fio2_ratio < 200 and respiratory_support:
            resp_score = 3
        elif pao2_fio2_ratio < 100 and respiratory_support:
            resp_score = 4
        else:
            # 如果PaO2/FiO2 < 200但无呼吸支持，按2分计算
            resp_score = 2
        
        total_score += resp_score
        organ_scores["respiratory"] = resp_score
        support_text = " (with respiratory support)" if respiratory_support else ""
        explanation_parts.append(f"Respiratory: PaO2/FiO2 ratio {pao2_fio2_ratio}{support_text} = {resp_score} points")
        
        # 2. 凝血系统 (血小板计数)
        if platelets >= 150:
            coag_score = 0
        elif 100 <= platelets < 150:
            coag_score = 1
        elif 50 <= platelets < 100:
            coag_score = 2
        elif 20 <= platelets < 50:
            coag_score = 3
        else:  # < 20
            coag_score = 4
        
        total_score += coag_score
        organ_scores["coagulation"] = coag_score
        explanation_parts.append(f"Coagulation: Platelets {platelets} ×10³/µL = {coag_score} points")
        
        # 3. 肝脏系统 (胆红素)
        if bilirubin < 1.2:
            liver_score = 0
        elif 1.2 <= bilirubin < 2.0:
            liver_score = 1
        elif 2.0 <= bilirubin < 6.0:
            liver_score = 2
        elif 6.0 <= bilirubin < 12.0:
            liver_score = 3
        else:  # >= 12.0
            liver_score = 4
        
        total_score += liver_score
        organ_scores["liver"] = liver_score
        explanation_parts.append(f"Liver: Bilirubin {bilirubin} mg/dL = {liver_score} points")
        
        # 4. 心血管系统 (MAP或血管活性药物)
        cardiovascular_score = 0
        
        # 检查是否使用血管活性药物
        if dopamine > 15 or epinephrine > 0.1 or norepinephrine > 0.1:
            cardiovascular_score = 4
            explanation_parts.append(f"Cardiovascular: High-dose vasopressors = {cardiovascular_score} points")
        elif dopamine > 5 or epinephrine <= 0.1 or norepinephrine <= 0.1:
            cardiovascular_score = 3
            explanation_parts.append(f"Cardiovascular: Medium-dose vasopressors = {cardiovascular_score} points")
        elif dopamine <= 5 or dobutamine > 0:
            cardiovascular_score = 2
            explanation_parts.append(f"Cardiovascular: Low-dose vasopressors = {cardiovascular_score} points")
        elif systolic_bp is not None and diastolic_bp is not None:
            # 计算平均动脉压
            map_value = round_number((systolic_bp + 2 * diastolic_bp) / 3, 1)
            if map_value < 70:
                cardiovascular_score = 1
                explanation_parts.append(f"Cardiovascular: MAP {map_value} mmHg < 70 = {cardiovascular_score} point")
            else:
                explanation_parts.append(f"Cardiovascular: MAP {map_value} mmHg ≥ 70 = 0 points")
        
        total_score += cardiovascular_score
        organ_scores["cardiovascular"] = cardiovascular_score
        
        # 5. 中枢神经系统 (GCS)
        if gcs == 15:
            cns_score = 0
        elif 13 <= gcs <= 14:
            cns_score = 1
        elif 10 <= gcs <= 12:
            cns_score = 2
        elif 6 <= gcs <= 9:
            cns_score = 3
        else:  # < 6
            cns_score = 4
        
        total_score += cns_score
        organ_scores["cns"] = cns_score
        explanation_parts.append(f"Central nervous system: GCS {gcs} = {cns_score} points")
        
        # 6. 肾脏系统 (肌酐或尿量)
        renal_score = 0
        
        if creatinine is not None:
            if creatinine < 1.2:
                renal_score = 0
            elif 1.2 <= creatinine < 2.0:
                renal_score = 1
            elif 2.0 <= creatinine < 3.5:
                renal_score = 2
            elif 3.5 <= creatinine < 5.0:
                renal_score = 3
            else:  # >= 5.0
                renal_score = 4
            explanation_parts.append(f"Renal: Creatinine {creatinine} mg/dL = {renal_score} points")
        elif urine_output is not None:
            if urine_output >= 500:
                renal_score = 0
            elif 200 <= urine_output < 500:
                renal_score = 3
            else:  # < 200
                renal_score = 4
            explanation_parts.append(f"Renal: Urine output {urine_output} mL/day = {renal_score} points")
        
        total_score += renal_score
        organ_scores["renal"] = renal_score
        
        # 生成解释
        explanation = "SOFA (Sequential Organ Failure Assessment) Score calculation:\n\n"
        explanation += "\n".join([f"• {part}" for part in explanation_parts])
        explanation += f"\n\nTotal SOFA Score: {total_score} points"
        
        # 添加死亡率预测
        if total_score < 2:
            mortality_risk = "<10%"
        elif total_score < 6:
            mortality_risk = "10-20%"
        elif total_score < 9:
            mortality_risk = "20-40%"
        elif total_score < 12:
            mortality_risk = "40-60%"
        elif total_score < 15:
            mortality_risk = "60-80%"
        else:
            mortality_risk = ">80%"
        
        explanation += f"\n\nICU Mortality Risk: {mortality_risk}"
        
        return CalculationResult(
            value=total_score,
            unit="points",
            explanation=explanation,
            metadata={
                "mortality_risk": mortality_risk,
                "organ_scores": organ_scores,
                "pao2_fio2_ratio": pao2_fio2_ratio,
                "respiratory_support": respiratory_support,
                "map_value": round_number((systolic_bp + 2 * diastolic_bp) / 3, 1) if systolic_bp and diastolic_bp else None
            }
        )
