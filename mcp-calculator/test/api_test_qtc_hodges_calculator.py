import asyncio
import json
import sys
import os
from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVER_URL


async def test_qtc_hodges_calculator(client):
    """测试 QTc Hodges 计算器的各种功能"""

    def print_header():
        print("\n" + "=" * 60)
        print("QTc Hodges 计算器测试套件")
        print("=" * 60)

    def print_test_case(i, test_case):
        print(f"\n测试 {i:2d} | {test_case['name']}")
        print(f"- {test_case['description']}")
        print(f"- 输入参数: {test_case['params']}")
        if 'expected_range' in test_case:
            print(f"- 期望结果范围: {test_case['expected_range'][0]:.3f} - {test_case['expected_range'][1]:.3f}")

    def print_calculation_result(data):
        """打印完整的计算结果"""
        qtc_value = data.get("value", "N/A")
        unit = data.get("unit", "")
        explanation = data.get("explanation", "")
        metadata = data.get("metadata", {})
        warnings = data.get("warnings", [])

        # 基本结果
        print(f"- QTc 值: {qtc_value} {unit}")

        # 元数据信息
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
                print(f"- RR 间期: {rr_interval} sec")
            if formula:
                print(f"- 公式: {formula}")

        # 警告信息
        if warnings:
            for warning in warnings:
                print(f"- ⚠️  警告: {warning}")

        # 详细解释（截取前几行显示）
        if explanation:
            print(f"- 解释: {explanation[:200]}...")

    def print_test_result(i, passed, error_msg=None):
        if passed:
            status = "✅ 通过"
        else:
            status = "❌ 失败"
        print(f"- 测试结果: {status}")
        if error_msg:
            print(f"- 错误信息: {error_msg}")
        print("-" * 60)

    def print_summary(total, passed, failed):
        print(f"\n测试总结:")
        print(f"  总测试数: {total}")
        print(f"  通过数: {passed}")
        print(f"  失败数: {failed}")
        print(f"  成功率: {(passed/total*100):.1f}%")

        if failed == 0:
            print("\n✅ 所有测试都通过了！QTc Hodges 计算器工作正常。")
        else:
            print(f"\n❌ {failed} 个测试失败，请检查实现。")

        print("\n测试覆盖范围:")
        features = [
            "QT 间期参数验证",
            "心率参数验证",
            "Hodges 公式计算",
            "边界值测试",
            "错误处理",
        ]
        for feature in features:
            print(f"  - {feature}")

    # Test statistics
    total_tests = 0
    passed_tests = 0

    # Test cases based on medcalc_train_testcase_s20.jsonl data
    test_cases = [
        {
            "name": "Standard case 1",
            "params": {"qt_interval": 330, "heart_rate": 114},
            "expected_valid": True,
            "expected_range": [403.389, 445.851],  # Ground Truth: 424.62
            "description": "标准测试用例 (QT=330ms, HR=114bpm)",
        },
        {
            "name": "Standard case 2", 
            "params": {"qt_interval": 330, "heart_rate": 106},
            "expected_valid": True,
            "expected_range": [389.986, 431.038],  # Ground Truth: 410.512
            "description": "标准测试用例 (QT=330ms, HR=106bpm)",
        },
        {
            "name": "High heart rate",
            "params": {"qt_interval": 330, "heart_rate": 171},
            "expected_valid": True, 
            "expected_range": [497.938, 550.352],  # Ground Truth: 524.145
            "description": "高心率测试 (QT=330ms, HR=171bpm)",
        },
        {
            "name": "Low heart rate",
            "params": {"qt_interval": 330, "heart_rate": 55},
            "expected_valid": True,
            "expected_range": [305.18, 337.304],  # Ground Truth: 321.242
            "description": "低心率测试 (QT=330ms, HR=55bpm)",
        },
        {
            "name": "Normal heart rate",
            "params": {"qt_interval": 330, "heart_rate": 90},
            "expected_valid": True,
            "expected_range": [363.3, 401.542],  # Ground Truth: 382.421
            "description": "正常心率测试 (QT=330ms, HR=90bpm)",
        },
        {
            "name": "Invalid QT interval (too low)",
            "params": {"qt_interval": 150, "heart_rate": 90},
            "expected_valid": False,
            "description": "无效 QT 间期（过低）",
        },
        {
            "name": "Invalid QT interval (too high)",
            "params": {"qt_interval": 900, "heart_rate": 90},
            "expected_valid": False,
            "description": "无效 QT 间期（过高）",
        },
        {
            "name": "Invalid heart rate (too low)",
            "params": {"qt_interval": 330, "heart_rate": 25},
            "expected_valid": False,
            "description": "无效心率（过低）",
        },
        {
            "name": "Invalid heart rate (too high)",
            "params": {"qt_interval": 330, "heart_rate": 300},
            "expected_valid": False,
            "description": "无效心率（过高）",
        },
    ]

    print_header()

    # Execute test cases
    for i, test_case in enumerate(test_cases, 1):
        total_tests += 1
        test_passed = True
        error_msg = None

        print_test_case(i, test_case)

        # Calculation test
        try:
            calc_result = await client.call_tool(
                "calculate",
                {
                    "calculator_id": 58,  # QTc Hodges Calculator ID
                    "parameters": test_case["params"],
                },
            )

            # 使用 structured_content 或 data 属性获取实际数据
            calc_data = calc_result.structured_content or calc_result.data or {}

            if isinstance(calc_data, dict) and calc_data.get("success") and "result" in calc_data:
                # 成功计算
                data = calc_data["result"]
                print_calculation_result(data)

                # 检查是否符合预期
                if not test_case["expected_valid"]:
                    error_msg = "预期失败但计算成功"
                    test_passed = False
                elif 'expected_range' in test_case:
                    # 检查结果是否在期望范围内
                    qtc_value = data.get("value")
                    if qtc_value is not None:
                        lower_bound, upper_bound = test_case['expected_range']
                        if not (lower_bound <= qtc_value <= upper_bound):
                            error_msg = f"结果 {qtc_value} 不在期望范围 [{lower_bound:.3f}, {upper_bound:.3f}] 内"
                            test_passed = False
            else:
                # 计算失败（可能是参数验证失败）
                error_msg = calc_data.get("error", "未知错误") if isinstance(calc_data, dict) else str(calc_data)
                print(f"- 计算失败: {error_msg}")

                # 检查是否符合预期
                if test_case["expected_valid"]:
                    test_passed = False

        except Exception as e:
            error_msg = f"计算错误: {e}"
            print(f"- {error_msg}")
            # 检查是否符合预期
            if test_case["expected_valid"]:
                test_passed = False

        # Update statistics
        if test_passed:
            passed_tests += 1

        print_test_result(i, test_passed, error_msg)

    print_summary(total_tests, passed_tests, total_tests - passed_tests)
    return passed_tests, total_tests - passed_tests


async def main():
    def print_header():
        print("QTc Hodges 计算器 MCP 测试")
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
        print("QTc Hodges 计算器测试结果")
        print("=" * 60)
        print(f"总测试数: {total_tests}")
        print(f"通过数: {total_passed}")
        print(f"失败数: {total_failed}")
        print(f"成功率: {(total_passed/total_tests*100):.1f}%")

        if total_failed == 0:
            print("\n✅ QTc Hodges 计算器所有测试都通过了！")
        else:
            print(f"\n❌ {total_failed} 个测试失败，请检查 QTc Hodges 计算器实现。")

    print_header()

    try:
        async with Client(MCP_SERVER_URL) as client:
            print_connection_status(True)
            passed, failed = await test_qtc_hodges_calculator(client)
            print_overall_results(passed, failed)

    except Exception as e:
        print_connection_status(False, str(e))
        import traceback

        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("✅ QTc Hodges 计算器测试完成")


if __name__ == "__main__":
    asyncio.run(main())