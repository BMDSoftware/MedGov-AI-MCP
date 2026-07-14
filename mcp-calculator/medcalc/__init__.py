"""
Medical Calculator MCP Service - Core Module
"""

from .models import ParameterType, Parameter, CalculatorInfo, ValidationResult, CalculationResult

from .base import BaseCalculator
from .registry import register_calculator, CalculatorRegistry
from .service import CalculatorService
from .exceptions import CalculatorError, ValidationError, CalculationError, NotFoundError

# 导入所有计算器以执行装饰器注册
import calculators

__version__ = "3.0.0"
__all__ = [
    "ParameterType",
    "Parameter",
    "CalculatorInfo",
    "ValidationResult",
    "CalculationResult",
    "BaseCalculator",
    "register_calculator",
    "CalculatorRegistry",
    "CalculatorService",
    "CalculatorError",
    "ValidationError",
    "CalculationError",
    "NotFoundError",
]
