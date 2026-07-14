"""
Free Water Deficit Calculator
自由水缺失计算器的 FastMCP 2.0 实现
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


@register_calculator("free_water_deficit")
class FreeWaterDeficitCalculator(BaseCalculator):
    """自由水缺失计算器实现"""
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=38,
            name="Free Water Deficit",
            category="laboratory",
            description="Calculate free water deficit for hypernatremia correction",
            parameters=[
                Parameter(
                    name="age",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="years",
                    min_value=0,
                    max_value=120,
                    description="Patient age in years"
                ),
                Parameter(
                    name="sex",
                    type=ParameterType.CHOICE,
                    required=True,
                    choices=["Male", "Female"],
                    description="Biological sex"
                ),
                Parameter(
                    name="weight", 
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="kg",
                    min_value=1,
                    max_value=300,
                    description="Body weight in kilograms"
                ),
                Parameter(
                    name="sodium",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="mmol/L",
                    min_value=100,
                    max_value=200,
                    description="Serum sodium level in mmol/L"
                )
            ]
        )
    
    def _parse_parameter(self, value: Any) -> tuple[float, str]:
        """解析参数，支持字符串格式如 '25 years' 或 '70kg'"""
        if isinstance(value, (int, float)):
            return float(value), ""
        
        if isinstance(value, str):
            import re
            # 匹配数字和单位，支持空格分隔
            match = re.match(r'^([0-9]*\.?[0-9]+)\s*([a-zA-Z/]*)$', value.strip())
            if match:
                num_str, unit = match.groups()
                return float(num_str), unit.lower()
        
        raise ValueError(f"Cannot parse parameter value: {value}")
    
    def _convert_age_to_years(self, age_value: float, age_unit: str) -> float:
        """转换年龄到年"""
        if age_unit in ["", "years", "year"]:
            return age_value
        elif age_unit in ["days", "day"]:
            return age_value / 365.25
        elif age_unit in ["months", "month"]:
            return age_value / 12.0
        else:
            raise ValueError(f"Unknown age unit: {age_unit}")
    
    def _convert_weight_to_kg(self, weight_value: float, weight_unit: str) -> float:
        """转换体重到千克"""
        if weight_unit in ["", "kg"]:
            return weight_value
        elif weight_unit in ["g", "grams"]:
            return weight_value / 1000.0
        elif weight_unit in ["lb", "lbs", "pounds"]:
            return weight_value * 0.453592
        else:
            raise ValueError(f"Unknown weight unit: {weight_unit}")
    
    def _convert_sodium_to_mmol(self, sodium_value: float, sodium_unit: str) -> float:
        """转换钠离子浓度到mmol/L"""
        if sodium_unit in ["", "mmol/l"]:
            return sodium_value
        elif sodium_unit in ["meq/l"]:
            return sodium_value  # mEq/L = mmol/L for sodium
        else:
            raise ValueError(f"Unknown sodium unit: {sodium_unit}")
    
    def validate_parameters(self, params: Dict[str, Any]) -> ValidationResult:
        """验证输入参数"""
        errors = []
        
        # 验证年龄
        if "age" not in params:
            errors.append("Age is required")
        else:
            try:
                age_value, age_unit = self._parse_parameter(params["age"])
                if age_value < 0 or age_value > 120:
                    errors.append("Age must be between 0 and 120")
            except ValueError:
                errors.append("Invalid age format")
            
        # 验证性别
        if "sex" not in params:
            errors.append("Sex is required")
        elif params["sex"] not in ["Male", "Female"]:
            errors.append("Sex must be 'Male' or 'Female'")
            
        # 验证体重
        if "weight" not in params:
            errors.append("Weight is required")
        else:
            try:
                weight_value, weight_unit = self._parse_parameter(params["weight"])
                # 转换到千克进行验证
                weight_kg = self._convert_weight_to_kg(weight_value, weight_unit)
                if weight_kg < 0.1 or weight_kg > 1000:
                    errors.append("Weight must be between 0.1 and 1000 kg")
            except ValueError:
                errors.append("Invalid weight format")
            
        # 验证钠离子
        if "sodium" not in params:
            errors.append("Sodium is required")
        else:
            try:
                sodium_value, sodium_unit = self._parse_parameter(params["sodium"])
                if sodium_value < 100 or sodium_value > 200:
                    errors.append("Sodium must be between 100 and 200")
            except ValueError:
                errors.append("Invalid sodium format")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )
    
    def calculate(self, params: Dict[str, Any]) -> CalculationResult:
        """计算自由水缺失"""
        # 验证参数
        validation = self.validate_parameters(params)
        if not validation.is_valid:
            raise ValueError(f"Invalid parameters: {', '.join(validation.errors)}")
        
        # 解析和转换参数值
        age_value, age_unit = self._parse_parameter(params["age"])
        age = self._convert_age_to_years(age_value, age_unit)
        
        sex = params["sex"]
        
        weight_value, weight_unit = self._parse_parameter(params["weight"])
        weight = self._convert_weight_to_kg(weight_value, weight_unit)
        
        sodium_value, sodium_unit = self._parse_parameter(params["sodium"])
        sodium = self._convert_sodium_to_mmol(sodium_value, sodium_unit)
        
        # 根据年龄和性别确定总体水分百分比
        if 0 <= age < 18:
            tbw = 0.6  # 儿童
            age_category = "child"
        elif 18 <= age < 65:
            if sex == "Male":
                tbw = 0.6  # 成年男性
                age_category = "adult male"
            else:
                tbw = 0.5  # 成年女性
                age_category = "adult female"
        else:  # age >= 65
            if sex == "Male":
                tbw = 0.5  # 老年男性
                age_category = "elderly male"
            else:
                tbw = 0.45  # 老年女性
                age_category = "elderly female"
        
        # 计算自由水缺失
        # 公式: Free Water Deficit = TBW × Weight × (Na/140 - 1)
        free_water_deficit = tbw * weight * (sodium / 140 - 1)
        free_water_deficit_rounded = round_number(free_water_deficit)
        
        # 构建解释说明
        explanation = (
            f"Free Water Deficit calculation:\n"
            f"Formula: Free Water Deficit = TBW × Weight × (Na/140 - 1)\n"
            f"Where:\n"
            f"- Age = {age} years\n"
            f"- Sex = {sex}\n"
            f"- Weight = {weight} kg\n"
            f"- Sodium = {sodium} mmol/L\n\n"
            f"Total Body Water (TBW) percentage based on age and sex:\n"
            f"Patient category: {age_category}\n"
            f"TBW = {tbw} (60% for children and adult males, 50% for adult females and elderly males, 45% for elderly females)\n\n"
            f"Calculation:\n"
            f"Free Water Deficit = {tbw} × {weight} × ({sodium}/140 - 1)\n"
            f"Free Water Deficit = {tbw} × {weight} × ({round_number(sodium/140)} - 1)\n"
            f"Free Water Deficit = {tbw} × {weight} × {round_number(sodium/140 - 1)}\n"
            f"Free Water Deficit = {free_water_deficit_rounded} L"
        )
        
        # 添加临床意义
        if free_water_deficit_rounded > 5:
            clinical_note = "Severe free water deficit - consider gradual correction over 48-72 hours"
        elif free_water_deficit_rounded > 2:
            clinical_note = "Moderate free water deficit - monitor closely during correction"
        else:
            clinical_note = "Mild free water deficit - can be corrected more rapidly"
        
        return CalculationResult(
            value=free_water_deficit_rounded,
            unit="L",
            explanation=explanation,
            metadata={
                "age": age,
                "sex": sex,
                "weight": weight,
                "sodium": sodium,
                "tbw_percentage": tbw,
                "age_category": age_category,
                "clinical_note": clinical_note
            }
        )
