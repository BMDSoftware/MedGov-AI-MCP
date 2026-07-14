"""
计算器基类
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from .models import CalculatorInfo, ValidationResult, CalculationResult, Parameter
from .exceptions import ValidationError


class BaseCalculator(ABC):
    """所有计算器的基类"""
    
    def __init__(self):
        self.unit_converter: Optional['UnitConverter'] = None
    
    @abstractmethod
    def get_info(self) -> CalculatorInfo:
        """获取计算器信息"""
        pass
    
    @abstractmethod
    def validate_parameters(self, params: Dict[str, Any]) -> ValidationResult:
        """验证参数"""
        pass
    
    @abstractmethod
    def calculate(self, params: Dict[str, Any]) -> CalculationResult:
        """执行计算"""
        pass
    
    def get_param_value(self, params: Dict, param_name: str, param_def: Parameter) -> Any:
        """获取参数值，处理默认值"""
        value = params.get(param_name, param_def.default)
        if value is None and param_def.required:
            raise ValidationError(f"Missing required parameter: {param_name}")
        return value
    
    def validate_numeric_range(self, value: float, param_def: Parameter) -> Optional[str]:
        """验证数值范围"""
        if param_def.min_value is not None and value < param_def.min_value:
            return f"Value {value} is below minimum {param_def.min_value}"
        if param_def.max_value is not None and value > param_def.max_value:
            return f"Value {value} is above maximum {param_def.max_value}"
        return None
