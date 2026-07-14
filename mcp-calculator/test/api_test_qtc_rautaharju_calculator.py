import asyncio
import json
import sys
import os
from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVER_URL


async def test_qtc_rautaharju_calculator(client):
    """测试 QTc Rautaharju 计算器的各种功能"""

    def print_header():
        print("\n" + "=" * 60)
        print("QTc Rautaharju 计算器测试套件")
        print("=" * 60)

    def print_test_case(i, test_case):
        print(f"\n测试 {i:2d} | {test_case['name']}")
        print(f"- {test_case['description']}")
        print(f"- 输入参数: {test_case['params']}")

    def print_calculation_result(data):
        """打印完整的计算结果"""
        qtc_value = data.get("value", "N/A")
        unit = data.get("unit", "")
        explanation = data.get("explanation", "")
        metadata = data.get("metadata", {})
        warnings = data.get("warnings", [])

        # 基本结果
        print(f"- QTc 值: {qtc_value} {unit}")

        # 原始输入值
        if metadata:
            qt_interval = metadata.get("qt_interval")
            heart_rate = metadata.get("heart_rate")
            formula = metadata.get("formula", "N/A")

            if qt_interval:
                print(f"- QT间期: {qt_interval} msec")
            if heart_rate:
                print(f"- 心率: {heart_rate} bpm")
            if formula:
                print(f"- 公式: {formula}")

        # 警告信息
        if warnings:
            for warning in warnings:
                print(f"- ⚠️  警告: {warning}")

        # 详细解释（截取前几行显示）
        if explanation:
            print(f"- 解释: {explanation.strip()[:100]}...")

    def print_test_result(i, passed, expected_qtc=None, actual_qtc=None):
        if passed:
            status = "✅ 通过"
        else:
            status = "❌ 失败"
        print(f"- 测试结果: {status}")
        if expected_qtc and actual_qtc:
            print(f"- 期望值: {expected_qtc}, 实际值: {actual_qtc}")
        print("-" * 60)

    def print_summary(total, passed, failed):
        print(f"\n测试总结:")
        print(f"  总测试数: {total}")
        print(f"  通过数: {passed}")
        print(f"  失败数: {failed}")
        print(f"  成功率: {(passed/total*100):.1f}%")

        if failed == 0:
            print("\n✅ 所有测试都通过了！QTc Rautaharju 计算器工作正常。")
        else:
            print(f"\n❌ {failed} 个测试失败，请检查实现。")

        print("\n测试覆盖范围:")
        features = [
            "基础QTc计算",
            "参数验证",
            "边界值测试",
            "公式准确性",
            "错误处理",
        ]
        for feature in features:
            print(f"  - {feature}")

    # Test statistics
    total_tests = 0
    passed_tests = 0

    # Test cases from the data file - using various heart rates and QT intervals
    test_cases = [
        {
            "name": "Standard calculation (HR=57, QT=330)",
            "params": {"heart_rate": 57, "qt_interval": 330},
            "expected_qtc": 324.5,
            "expected_valid": True,
            "description": "标准计算 - 低心率",
            "tolerance": 0.1
        },
        {
            "name": "Standard calculation (HR=110, QT=330)",
            "params": {"heart_rate": 110, "qt_interval": 330},
            "expected_qtc": 421.667,
            "expected_valid": True,
            "description": "标准计算 - 正常心率",
            "tolerance": 0.1
        },
        {
            "name": "High heart rate (HR=173, QT=330)",
            "params": {"heart_rate": 173, "qt_interval": 330},
            "expected_qtc": 537.167,
            "expected_valid": True,
            "description": "高心率计算",
            "tolerance": 0.1
        },
        {
            "name": "Low heart rate (HR=71, QT=330)",
            "params": {"heart_rate": 71, "qt_interval": 330},
            "expected_qtc": 350.167,
            "expected_valid": True,
            "description": "低心率计算",
            "tolerance": 0.1
        },
        {
            "name": "Moderate heart rate (HR=92, QT=330)",
            "params": {"heart_rate": 92, "qt_interval": 330},
            "expected_qtc": 388.667,
            "expected_valid": True,
            "description": "中等心率计算",
            "tolerance": 0.1
        },
        {
            "name": "Invalid heart rate (too low)",
            "params": {"heart_rate": 25, "qt_interval": 330},
            "expected_valid": False,
            "description": "无效心率（过低）",
        },
        {
            "name": "Invalid heart rate (too high)",
            "params": {"heart_rate": 300, "qt_interval": 330},
            "expected_valid": False,
            "description": "无效心率（过高）",
        },
        {
            "name": "Invalid QT interval (too low)",
            "params": {"heart_rate": 80, "qt_interval": 150},
            "expected_valid": False,
            "description": "无效QT间期（过低）",
        },
        {
            "name": "Invalid QT interval (too high)",
            "params": {"heart_rate": 80, "qt_interval": 900},
            "expected_valid": False,
            "description": "无效QT间期（过高）",
        },
        {
            "name": "Boundary values (min HR, min QT)",
            "params": {"heart_rate": 30, "qt_interval": 200},
            "expected_qtc": 166.667,
            "expected_valid": True,
            "description": "边界值测试 - 最小值",
            "tolerance": 0.1
        },
        {
            "name": "Boundary values (max HR, max QT)",
            "params": {"heart_rate": 250, "qt_interval": 800},
            "expected_qtc": 1644.444,
            "expected_valid": True,
            "description": "边界值测试 - 最大值",
            "tolerance": 0.1
        },
    ]

    print_header()

    # Execute test cases
    for i, test_case in enumerate(test_cases, 1):
        total_tests += 1
        test_passed = True
        actual_qtc = None

        print_test_case(i, test_case)

        # Calculation test
        try:
            calc_result = await client.call_tool(
                "calculate",
                {
                    "calculator_id": 59,
                    "parameters": test_case["params"],
                },
            )

            # 使用 structured_content 或 data 属性获取实际数据
            calc_data = calc_result.structured_content or calc_result.data or {}

            if isinstance(calc_data, dict) and calc_data.get("success") and "result" in calc_data:
                # 成功计算
                data = calc_data["result"]
                print_calculation_result(data)
                
                actual_qtc = data.get("value")

                # 检查是否符合预期
                if not test_case["expected_valid"]:
                    print("- 错误: 预期失败但计算成功")
                    test_passed = False
                elif "expected_qtc" in test_case:
                    # 检查计算结果是否准确
                    expected = test_case["expected_qtc"]
                    tolerance = test_case.get("tolerance", 0.1)
                    if actual_qtc is None or abs(actual_qtc - expected) > tolerance:
                        print(f"- 错误: 计算结果不准确，期望: {expected}, 实际: {actual_qtc}")
                        test_passed = False
            else:
                # 计算失败（可能是参数验证失败）
                error_msg = calc_data.get("error", "未知错误") if isinstance(calc_data, dict) else str(calc_data)
                print(f"- 计算失败: {error_msg}")

                # 检查是否符合预期
                if test_case["expected_valid"]:
                    print("- 错误: 预期成功但计算失败")
                    test_passed = False

        except Exception as e:
            print(f"- 计算错误: {e}")
            # 检查是否符合预期
            if test_case["expected_valid"]:
                test_passed = False

        # Update statistics
        if test_passed:
            passed_tests += 1

        print_test_result(i, test_passed, test_case.get("expected_qtc"), actual_qtc)

    print_summary(total_tests, passed_tests, total_tests - passed_tests)
    return passed_tests, total_tests - passed_tests


async def main():
    def print_header():
        print("QTc Rautaharju 计算器 MCP 测试")
        print("=" * 60)

    def print_connection_status(success, error=None):
        if success:
            print("✅ 成功连接到 MCP 服务器")
        else:
            print(f"❌ 连接失败: {error}")

    def print_overall_results(total_passed, total_failed):
        total_tests = total_passed + total_failed
        if total_tests == 0:
            return

        print("\n" + "=" * 60)
        print("QTc Rautaharju 计算器测试结果")
        print("=" * 60)
        print(f"总测试数: {total_tests}")
        print(f"通过数: {total_passed}")
        print(f"失败数: {total_failed}")
        print(f"成功率: {(total_passed/total_tests*100):.1f}%")

        if total_failed == 0:
            print("\n✅ QTc Rautaharju 计算器所有测试都通过了！")
        else:
            print(f"\n❌ {total_failed} 个测试失败，请检查 QTc Rautaharju 计算器实现。")

    print_header()

    try:
        async with Client(MCP_SERVER_URL) as client:
            print_connection_status(True)
            passed, failed = await test_qtc_rautaharju_calculator(client)
            print_overall_results(passed, failed)

    except Exception as e:
        print_connection_status(False, str(e))
        import traceback

        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("✅ QTc Rautaharju 计算器测试完成")


if __name__ == "__main__":
    asyncio.run(main())