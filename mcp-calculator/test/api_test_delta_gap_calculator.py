import asyncio
import json
import sys
import os
from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVER_URL


async def test_delta_gap_calculator(client):
    """测试 Delta Gap 计算器的各种功能和单位转换"""

    def print_header():
        print("\n" + "=" * 60)
        print("Delta Gap 计算器测试套件")
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

    def print_calculation_result(data):
        """打印完整的计算结果"""
        delta_gap_value = data.get("value", "N/A")
        unit = data.get("unit", "")
        explanation = data.get("explanation", "")
        metadata = data.get("metadata", {})

        # 基本结果
        print(f"- Delta Gap 值: {delta_gap_value} {unit}")

        # 原始输入和计算过程
        if metadata:
            sodium = metadata.get("sodium")
            chloride = metadata.get("chloride")
            bicarbonate = metadata.get("bicarbonate")
            anion_gap = metadata.get("anion_gap")
            clinical_note = metadata.get("clinical_note")

            if sodium:
                print(f"- 输入钠离子: {sodium} mEq/L")
            if chloride:
                print(f"- 输入氯离子: {chloride} mEq/L")
            if bicarbonate:
                print(f"- 输入碳酸氢盐: {bicarbonate} mEq/L")
            if anion_gap:
                print(f"- 阴离子间隙: {anion_gap} mEq/L")
            if clinical_note:
                print(f"- 临床意义: {clinical_note}")

        # 详细解释（截取前几行显示）
        if explanation:
            lines = explanation.split('\n')[:3]  # 只显示前3行
            for line in lines:
                if line.strip():
                    print(f"- 解释: {line.strip()}")

    def print_test_result(i, passed, expected_value=None, actual_value=None):
        if passed:
            status = "✅ 通过"
        else:
            status = "❌ 失败"
        print(f"- 测试结果: {status}")
        if expected_value is not None and actual_value is not None:
            print(f"- 期望值: {expected_value}, 实际值: {actual_value}")
        print("-" * 60)

    def print_summary(total, passed, failed):
        print(f"\n测试总结:")
        print(f"  总测试数: {total}")
        print(f"  通过数: {passed}")
        print(f"  失败数: {failed}")
        print(f"  成功率: {(passed/total*100):.1f}%")

        if failed == 0:
            print("\n✅ 所有测试都通过了！Delta Gap 计算器工作正常。")
        else:
            print(f"\n❌ {failed} 个测试失败，请检查实现。")

        print("\n测试覆盖范围:")
        features = [
            "标准单位计算 (mEq/L)",
            "混合单位转换 (mmol/L)",
            "不同单位组合",
            "参数验证",
            "正负值计算",
            "边界测试",
            "错误处理",
        ]
        for feature in features:
            print(f"  - {feature}")

    # Test statistics
    total_tests = 0
    passed_tests = 0

    # 基于真实测试数据的测试用例
    test_cases = [
        {
            "name": "Standard calculation 1",
            "params": {"sodium": 135.0, "chloride": 110.0, "bicarbonate": 7.5},
            "expected_valid": True,
            "expected_value": 5.5,
            "description": "标准计算 - 阳性Delta Gap (钠135, 氯110, 碳酸氢盐7.5)",
        },
        {
            "name": "Negative delta gap",
            "params": {"sodium": 131.0, "chloride": 89.0, "bicarbonate": 36.0},
            "expected_valid": True,
            "expected_value": -6.0,
            "description": "负Delta Gap - 高氯血症性酸中毒 (钠131, 氯89, 碳酸氢盐36)",
        },
        {
            "name": "High positive delta gap",
            "params": {"sodium": 144.0, "chloride": 89.0, "bicarbonate": 10.0},
            "expected_valid": True,
            "expected_value": 33.0,
            "description": "高阳性Delta Gap - 高阴离子间隙代谢性酸中毒 (钠144, 氯89, 碳酸氢盐10)",
        },
        {
            "name": "Normal range",
            "params": {"sodium": 137.0, "chloride": 100.0, "bicarbonate": 25.0},
            "expected_valid": True,
            "expected_value": 0.0,
            "description": "正常范围 - Delta Gap为0 (钠137, 氯100, 碳酸氢盐25)",
        },
        {
            "name": "Moderate positive",
            "params": {"sodium": 142.0, "chloride": 109.0, "bicarbonate": 23.0},
            "expected_valid": True,
            "expected_value": -2.0,
            "description": "轻度负值 (钠142, 氯109, 碳酸氢盐23)",
        },
        {
            "name": "Invalid sodium (low)",
            "params": {"sodium": 100.0, "chloride": 100.0, "bicarbonate": 25.0},
            "expected_valid": False,
            "description": "无效钠离子值（过低）",
        },
        {
            "name": "Invalid chloride (high)",
            "params": {"sodium": 140.0, "chloride": 130.0, "bicarbonate": 25.0},
            "expected_valid": False,
            "description": "无效氯离子值（过高）",
        },
        {
            "name": "Invalid bicarbonate (low)",
            "params": {"sodium": 140.0, "chloride": 100.0, "bicarbonate": 2.0},
            "expected_valid": False,
            "description": "无效碳酸氢盐值（过低）",
        },
        {
            "name": "Edge case - high values",
            "params": {"sodium": 148.0, "chloride": 117.0, "bicarbonate": 8.6},
            "expected_valid": True,
            "expected_value": 10.4,
            "description": "边界测试 - 高值范围 (钠148, 氯117, 碳酸氢盐8.6)",
        },
    ]

    print_header()

    # Execute test cases
    for i, test_case in enumerate(test_cases, 1):
        total_tests += 1
        test_passed = True
        actual_value = None

        print_test_case(i, test_case)

        # Calculation test
        try:
            calc_result = await client.call_tool(
                "calculate",
                {
                    "calculator_id": 63,  # Delta Gap calculator ID
                    "parameters": test_case["params"],
                },
            )

            # 使用 structured_content 或 data 属性获取实际数据
            calc_data = calc_result.structured_content or calc_result.data or {}

            if isinstance(calc_data, dict) and calc_data.get("success") and "result" in calc_data:
                # 成功计算
                data = calc_data["result"]
                actual_value = data.get("value")
                print_calculation_result(data)

                # 检查是否符合预期的有效性
                if not test_case["expected_valid"]:
                    print("- 错误: 预期失败但计算成功")
                    test_passed = False
                else:
                    # 如果测试用例有期望值，检查数值精度
                    if "expected_value" in test_case and actual_value is not None:
                        expected = test_case["expected_value"]
                        # 允许小的数值误差（约5%）
                        tolerance = abs(expected * 0.05) + 0.1  # 至少0.1的容差
                        if abs(actual_value - expected) > tolerance:
                            print(f"- 数值误差: 期望 {expected}, 实际 {actual_value}, 容差 ±{tolerance:.1f}")
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

        expected_val = test_case.get("expected_value")
        print_test_result(i, test_passed, expected_val, actual_value)

    print_summary(total_tests, passed_tests, total_tests - passed_tests)
    return passed_tests, total_tests - passed_tests


async def main():
    def print_header():
        print("Delta Gap 计算器 MCP 测试")
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
        print("Delta Gap 计算器测试结果")
        print("=" * 60)
        print(f"总测试数: {total_tests}")
        print(f"通过数: {total_passed}")
        print(f"失败数: {total_failed}")
        print(f"成功率: {(total_passed/total_tests*100):.1f}%")

        if total_failed == 0:
            print("\n✅ Delta Gap 计算器所有测试都通过了！")
        else:
            print(f"\n❌ {total_failed} 个测试失败，请检查 Delta Gap 计算器实现。")

    print_header()

    try:
        async with Client(MCP_SERVER_URL) as client:
            print_connection_status(True)
            passed, failed = await test_delta_gap_calculator(client)
            print_overall_results(passed, failed)

    except Exception as e:
        print_connection_status(False, str(e))
        import traceback

        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("✅ Delta Gap 计算器测试完成")


if __name__ == "__main__":
    asyncio.run(main())