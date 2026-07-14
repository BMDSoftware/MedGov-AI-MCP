"""
Steroid Conversion Calculator
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


@register_calculator("steroid_conversion")
class SteroidConversionCalculator(BaseCalculator):
    """类固醇转换计算器实现"""
    
    def get_info(self) -> CalculatorInfo:
        steroid_choices = [
            "Betamethasone IV",
            "Cortisone PO", 
            "Dexamethasone IV",
            "Dexamethasone PO",
            "Hydrocortisone IV",
            "Hydrocortisone PO",
            "MethylPrednisoLONE IV",
            "MethylPrednisoLONE PO",
            "PrednisoLONE PO",
            "PredniSONE PO",
            "Triamcinolone IV"
        ]
        
        return CalculatorInfo(
            id=24,
            name="Steroid Conversion Calculator",
            category="pharmacology",
            description="Convert between equivalent doses of different corticosteroids",
            parameters=[
                Parameter(
                    name="input_steroid",
                    type=ParameterType.CHOICE,
                    required=True,
                    choices=steroid_choices,
                    description="Input steroid type and route"
                ),
                Parameter(
                    name="input_dose",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="mg",
                    min_value=0.001,
                    max_value=1000,
                    description="Input steroid dose in mg"
                ),
                Parameter(
                    name="target_steroid",
                    type=ParameterType.CHOICE,
                    required=True,
                    choices=steroid_choices,
                    description="Target steroid type and route"
                )
            ]
        )
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> ValidationResult:
        """验证输入参数"""
        errors = []
        
        # 获取参数值
        input_steroid = parameters.get("input_steroid")
        input_dose = parameters.get("input_dose")
        target_steroid = parameters.get("target_steroid")
        
        # 验证必需参数
        if input_steroid is None:
            errors.append("input_steroid is required")
        if input_dose is None:
            errors.append("input_dose is required")
        elif not isinstance(input_dose, (int, float)) or input_dose <= 0:
            errors.append("input_dose must be a positive number")
        if target_steroid is None:
            errors.append("target_steroid is required")
            
        return ValidationResult(is_valid=len(errors) == 0, errors=errors)
    
    def calculate(self, parameters: Dict[str, Any]) -> CalculationResult:
        """计算类固醇转换"""
        # 转换因子字典（相对于0.75mg基准）
        conversion_dict = {
            "Betamethasone IV": 1, 
            "Cortisone PO": 33.33, 
            "Dexamethasone IV": 1, 
            "Dexamethasone PO": 1,
            "Hydrocortisone IV": 26.67,
            "Hydrocortisone PO": 26.67,
            "MethylPrednisoLONE IV": 5.33,
            "MethylPrednisoLONE PO": 5.33,
            "PrednisoLONE PO": 6.67, 
            "PredniSONE PO": 6.67, 
            "Triamcinolone IV": 5.33
        }
        
        # 等效剂量字典（mg）
        equivalent_doses = {
            "Betamethasone IV": 0.75,
            "Cortisone PO": 25,
            "Dexamethasone IV": 0.75,
            "Dexamethasone PO": 0.75,
            "Hydrocortisone IV": 20,
            "Hydrocortisone PO": 20,
            "MethylPrednisoLONE IV": 4,
            "MethylPrednisoLONE PO": 4,
            "PrednisoLONE PO": 5,
            "PredniSONE PO": 5,
            "Triamcinolone IV": 4
        }
        
        # 获取参数值
        input_steroid = parameters["input_steroid"]
        input_dose = float(parameters["input_dose"])
        target_steroid = parameters["target_steroid"]
        
        # 计算转换
        from_multiplier = conversion_dict[input_steroid]
        to_multiplier = conversion_dict[target_steroid]
        
        conversion_factor = round_number(to_multiplier / from_multiplier)
        converted_amount = round_number(input_dose * conversion_factor)
        
        # 生成解释
        explanation = self._generate_explanation(
            input_steroid, input_dose, target_steroid, 
            conversion_factor, converted_amount, equivalent_doses
        )
        
        return CalculationResult(
            value=converted_amount,
            unit="mg",
            explanation=explanation,
            metadata={
                "input_steroid": input_steroid,
                "input_dose_mg": input_dose,
                "target_steroid": target_steroid,
                "conversion_factor": conversion_factor,
                "converted_dose_mg": converted_amount,
                "input_equivalent_dose": equivalent_doses[input_steroid],
                "target_equivalent_dose": equivalent_doses[target_steroid]
            }
        )
    
    def _generate_explanation(self, input_steroid: str, input_dose: float, target_steroid: str,
                            conversion_factor: float, converted_amount: float, equivalent_doses: Dict) -> str:
        """生成计算解释"""
        explanation = """Steroid Conversion Calculator

The following are equivalent doses for various corticosteroids:

1. Betamethasone: Route = IV, Equivalent Dose = 0.75 mg
2. Cortisone: Route = PO, Equivalent Dose = 25 mg
3. Dexamethasone (Decadron): Route = IV or PO, Equivalent Dose = 0.75 mg
4. Hydrocortisone: Route = IV or PO, Equivalent Dose = 20 mg
5. MethylPrednisoLONE: Route = IV or PO, Equivalent Dose = 4 mg
6. PrednisoLONE: Route = PO, Equivalent Dose = 5 mg
7. PredniSONE: Route = PO, Equivalent Dose = 5 mg
8. Triamcinolone: Route = IV, Equivalent Dose = 4 mg

"""
        
        explanation += f"Converting {input_dose} mg of {input_steroid} to {target_steroid}:\n\n"
        
        explanation += f"Input steroid equivalent dose: {equivalent_doses[input_steroid]} mg\n"
        explanation += f"Target steroid equivalent dose: {equivalent_doses[target_steroid]} mg\n"
        explanation += f"Conversion factor: {conversion_factor}\n\n"
        
        explanation += f"Calculation: {input_dose} mg × {conversion_factor} = {converted_amount} mg\n\n"
        
        explanation += f"Therefore, {input_dose} mg of {input_steroid} is equivalent to {converted_amount} mg of {target_steroid}."
        
        return explanation
