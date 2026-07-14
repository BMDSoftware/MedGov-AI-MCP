"""
异常处理类
"""

from typing import Dict


class CalculatorError(Exception):
    """计算器基础异常"""
    def __init__(self, message: str, code: str = "CALC_ERROR", details: Dict = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


class ValidationError(CalculatorError):
    """参数验证异常"""
    def __init__(self, message: str, details: Dict = None):
        super().__init__(message, "VALIDATION_ERROR", details)


class CalculationError(CalculatorError):
    """计算执行异常"""
    def __init__(self, message: str, details: Dict = None):
        super().__init__(message, "CALCULATION_ERROR", details)


class NotFoundError(CalculatorError):
    """计算器未找到异常"""
    def __init__(self, message: str, details: Dict = None):
        super().__init__(message, "NOT_FOUND_ERROR", details)
