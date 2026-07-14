import asyncio
import json
import sys
import os
from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVER_URL


async def test_meld_na_calculator(client):
    """测试 MELD Na 计算器的各种功能"""

    def print_header():
        print("\n" + "=" * 60)
        print("MELD Na 计算器测试套件")
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
        score = data.get("value", "N/A")
        explanation = data.get("explanation", "")
        metadata = data.get("metadata", {})

        # 基本结果
        print(f"- MELD Na 评分: {score}")

        # 显示调整后的数值
        if metadata:
            print(f"- 原始肌酐: {metadata.get('original_creatinine', 'N/A')} mg/dL")
            print(f"- 调整后肌酐: {metadata.get('adjusted_creatinine', 'N/A')} mg/dL")
            print(f"- 原始胆红素: {metadata.get('original_bilirubin', 'N/A')} mg/dL")
            print(f"- 调整后胆红素: {metadata.get('adjusted_bilirubin', 'N/A')} mg/dL")
            print(f"- 原始INR: {metadata.get('original_inr', 'N/A')}")
            print(f"- 调整后INR: {metadata.get('adjusted_inr', 'N/A')}")
            print(f"- 原始钠: {metadata.get('original_sodium', 'N/A')} mEq/L")
            print(f"- 调整后钠: {metadata.get('adjusted_sodium', 'N/A')} mEq/L")
            if metadata.get('dialysis_twice'):
                print(f"- 过去一周内透析≥2次: 是")
            if metadata.get('cvvhd'):
                print(f"- 过去24小时CVVHD: 是")
            print(f"- 严重程度: {metadata.get('severity', 'N/A')}")

        # 详细解释（显示前几行）
        if explanation:
            lines = explanation.strip().split('\n')[:5]
            print(f"- 解释: {lines[0]}")

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
            print("\n✅ 所有测试都通过了！MELD Na 计算器工作正常。")
        else:
            print(f"\n❌ {failed} 个测试失败，请检查实现。")

        print("\n测试覆盖范围:")
        features = [
            "标准参数计算",
            "参数范围限制",
            "透析状态处理",
            "参数验证",
            "边界值测试",
            "错误处理",
        ]
        for feature in features:
            print(f"  - {feature}")

    # Test statistics
    total_tests = 0
    passed_tests = 0

    # Test cases
    test_cases = [
        {
            "name": "Normal values",
            "params": {"creatinine": 1.2, "bilirubin": 1.5, "inr": 1.3, "sodium": 140},
            "expected_valid": True,
            "description": "正常数值计算",
        },
        {
            "name": "High MELD score values",
            "params": {"creatinine": 3.5, "bilirubin": 8.0, "inr": 2.5, "sodium": 125},
            "expected_valid": True,
            "description": "高MELD评分数值",
        },
        {
            "name": "Low values with adjustments",
            "params": {"creatinine": 0.5, "bilirubin": 0.3, "inr": 0.8, "sodium": 120},
            "expected_valid": True,
            "description": "低数值（需调整）",
        },
        {
            "name": "High sodium (capped)",
            "params": {"creatinine": 2.0, "bilirubin": 3.0, "inr": 1.8, "sodium": 145},
            "expected_valid": True,
            "description": "高钠数值（需限制）",
        },
        {
            "name": "With dialysis history",
            "params": {"creatinine": 2.0, "bilirubin": 2.0, "inr": 1.5, "sodium": 135, "dialysis_twice": True},
            "expected_valid": True,
            "description": "有透析史",
        },
        {
            "name": "With CVVHD",
            "params": {"creatinine": 1.5, "bilirubin": 4.0, "inr": 2.0, "sodium": 130, "cvvhd": True},
            "expected_valid": True,
            "description": "有CVVHD史",
        },
        {
            "name": "Very high creatinine",
            "params": {"creatinine": 8.0, "bilirubin": 5.0, "inr": 3.0, "sodium": 128},
            "expected_valid": True,
            "description": "极高肌酐（需限制到4.0）",
        },
        {
            "name": "Missing creatinine",
            "params": {"bilirubin": 2.0, "inr": 1.5, "sodium": 135},
            "expected_valid": False,
            "description": "缺少肌酐参数",
        },
        {
            "name": "Invalid negative creatinine",
            "params": {"creatinine": -1.0, "bilirubin": 2.0, "inr": 1.5, "sodium": 135},
            "expected_valid": False,
            "description": "无效负数肌酐",
        },
        {
            "name": "Invalid zero bilirubin",
            "params": {"creatinine": 1.5, "bilirubin": 0, "inr": 1.5, "sodium": 135},
            "expected_valid": False,
            "description": "无效零胆红素",
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
                    "calculator_id": 23,
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
                    print("- 错误: 预期失败但计算成功")
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
        print("MELD Na 计算器 MCP 测试")
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
        print("MELD Na 计算器测试结果")
        print("=" * 60)
        print(f"总测试数: {total_tests}")
        print(f"通过数: {total_passed}")
        print(f"失败数: {total_failed}")
        print(f"成功率: {(total_passed/total_tests*100):.1f}%")

        if total_failed == 0:
            print("\n✅ MELD Na 计算器所有测试都通过了！")
        else:
            print(f"\n❌ {total_failed} 个测试失败，请检查 MELD Na 计算器实现。")

    print_header()

    try:
        async with Client(MCP_SERVER_URL) as client:
            print_connection_status(True)
            passed, failed = await test_meld_na_calculator(client)
            print_overall_results(passed, failed)

    except Exception as e:
        print_connection_status(False, str(e))
        import traceback

        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("✅ MELD Na 计算器测试完成")


if __name__ == "__main__":
    asyncio.run(main())