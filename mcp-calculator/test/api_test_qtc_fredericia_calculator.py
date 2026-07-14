import asyncio
import json
import sys
import os
from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVER_URL


async def test_qtc_fredericia_calculator(client):
    """测试 QTc Fredericia 计算器的各种功能"""

    def print_header():
        print("\n" + "=" * 60)
        print("QTc Fredericia 计算器测试套件")
        print("=" * 60)

    def print_test_case(i, test_case):
        print(f"\n测试 {i:2d} | {test_case['name']}")
        print(f"- {test_case['description']}")
        print(f"- 输入参数: {test_case['params']}")

    def print_validation_result(expected, actual, errors=None, warnings=None):
        if expected == actual:
            status = "✅ 通过"
        else:
            status = "❌ 失败"
        expected_text = "有效" if expected else "无效"
        actual_text = "有效" if actual else "无效"
        print(f"- 验证结果: {status} (期望: {expected_text}, 实际: {actual_text})")
        if errors:
            print(f"- ⚠️  错误: {errors}")
        if warnings:
            print(f"- ⚠️  警告: {warnings}")

    def print_calculation_result(data, expected_value=None):
        """打印完整的计算结果"""
        qtc_value = data.get("value", "N/A")
        unit = data.get("unit", "")
        explanation = data.get("explanation", "")
        metadata = data.get("metadata", {})
        warnings = data.get("warnings", [])

        # 基本结果
        print(f"- QTc Fredericia 值: {qtc_value} {unit}")
        
        # 期望值比较
        if expected_value is not None:
            diff = abs(float(qtc_value) - expected_value) if qtc_value != "N/A" else 999
            tolerance = expected_value * 0.05  # 5% 容差
            if diff <= tolerance:
                print(f"- 期望值: {expected_value:.3f} (✅ 在容差范围内, 差异: {diff:.3f})")
            else:
                print(f"- 期望值: {expected_value:.3f} (❌ 超出容差范围, 差异: {diff:.3f})")

        # 原始输入和转换后的值
        if metadata:
            qt_interval = metadata.get("qt_interval")
            heart_rate = metadata.get("heart_rate")
            rr_interval = metadata.get("rr_interval")
            interpretation = metadata.get("interpretation")
            formula = metadata.get("formula")

            if qt_interval:
                print(f"- QT间期: {qt_interval} msec")
            if heart_rate:
                print(f"- 心率: {heart_rate} bpm")
            if rr_interval:
                print(f"- RR间期: {rr_interval} 秒")
            if interpretation:
                print(f"- 解释: {interpretation}")
            if formula:
                print(f"- 公式: {formula}")

        # 警告信息
        if warnings:
            for warning in warnings:
                print(f"- ⚠️  警告: {warning}")

        # 详细解释（截取前几行显示）
        if explanation:
            lines = explanation.strip().split('\n')[:3]  # 只显示前3行
            print(f"- 计算过程: {' / '.join(lines)}")

    def print_test_result(i, passed):
        if passed:
            status = "✅ 通过"
        else:
            status = "❌ 失败"
        print(f"- 测试结果: {status}")
        print("-" * 60)

    def print_summary(total, passed, failed):
        print(f"\n测试总结:")
        print(f"  总测试数: {total}")
        print(f"  通过数: {passed}")
        print(f"  失败数: {failed}")
        print(f"  成功率: {(passed/total*100):.1f}%")

        if failed == 0:
            print("\n✅ 所有测试都通过了！QTc Fredericia 计算器工作正常。")
        else:
            print(f"\n❌ {failed} 个测试失败，请检查实现。")

        print("\n测试覆盖范围:")
        features = [
            "QTc Fredericia 公式计算",
            "不同心率测试",
            "参数验证",
            "QTc 分类",
            "错误处理",
            "边界测试",
        ]
        for feature in features:
            print(f"  - {feature}")

    # Test statistics
    total_tests = 0
    passed_tests = 0

    # Test cases based on JSONL data
    test_cases = [
        {
            "name": "Normal heart rate (70 bpm)",
            "params": {"heart_rate": 70, "qt_interval": 330},
            "expected_valid": True,
            "expected_value": 347.419,
            "description": "正常心率下的QTc Fredericia计算",
        },
        {
            "name": "High heart rate (168 bpm)",
            "params": {"heart_rate": 168, "qt_interval": 330},
            "expected_valid": True,
            "expected_value": 465.184,
            "description": "高心率下的QTc Fredericia计算",
        },
        {
            "name": "Low heart rate (59 bpm)",
            "params": {"heart_rate": 59, "qt_interval": 330},
            "expected_valid": True,
            "expected_value": 328.151,
            "description": "低心率下的QTc Fredericia计算",
        },
        {
            "name": "Very high heart rate (180 bpm)",
            "params": {"heart_rate": 180, "qt_interval": 330},
            "expected_valid": True,
            "expected_value": 476.101,
            "description": "极高心率下的QTc Fredericia计算",
        },
        {
            "name": "Very low heart rate (47 bpm)",
            "params": {"heart_rate": 47, "qt_interval": 330},
            "expected_valid": True,
            "expected_value": 304.170,
            "description": "极低心率下的QTc Fredericia计算",
        },
        {
            "name": "Invalid heart rate (negative)",
            "params": {"heart_rate": -10, "qt_interval": 330},
            "expected_valid": False,
            "description": "无效心率（负数）",
        },
        {
            "name": "Invalid QT interval (zero)",
            "params": {"heart_rate": 70, "qt_interval": 0},
            "expected_valid": False,
            "description": "无效QT间期（零）",
        },
        {
            "name": "Heart rate too high",
            "params": {"heart_rate": 300, "qt_interval": 330},
            "expected_valid": False,
            "description": "心率过高（超出范围）",
        },
        {
            "name": "Heart rate too low",
            "params": {"heart_rate": 20, "qt_interval": 330},
            "expected_valid": False,
            "description": "心率过低（低于范围）",
        },
        {
            "name": "QT interval too high",
            "params": {"heart_rate": 70, "qt_interval": 900},
            "expected_valid": False,
            "description": "QT间期过高（超出范围）",
        },
    ]

    print_header()

    # Execute test cases
    for i, test_case in enumerate(test_cases, 1):
        total_tests += 1
        test_passed = True

        print_test_case(i, test_case)

        # Calculation test (validation is included in calculate)
        try:
            calc_result = await client.call_tool(
                "calculate",
                {
                    "calculator_id": 56,  # QTc Fredericia calculator ID
                    "parameters": test_case["params"],
                },
            )

            # 使用 structured_content 或 data 属性获取实际数据
            calc_data = calc_result.structured_content or calc_result.data or {}

            if isinstance(calc_data, dict) and calc_data.get("success") and "result" in calc_data:
                # 成功计算
                data = calc_data["result"]
                expected_value = test_case.get("expected_value")
                print_calculation_result(data, expected_value)

                # 检查是否符合预期
                if not test_case["expected_valid"]:
                    print("- 错误: 预期失败但计算成功")
                    test_passed = False
                elif expected_value is not None:
                    # 检查计算结果是否在预期范围内（5% 容差）
                    actual_value = data.get("value")
                    if actual_value != "N/A":
                        diff = abs(float(actual_value) - expected_value)
                        tolerance = expected_value * 0.05
                        if diff > tolerance:
                            print(f"- 错误: 计算结果超出预期范围")
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

        print_test_result(i, test_passed)

    print_summary(total_tests, passed_tests, total_tests - passed_tests)
    return passed_tests, total_tests - passed_tests


async def main():
    def print_header():
        print("QTc Fredericia 计算器 MCP 测试")
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
        print("QTc Fredericia 计算器测试结果")
        print("=" * 60)
        print(f"总测试数: {total_tests}")
        print(f"通过数: {total_passed}")
        print(f"失败数: {total_failed}")
        print(f"成功率: {(total_passed/total_tests*100):.1f}%")

        if total_failed == 0:
            print("\n✅ QTc Fredericia 计算器所有测试都通过了！")
        else:
            print(f"\n❌ {total_failed} 个测试失败，请检查 QTc Fredericia 计算器实现。")

    print_header()

    try:
        async with Client(MCP_SERVER_URL) as client:
            print_connection_status(True)
            passed, failed = await test_qtc_fredericia_calculator(client)
            print_overall_results(passed, failed)

    except Exception as e:
        print_connection_status(False, str(e))
        import traceback

        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("✅ QTc Fredericia 计算器测试完成")


if __name__ == "__main__":
    asyncio.run(main())