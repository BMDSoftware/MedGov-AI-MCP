"""
核心数据模型
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Union
from enum import Enum
from datetime import datetime


class ParameterType(Enum):
    NUMERIC = "numeric"
    TEXT = "text"
    CHOICE = "choice"
    BOOLEAN = "boolean"
    DATE = "date"


@dataclass
class Parameter:
    """参数定义"""
    name: str
    type: ParameterType
    required: bool = True
    default: Any = None
    unit: Optional[str] = None
    choices: Optional[List[str]] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    description: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "type": self.type.value,
            "required": self.required,
            "default": self.default,
            "unit": self.unit,
            "choices": self.choices,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "description": self.description
        }


@dataclass
class CalculatorInfo:
    """计算器信息"""
    id: str
    name: str
    category: str
    description: str
    parameters: List[Parameter]
    references: List[str] = field(default_factory=list)
    version: str = "1.0.0"
    author: str = ""
    tags: List[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class CalculationResult:
    """计算结果"""
    value: Any
    unit: str = ""
    explanation: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict:
        return {
            "value": self.value,
            "unit": self.unit,
            "explanation": self.explanation,
            "metadata": self.metadata,
            "warnings": self.warnings,
            "timestamp": self.timestamp
        }
