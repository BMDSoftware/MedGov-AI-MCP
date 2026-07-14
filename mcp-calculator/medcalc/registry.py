"""
计算器注册系统
"""

from typing import Dict, Type, List, Optional
from .base import BaseCalculator
from .exceptions import NotFoundError


# 全局计算器注册表
_calculator_registry: Dict[str, Type[BaseCalculator]] = {}


def register_calculator(calc_id: str):
    """计算器注册装饰器"""
    def decorator(cls: Type[BaseCalculator]):
        _calculator_registry[calc_id] = cls
        return cls
    return decorator


class CalculatorRegistry:
    """计算器注册表管理"""
    
    def __init__(self):
        self._instances: Dict[str, BaseCalculator] = {}
        self._load_calculators()
    
    def _load_calculators(self):
        """加载所有注册的计算器"""
        for calc_id, calc_class in _calculator_registry.items():
            self._instances[calc_id] = calc_class()
    
    def get_calculator(self, calc_id) -> BaseCalculator:
        """获取计算器实例，支持字符串和数字ID"""
        # 如果传入数字ID，需要通过计算器的get_info().id来匹配
        if isinstance(calc_id, int):
            for instance in self._instances.values():
                if instance.get_info().id == calc_id:
                    return instance
            raise NotFoundError(f"Calculator with ID '{calc_id}' not found")
        
        # 字符串ID的原有逻辑（向后兼容）
        if calc_id not in self._instances:
            raise NotFoundError(f"Calculator '{calc_id}' not found")
        return self._instances[calc_id]
    
    def list_calculators(self) -> List[str]:
        """列出所有可用的计算器ID"""
        return list(self._instances.keys())
    
    def has_calculator(self, calc_id: str) -> bool:
        """检查计算器是否存在"""
        return calc_id in self._instances
