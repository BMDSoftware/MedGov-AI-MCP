"""
工具类和辅助函数
"""

from typing import Dict, Any
from math import log10, floor


class UnitConverter:
    """单位转换器"""
    
    # 长度转换（转换为米）
    LENGTH_CONVERSIONS = {
        "m": 1.0,
        "cm": 0.01,
        "mm": 0.001,
        "in": 0.0254,
        "ft": 0.3048
    }
    
    # 重量转换（转换为千克）
    WEIGHT_CONVERSIONS = {
        "kg": 1.0,
        "g": 0.001,
        "lb": 0.453592,
        "lbs": 0.453592,
        "oz": 0.0283495
    }
    
    # 温度转换（特殊处理，不能用简单的倍数）
    TEMPERATURE_UNITS = {
        "celsius": "c",
        "degrees celsius": "c", 
        "c": "c",
        "°c": "c",
        "fahrenheit": "f",
        "degrees fahrenheit": "f",
        "f": "f",
        "°f": "f"
    }
    
    def convert(self, value: float, from_unit: str, to_unit: str) -> float:
        """通用单位转换"""
        
        # 温度转换（特殊处理）
        from_unit_lower = from_unit.lower()
        to_unit_lower = to_unit.lower()
        
        from_temp = None
        to_temp = None
        
        for unit_name, unit_code in self.TEMPERATURE_UNITS.items():
            if from_unit_lower == unit_name:
                from_temp = unit_code
                break
        
        for unit_name, unit_code in self.TEMPERATURE_UNITS.items():
            if to_unit_lower == unit_name:
                to_temp = unit_code
                break
        
        if from_temp or to_temp:
            # 温度转换
            if from_temp == "f":
                # 华氏度转摄氏度
                celsius_value = (value - 32) * 5/9
            else:
                # 默认为摄氏度
                celsius_value = value
            
            if to_temp == "f":
                # 摄氏度转华氏度
                return celsius_value * 9/5 + 32
            else:
                # 默认返回摄氏度
                return celsius_value
        
        # 长度转换
        if from_unit in self.LENGTH_CONVERSIONS and to_unit in self.LENGTH_CONVERSIONS:
            # 先转换为米，再转换为目标单位
            meters = value * self.LENGTH_CONVERSIONS[from_unit]
            return meters / self.LENGTH_CONVERSIONS[to_unit]
        
        # 重量转换
        if from_unit in self.WEIGHT_CONVERSIONS and to_unit in self.WEIGHT_CONVERSIONS:
            # 先转换为千克，再转换为目标单位
            kg = value * self.WEIGHT_CONVERSIONS[from_unit]
            return kg / self.WEIGHT_CONVERSIONS[to_unit]
        
        # 如果单位相同或无法转换，返回原值
        if from_unit == to_unit:
            return value
        
        raise ValueError(f"Cannot convert from {from_unit} to {to_unit}")


def round_number(num: float, precision: int = 3) -> float:
    """智能数字舍入"""
    if num == 0:
        return 0
    
    if abs(num) >= 0.001:
        # 对于较大的数字，保留指定的小数位数
        return round(num, precision)
    else:
        # 对于很小的数字，保留有效数字
        return round(num, -int(floor(log10(abs(num)))) + precision - 1)
