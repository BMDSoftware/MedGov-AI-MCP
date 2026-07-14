"""
Calcium Correction for Hypoalbuminemia Calculator
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
from medcalc.utils import round_number, UnitConverter


@register_calculator("calcium_correction")
class CalciumCorrectionCalculator(BaseCalculator):
    """低白蛋白血症的钙校正计算器实现"""
    
    def __init__(self):
        super().__init__()
        self.unit_converter = UnitConverter()
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=7,
            name="Calcium Correction for Hypoalbuminemia",
            category="laboratory",
            description="Correct serum calcium concentration for low albumin levels",
            parameters=[
                Parameter(
                    name="serum_calcium",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="mg/dL",
                    min_value=1.0,
                    max_value=20.0,
                    description="Serum calcium concentration in mg/dL"
                ),
                Parameter(
                    name="serum_albumin", 
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="g/dL",
                    min_value=0.5,
                    max_value=6.0,
                    description="Serum albumin concentration in g/dL"
                ),
                Parameter(
                    name="normal_albumin",
                    type=ParameterType.NUMERIC,
                    required=False,
                    unit="g/dL",
                    default=4.0,
                    min_value=3.5,
                    max_value=5.0,
                    description="Normal albumin level (default: 4.0 g/dL)"
                )
            ]
        )
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> ValidationResult:
        """验证参数"""
        errors = []
        
        # 解析和转换参数（支持原始数据格式中的"Calcium"和"Albumin"键名）
        try:
            serum_calcium_raw = parameters.get("serum_calcium") or parameters.get("Calcium")
            serum_albumin_raw = parameters.get("serum_albumin") or parameters.get("Albumin")
            normal_albumin_raw = parameters.get("normal_albumin", 4.0)
            
            if serum_calcium_raw is not None:
                serum_calcium = self._parse_and_convert_parameter(serum_calcium_raw, "mg/dL", "serum_calcium")
                if serum_calcium < 1.0 or serum_calcium > 20.0:
                    errors.append("Serum calcium must be between 1.0 and 20.0 mg/dL")
            else:
                errors.append("Missing required parameter: serum_calcium or Calcium")
                
            if serum_albumin_raw is not None:
                serum_albumin = self._parse_and_convert_parameter(serum_albumin_raw, "g/dL", "serum_albumin") 
                if serum_albumin < 0.3 or serum_albumin > 6.0:
                    errors.append("Serum albumin must be between 0.3 and 6.0 g/dL")
            else:
                errors.append("Missing required parameter: serum_albumin or Albumin")
                
            if normal_albumin_raw is not None:
                normal_albumin = self._parse_and_convert_parameter(normal_albumin_raw, "g/dL", "normal_albumin")
                if normal_albumin < 3.5 or normal_albumin > 5.0:
                    errors.append("Normal albumin must be between 3.5 and 5.0 g/dL")
                    
        except (ValueError, TypeError) as e:
            errors.append(f"Parameter parsing error: {e}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )
    
    def calculate(self, parameters: Dict[str, Any]) -> CalculationResult:
        """执行计算"""
        # 解析和转换参数（支持原始数据格式中的"Calcium"和"Albumin"键名）
        serum_calcium_raw = parameters.get("serum_calcium") or parameters.get("Calcium")
        serum_albumin_raw = parameters.get("serum_albumin") or parameters.get("Albumin") 
        normal_albumin_raw = parameters.get("normal_albumin", 4.0)
        
        # 转换为标准单位
        serum_calcium = self._parse_and_convert_parameter(serum_calcium_raw, "mg/dL")
        serum_albumin = self._parse_and_convert_parameter(serum_albumin_raw, "g/dL")
        normal_albumin = self._parse_and_convert_parameter(normal_albumin_raw, "g/dL")
        
        # 计算校正钙: 校正钙 = 0.8 × (正常白蛋白 - 患者白蛋白) + 血清钙
        corrected_calcium = round_number(0.8 * (normal_albumin - serum_albumin) + serum_calcium)
        
        # 生成解释
        explanation = self._generate_explanation(serum_calcium, serum_albumin, normal_albumin, corrected_calcium)
        
        return CalculationResult(
            value=corrected_calcium,
            unit="mg/dL",
            explanation=explanation,
            metadata={
                "serum_calcium": serum_calcium,
                "serum_albumin": serum_albumin,
                "normal_albumin": normal_albumin,
                "formula": "Corrected Calcium = 0.8 × (Normal Albumin - Patient Albumin) + Serum Calcium"
            }
        )
    
    def _generate_explanation(self, serum_calcium: float, serum_albumin: float, 
                            normal_albumin: float, corrected_calcium: float) -> str:
        """生成计算解释"""
        explanation = f"To compute the patient's corrected calcium level in mg/dL, the formula is "
        explanation += f"(0.8 * (Normal Albumin (in g/dL) - Patient's Albumin (in g/dL))) + Serum Calcium (in mg/dL).\n\n"
        
        explanation += f"The patient's normal albumin level is {normal_albumin} g/dL.\n"
        explanation += f"The patient's serum albumin is {serum_albumin} g/dL.\n"
        explanation += f"The patient's serum calcium is {serum_calcium} mg/dL.\n\n"
        
        explanation += f"Plugging these values into the formula, we get "
        explanation += f"(0.8 * ({normal_albumin} g/dL - {serum_albumin} g/dL)) + {serum_calcium} mg/dL = {corrected_calcium} mg/dL.\n\n"
        
        explanation += f"The patient's corrected calcium concentration is {corrected_calcium} mg/dL."
        
        return explanation
    
    def _parse_and_convert_parameter(self, param_value, target_unit: str, param_name: str = ""):
        """解析参数并转换单位（遵循原始计算引擎逻辑）
        
        参数格式支持：
        - 简单数值: 7.6
        - 列表格式: [7.6, "mg/dL"]
        """
        if isinstance(param_value, (int, float)):
            # 如果是简单数值，假设已经是目标单位
            return float(param_value)
        elif isinstance(param_value, (list, tuple)) and len(param_value) == 2:
            # 列表格式 [值, 单位]
            value, unit = param_value
            value = float(value)
            
            # 单位转换（遵循原始计算引擎的逻辑）
            if unit != target_unit:
                if target_unit == "mg/dL" and unit == "mmol/L":
                    # 钙单位转换：使用原始计算引擎的分步四舍五入逻辑
                    # 步骤1: mmol → mol (四舍五入到3位小数)
                    mol_value = round(value * 0.001, 3)
                    # 步骤2: mol → g (使用40.08分子量，四舍五入到3位小数)  
                    gram_value = round(mol_value * 40.08, 3)
                    # 步骤3: g → mg (四舍五入到1位小数)
                    mg_value = round(gram_value * 1000, 1)
                    # 步骤4: L → dL，最终结果
                    return mg_value / 10.0
                elif target_unit == "g/dL" and unit == "g/L":
                    # 白蛋白单位转换: g/L ÷ 10 = g/dL  
                    return value / 10.0
                else:
                    return value  # 无法转换时返回原值
            return value
        else:
            # 其他情况，尝试转换为float
            return float(param_value)
    

