import asyncio
import json
import sys
import os
from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVER_URL


async def test_qtc_framingham_calculator(client):
    """测试 QTc Framingham 计算器的各种功能和单位转换"""

    def print_header():
        print("\n" + "=" * 60)
        print("QTc Framingham 计算器测试套件")
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

    def print_calculation_result(data, expected_range=None):
        """打印完整的计算结果"""
        qtc_value = data.get("value", "N/A")
        unit = data.get("unit", "")
        explanation = data.get("explanation", "")
        metadata = data.get("metadata", {})
        warnings = data.get("warnings", [])

        # 基本结果
        print(f"- QTc 值: {qtc_value} {unit}")

        # 计算输入和原始值
        if metadata:
            qt_interval = metadata.get("qt_interval")
            heart_rate = metadata.get("heart_rate")
            rr_interval = metadata.get("rr_interval")
            formula = metadata.get("formula")

            if qt_interval:
                print(f"- QT 间期: {qt_interval} msec")
            if heart_rate:
                print(f"- 心率: {heart_rate} bpm")
            if rr_interval:
                print(f"- RR 间期: {rr_interval:.3f} sec")
            if formula:
                print(f"- 公式: {formula}")

        # 验证计算结果是否在预期范围内
        if expected_range and qtc_value != "N/A":
            lower, upper, expected = expected_range
            try:
                qtc_float = float(qtc_value)
                if lower <= qtc_float <= upper:
                    print(f"- ✅ 计算结果在预期范围内 ({lower:.3f} - {upper:.3f})")
                else:
                    print(f"- ❌ 计算结果超出预期范围 ({lower:.3f} - {upper:.3f})")
                    print(f"- 预期值: {expected:.3f}, 实际值: {qtc_float:.3f}")
            except ValueError:
                print(f"- ❌ 无法解析计算结果: {qtc_value}")

        # 警告信息
        if warnings:
            for warning in warnings:
                print(f"- ⚠️  警告: {warning}")

        # 详细解释（截取前几行显示）
        if explanation:
            print(f"- 解释: {explanation[:100]}..." if len(explanation) > 100 else f"- 解释: {explanation}")

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
            print("\n✅ 所有测试都通过了！QTc Framingham 计算器工作正常。")
        else:
            print(f"\n❌ {failed} 个测试失败，请检查实现。")

        print("\n测试覆盖范围:")
        features = [
            "QT 间期和心率输入",
            "QTc Framingham 公式计算",
            "参数验证",
            "错误处理",
            "边界测试",
            "准确性验证"
        ]
        for feature in features:
            print(f"  - {feature}")

    # Test statistics
    total_tests = 0
    passed_tests = 0

    # Test cases - 来自训练数据集
    test_cases = [
        {
            "name": "Standard case 1",
            "params": {"qt_interval": 330, "heart_rate": 131},
            "expected_valid": True,
            "expected_range": (392.795, 434.141, 413.468),
            "description": "QT间期330ms, 心率131bpm",
        },
        {
            "name": "Standard case 2",
            "params": {"qt_interval": 330, "heart_rate": 134},
            "expected_valid": True,
            "expected_range": (394.258, 435.758, 415.008),
            "description": "QT间期330ms, 心率134bpm",
        },
        {
            "name": "High heart rate",
            "params": {"qt_interval": 330, "heart_rate": 178},
            "expected_valid": True,
            "expected_range": (410.497, 453.707, 432.102),
            "description": "高心率测试: QT间期330ms, 心率178bpm",
        },
        {
            "name": "Low heart rate",
            "params": {"qt_interval": 330, "heart_rate": 47},
            "expected_valid": True,
            "expected_range": (272.975, 301.709, 287.342),
            "description": "低心率测试: QT间期330ms, 心率47bpm",
        },
        {
            "name": "Normal heart rate",
            "params": {"qt_interval": 330, "heart_rate": 70},
            "expected_valid": True,
            "expected_range": (334.421, 369.623, 352.022),
            "description": "正常心率测试: QT间期330ms, 心率70bpm",
        },
        {
            "name": "Invalid QT interval (too low)",
            "params": {"qt_interval": 150, "heart_rate": 70},
            "expected_valid": False,
            "expected_range": None,
            "description": "无效QT间期（过低）",
        },
        {
            "name": "Invalid QT interval (too high)",
            "params": {"qt_interval": 900, "heart_rate": 70},
            "expected_valid": False,
            "expected_range": None,
            "description": "无效QT间期（过高）",
        },
        {
            "name": "Invalid heart rate (too low)",
            "params": {"qt_interval": 330, "heart_rate": 20},
            "expected_valid": False,
            "expected_range": None,
            "description": "无效心率（过低）",
        },
        {
            "name": "Invalid heart rate (too high)",
            "params": {"qt_interval": 330, "heart_rate": 300},
            "expected_valid": False,
            "expected_range": None,
            "description": "无效心率（过高）",
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
                    "calculator_id": 57,
                    "parameters": test_case["params"],
                },
            )

            # 使用 structured_content 或 data 属性获取实际数据
            calc_data = calc_result.structured_content or calc_result.data or {}

            if isinstance(calc_data, dict) and calc_data.get("success") and "result" in calc_data:
                # 成功计算
                data = calc_data["result"]
                print_calculation_result(data, test_case.get("expected_range"))

                # 检查是否符合预期
                if not test_case["expected_valid"]:
                    print("- 错误: 预期失败但计算成功")
                    test_passed = False

                # 验证计算结果准确性
                elif test_case.get("expected_range"):
                    lower, upper, expected = test_case["expected_range"]
                    try:
                        qtc_value = float(data.get("value", 0))
                        # 允许一定的计算误差（5%）
                        tolerance = abs(expected * 0.05)
                        if abs(qtc_value - expected) > tolerance:
                            print(f"- ❌ 计算结果与预期相差过大: 期望{expected:.3f}, 实际{qtc_value:.3f}")
                            test_passed = False
                    except (ValueError, TypeError):
                        print(f"- ❌ 无法验证计算结果")
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
        print("QTc Framingham 计算器 MCP 测试")
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
        print("QTc Framingham 计算器测试结果")
        print("=" * 60)
        print(f"总测试数: {total_tests}")
        print(f"通过数: {total_passed}")
        print(f"失败数: {total_failed}")
        print(f"成功率: {(total_passed/total_tests*100):.1f}%")

        if total_failed == 0:
            print("\n✅ QTc Framingham 计算器所有测试都通过了！")
        else:
            print(f"\n❌ {total_failed} 个测试失败，请检查 QTc Framingham 计算器实现。")

    print_header()

    try:
        async with Client(MCP_SERVER_URL) as client:
            print_connection_status(True)
            passed, failed = await test_qtc_framingham_calculator(client)
            print_overall_results(passed, failed)

    except Exception as e:
        print_connection_status(False, str(e))
        import traceback

        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("✅ QTc Framingham 计算器测试完成")


if __name__ == "__main__":
    asyncio.run(main())