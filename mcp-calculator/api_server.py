"""
Medical Calculator MCP Server
"""

import anyio
from datetime import datetime
from typing import Dict, Any, Optional
from fastmcp import FastMCP

from medcalc import CalculatorService


# 创建 FastMCP 服务器实例
mcp = FastMCP("Medical Calculator Service")

# 服务器配置
SERVER_CONFIG = {
    "name": "Medical Calculator Service",
    "version": "0.1.0",
    "description": "Medical calculator service based on FastMCP 2.0",
}

# 初始化计算器服务
calculator_service = CalculatorService(SERVER_CONFIG)


@mcp.tool
async def list_calculators(category: Optional[str] = None) -> Dict[str, Any]:
    """Get list of all available medical calculators

    Usage: Start here to browse available calculators. Use get_calculator_info()
    for detailed parameter information, then calculate() to perform calculations.

    Args:
        category: Optional category filter to return only calculators of specific category including
        "anthropometry", "cardiology", "cardiovascular", "critical_care", "hepatology", "infectious_disease",
        "laboratory", "nephrology", "obstetrics", "oncology", "pharmacology", "pulmonology"

    Returns:
        List of calculators with complete information
    """
    try:
        # 异步获取计算器列表
        calculators = await anyio.to_thread.run_sync(calculator_service.list_calculators)

        # 异步获取所有类别
        categories = await anyio.to_thread.run_sync(calculator_service.get_categories)

        # 如果指定了 category 参数，则过滤计算器
        if category:
            if category not in categories:
                raise ValueError(f"Category '{category}' not found, available categories: {categories}")
            calculators = [calc for calc in calculators if calc.category == category]
            categories = [cate for cate in categories if cate == category]

        result = {
            "calculators": [
                {
                    "id": calc.id,
                    "name": calc.name,
                    "category": calc.category,
                    "description": calc.description,
                    "parameter_names": [param.name for param in calc.parameters],
                }
                for calc in calculators
            ],
            "categories": categories,
            "count": len(calculators),
            "success": True,
        }

        return result
    except Exception as e:
        return {
            "error": str(e),
            "success": False,
        }


@mcp.tool
async def get_calculator_info(calculator_id: int) -> Dict[str, Any]:
    """Get detailed information about a specific medical calculator

    Usage: After selecting a calculator from list_calculators(), use this to get
    complete parameter details before calling calculate().

    Args:
        calculator_id: Calculator identifier (numeric ID)

    Returns:
        Calculator information
    """
    try:
        # 异步获取计算器实例
        calculator = await anyio.to_thread.run_sync(calculator_service.get_calculator, calculator_id)
        if not calculator:
            raise ValueError(f"Calculator {calculator_id} not found")

        # 异步获取计算器信息
        info = await anyio.to_thread.run_sync(calculator.get_info)

        result = {
            "id": info.id,
            "name": info.name,
            "category": info.category,
            "description": info.description,
            "version": info.version,
            "author": info.author,
            "tags": info.tags,
            "parameters": [param.to_dict() for param in info.parameters],
            "references": info.references,
            "success": True,
        }

        return result
    except Exception as e:
        return {
            "calculator_id": calculator_id,
            "error": str(e),
            "success": False,
        }


@mcp.tool
async def calculate(calculator_id: int, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Execute medical calculation

    Usage: After getting calculator details from get_calculator_info().
    Provide required parameters to perform the actual calculation.

    Args:
        calculator_id: Calculator identifier (numeric ID)
        parameters: Calculation parameters

    Returns:
        Calculation result and detailed information
    """

    try:
        # 异步获取计算器实例
        calculator = await anyio.to_thread.run_sync(calculator_service.get_calculator, calculator_id)
        if not calculator:
            raise ValueError(f"Calculator {calculator_id} not found")

        # 异步执行计算
        result = await anyio.to_thread.run_sync(calculator_service.calculate, calculator_id, parameters)

        # 格式化返回结果
        return {
            "calculator_id": calculator_id,
            "result": result.to_dict(),
            "timestamp": result.timestamp,
            "success": True,
        }

    except Exception as e:
        return {
            "calculator_id": calculator_id,
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
            "success": False,
        }


async def main():
    """启动异步HTTP服务器"""
    from config import SERVER_HOST, SERVER_PORT

    try:
        await mcp.run_async(transport="http", host=SERVER_HOST, port=SERVER_PORT)
    except Exception as e:
        print(f"❌ 服务器错误: {e}")


if __name__ == "__main__":
    anyio.run(main)
