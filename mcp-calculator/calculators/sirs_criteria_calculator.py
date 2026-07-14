"""
SIRS Criteria Calculator
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


@register_calculator("sirs_criteria")
class SIRSCriteriaCalculator(BaseCalculator):
    """SIRS全身炎症反应综合征标准计算器实现"""
    
    def get_info(self) -> CalculatorInfo:
        return CalculatorInfo(
            id=51,
            name="SIRS Criteria Calculator",
            category="critical_care",
            description="Assess Systemic Inflammatory Response Syndrome (SIRS) criteria",
            parameters=[
                Parameter(
                    name="temperature",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="°C",
                    min_value=30.0,
                    max_value=45.0,
                    description="Body temperature in Celsius"
                ),
                Parameter(
                    name="heart_rate",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="bpm",
                    min_value=30,
                    max_value=250,
                    description="Heart rate in beats per minute"
                ),
                Parameter(
                    name="wbc",
                    type=ParameterType.NUMERIC,
                    required=True,
                    unit="cells/mm³",
                    min_value=0,
                    max_value=100000,
                    description="White blood cell count per mm³"
                ),
                Parameter(
                    name="respiratory_rate",
                    type=ParameterType.NUMERIC,
                    required=False,
                    unit="breaths/min",
                    min_value=5,
                    max_value=60,
                    description="Respiratory rate in breaths per minute"
                ),
                Parameter(
                    name="paco2",
                    type=ParameterType.NUMERIC,
                    required=False,
                    unit="mmHg",
                    min_value=10,
                    max_value=80,
                    description="PaCO₂ partial pressure in mmHg"
                )
            ]
        )
    
    def _parse_parameter_with_unit(self, param_value: Any) -> tuple[float, str]:
        """Parse parameter that might come as [value, unit] tuple"""
        if isinstance(param_value, (list, tuple)) and len(param_value) == 2:
            return float(param_value[0]), str(param_value[1])
        elif isinstance(param_value, (int, float)):
            return float(param_value), ""
        else:
            return float(param_value), ""
    
    def _convert_wbc_to_cells_per_mm3(self, value: float, unit: str) -> float:
        """Convert WBC to cells/mm³ (medical-specific conversion)"""
        unit_lower = unit.lower()
        if "µl" in unit_lower or "μl" in unit_lower or "ul" in unit_lower:
            result = value  # µL is same as cells/mm³
        elif unit_lower == "l":
            # Interpret as K/L (thousands per liter), convert to cells/mm³
            result = value * 1000  # K/L to cells/mm³
        elif "m^3" in unit_lower:
            # Interpret as cells/mm³ (since medical context suggests this)
            result = value
        else:
            result = value  # Assume cells/mm³ if no unit specified
        
        return result
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> ValidationResult:
        """验证参数"""
        errors = []
        
        # 检查必需参数
        required_params = ["temperature", "heart_rate", "wbc"]
        for param in required_params:
            if param not in parameters:
                errors.append(f"Missing required parameter: {param}")
        
        if errors:
            return ValidationResult(is_valid=False, errors=errors)
        
        # 获取并转换参数值
        try:
            temp_value, temp_unit = self._parse_parameter_with_unit(parameters["temperature"])
            temperature = self.unit_converter.convert(temp_value, temp_unit, "celsius")
            
            heart_rate = float(parameters["heart_rate"][0] if isinstance(parameters["heart_rate"], (list, tuple)) else parameters["heart_rate"])
            
            wbc_value, wbc_unit = self._parse_parameter_with_unit(parameters["wbc"])
            wbc = self._convert_wbc_to_cells_per_mm3(wbc_value, wbc_unit)
            
            # 验证范围 (adjusted for converted values)
            if temperature < 25.0 or temperature > 50.0:  # More lenient temperature range
                errors.append("Temperature must be between 25.0 and 50.0 °C")
            
            if heart_rate < 30 or heart_rate > 250:
                errors.append("Heart rate must be between 30 and 250 bpm")
            
            if wbc < 0 or wbc > 100000:  # More lenient WBC range for converted values
                errors.append("WBC must be between 0 and 100000 cells/mm³")
            
            # 验证可选参数
            if "respiratory_rate" in parameters:
                resp_rate = float(parameters["respiratory_rate"][0] if isinstance(parameters["respiratory_rate"], (list, tuple)) else parameters["respiratory_rate"])
                if resp_rate < 5 or resp_rate > 60:
                    errors.append("Respiratory rate must be between 5 and 60 breaths/min")
            
            if "paco2" in parameters:
                paco2 = float(parameters["paco2"][0] if isinstance(parameters["paco2"], (list, tuple)) else parameters["paco2"])
                if paco2 < 10 or paco2 > 80:
                    errors.append("PaCO₂ must be between 10 and 80 mmHg")
        
        except (ValueError, TypeError, KeyError) as e:
            errors.append(f"Parameter parsing error: {str(e)}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )
    
    def calculate(self, parameters: Dict[str, Any]) -> CalculationResult:
        """执行计算"""
        # Parse and convert parameters
        temp_value, temp_unit = self._parse_parameter_with_unit(parameters["temperature"])
        temperature = self.unit_converter.convert(temp_value, temp_unit, "celsius")
        
        heart_rate = float(parameters["heart_rate"][0] if isinstance(parameters["heart_rate"], (list, tuple)) else parameters["heart_rate"])
        
        wbc_value, wbc_unit = self._parse_parameter_with_unit(parameters["wbc"])
        wbc = self._convert_wbc_to_cells_per_mm3(wbc_value, wbc_unit)
        
        # Optional parameters
        respiratory_rate = None
        if "respiratory_rate" in parameters:
            respiratory_rate = float(parameters["respiratory_rate"][0] if isinstance(parameters["respiratory_rate"], (list, tuple)) else parameters["respiratory_rate"])
        
        paco2 = None
        if "paco2" in parameters:
            paco2 = float(parameters["paco2"][0] if isinstance(parameters["paco2"], (list, tuple)) else parameters["paco2"])
        
        criteria_met = 0
        criteria_details = []
        
        # 1. 体温标准
        if temperature > 38 or temperature < 36:
            criteria_met += 1
            criteria_details.append(f"Temperature: {temperature}°C (>38°C or <36°C) - MET")
        else:
            criteria_details.append(f"Temperature: {temperature}°C (36-38°C) - NOT MET")
        
        # 2. 心率标准
        if heart_rate > 90:
            criteria_met += 1
            criteria_details.append(f"Heart rate: {heart_rate} bpm (>90) - MET")
        else:
            criteria_details.append(f"Heart rate: {heart_rate} bpm (≤90) - NOT MET")
        
        # 3. 白细胞计数标准
        if wbc > 12000 or wbc < 4000:
            criteria_met += 1
            criteria_details.append(f"WBC: {wbc} cells/mm³ (>12,000 or <4,000) - MET")
        else:
            criteria_details.append(f"WBC: {wbc} cells/mm³ (4,000-12,000) - NOT MET")
        
        # 4. 呼吸标准（呼吸频率或PaCO2）
        resp_met = False
        resp_details = []
        
        if respiratory_rate is not None:
            if respiratory_rate > 20:
                resp_met = True
                resp_details.append(f"Respiratory rate: {respiratory_rate} breaths/min (>20)")
            else:
                resp_details.append(f"Respiratory rate: {respiratory_rate} breaths/min (≤20)")
        
        if paco2 is not None:
            if paco2 < 32:
                resp_met = True
                resp_details.append(f"PaCO₂: {paco2} mmHg (<32)")
            else:
                resp_details.append(f"PaCO₂: {paco2} mmHg (≥32)")
        
        if resp_met:
            criteria_met += 1
            criteria_details.append(f"Respiratory: {' or '.join(resp_details)} - MET")
        else:
            if resp_details:
                criteria_details.append(f"Respiratory: {' and '.join(resp_details)} - NOT MET")
            else:
                criteria_details.append("Respiratory: No data provided - NOT MET")
        
        # 生成解释
        explanation = self._generate_explanation(criteria_met, criteria_details)
        
        return CalculationResult(
            value=criteria_met,
            unit="criteria",
            explanation=explanation,
            metadata={
                "temperature": temperature,
                "heart_rate": heart_rate,
                "wbc": wbc,
                "respiratory_rate": respiratory_rate,
                "paco2": paco2,
                "criteria_details": criteria_details
            }
        )
    
    def _generate_explanation(self, criteria_met: int, criteria_details: list) -> str:
        """生成计算解释"""
        explanation = """The rules for SIRS Criteria are listed below:

   1. Temperature >38°C (100.4°F) or <36°C (96.8°F): No = 0 points, Yes = +1 point
   2. Heart rate >90: No = 0 points, Yes = +1 point
   3. Respiratory rate >20 or PaCO₂ <32 mm Hg: No = 0 points, Yes = +1 point
   4. White blood cell count (WBC) >12,000/mm³, <4,000/mm³, or >10% bands: No = 0 points, Yes = +1 point

The total number of criteria met is taken by summing the score for each criteria.

"""
        
        explanation += "Assessment of each criterion:\n\n"
        
        for detail in criteria_details:
            explanation += f"• {detail}\n"
        
        explanation += f"\nHence, the number of SIRS criteria met by the patient is {criteria_met}.\n"
        
        if criteria_met >= 2:
            explanation += "\nWith ≥2 criteria met, the patient meets the definition for SIRS."
        else:
            explanation += "\nWith <2 criteria met, the patient does not meet the definition for SIRS."
        
        return explanation
