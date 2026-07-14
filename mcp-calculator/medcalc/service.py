"""
计算器服务主类
"""

from typing import Dict, Any, List, Optional
from .registry import CalculatorRegistry
from .utils import UnitConverter
from .models import CalculatorInfo, CalculationResult, ValidationResult
from .base import BaseCalculator
from .exceptions import ValidationError, NotFoundError


class CalculatorService:
    """计算器服务主类"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.registry = CalculatorRegistry()
        self.unit_converter = UnitConverter()
        self._inject_dependencies()

    def _inject_dependencies(self):
        """注入依赖到计算器"""
        for calc_id in self.registry._instances:
            calculator = self.registry._instances[calc_id]
            calculator.unit_converter = self.unit_converter

    def calculate(self, calc_id, params: Dict[str, Any]) -> CalculationResult:
        """执行计算"""
        # 获取计算器
        calculator = self.registry.get_calculator(calc_id)

        # 验证参数
        validation = calculator.validate_parameters(params)
        if not validation.is_valid:
            raise ValidationError(f"Invalid parameters: {', '.join(validation.errors)}")

        # 执行计算
        result = calculator.calculate(params)

        return result

    def get_calculator(self, calc_id) -> Optional[BaseCalculator]:
        """获取计算器实例"""
        try:
            return self.registry.get_calculator(calc_id)
        except NotFoundError:
            return None

    def list_calculators(self, category: Optional[str] = None) -> List[CalculatorInfo]:
        """列出可用的计算器"""
        result = []
        for calc_id, calculator in self.registry._instances.items():
            info = calculator.get_info()
            if category is None or info.category == category:
                result.append(info)
        return result

    def get_categories(self) -> List[str]:
        """获取所有计算器类别"""
        categories = set()
        for calculator in self.registry._instances.values():
            info = calculator.get_info()
            categories.add(info.category)
        return sorted(list(categories))
