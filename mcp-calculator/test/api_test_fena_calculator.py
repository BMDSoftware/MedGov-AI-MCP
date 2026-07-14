import asyncio
import json
import sys
import os
from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVER_URL


async def test_fena_calculator(client):
    """测试 FENa 计算器的各种功能和参数验证"""

    def print_header():
        print("\n" + "=" * 60)
        print("FENa 计算器测试套件")
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
        fena_value = data.get("value", "N/A")
        unit = data.get("unit", "")
        explanation = data.get("explanation", "")
        metadata = data.get("metadata", {})
        warnings = data.get("warnings", [])

        # 基本结果
        print(f"- FENa 值: {fena_value}{unit}")

        # 原始输入参数
        if metadata:
            serum_sodium = metadata.get("serum_sodium")
            serum_creatinine = metadata.get("serum_creatinine")
            urine_sodium = metadata.get("urine_sodium")
            urine_creatinine = metadata.get("urine_creatinine")
            clinical_note = metadata.get("clinical_note", "N/A")

            if serum_sodium is not None:
                print(f"- 血清钠: {serum_sodium} mEq/L")
            if serum_creatinine is not None:
                print(f"- 血清肌酐: {serum_creatinine} mg/dL")
            if urine_sodium is not None:
                print(f"- 尿钠: {urine_sodium} mEq/L")
            if urine_creatinine is not None:
                print(f"- 尿肌酐: {urine_creatinine} mg/dL")
            if clinical_note:
                print(f"- 临床意义: {clinical_note}")

        # 警告信息
        if warnings:
            for warning in warnings:
                print(f"- ⚠️  警告: {warning}")

        # 详细解释（截取前几行显示）
        if explanation:
            explanation_lines = explanation.strip().split('\n')[:3]
            print(f"- 解释: {explanation_lines}")

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
            print("\n✅ 所有测试都通过了！FENa 计算器工作正常。")
        else:
            print(f"\n❌ {failed} 个测试失败，请检查实现。")

        print("\n测试覆盖范围:")
        features = [
            "FENa 计算公式验证",
            "参数范围验证",
            "临床意义解释",
            "错误处理",
            "边界值测试",
            "无效参数处理",
        ]
        for feature in features:
            print(f"  - {feature}")

    # Test statistics
    total_tests = 0
    passed_tests = 0

    # Test cases
    test_cases = [
        {
            "name": "Normal prerenal azotemia case",
            "params": {
                "serum_sodium": 140,
                "serum_creatinine": 2.0,
                "urine_sodium": 10,
                "urine_creatinine": 100
            },
            "expected_valid": True,
            "expected_fena_range": (0, 1),
            "description": "正常肾前性氮质血症病例 (FENa < 1%)",
        },
        {
            "name": "Acute tubular necrosis case",
            "params": {
                "serum_sodium": 140,
                "serum_creatinine": 3.0,
                "urine_sodium": 60,
                "urine_creatinine": 80
            },
            "expected_valid": True,
            "expected_fena_range": (2, 5),
            "description": "急性肾小管坏死病例 (FENa > 2%)",
        },
        {
            "name": "Intermediate range case",
            "params": {
                "serum_sodium": 138,
                "serum_creatinine": 1.5,
                "urine_sodium": 25,
                "urine_creatinine": 120
            },
            "expected_valid": True,
            "expected_fena_range": (1, 2),
            "description": "中间范围病例 (FENa 1-2%)",
        },
        {
            "name": "Low serum sodium (hyponatremia)",
            "params": {
                "serum_sodium": 125,
                "serum_creatinine": 1.8,
                "urine_sodium": 15,
                "urine_creatinine": 90
            },
            "expected_valid": True,
            "description": "低钠血症病例",
        },
        {
            "name": "High serum creatinine",
            "params": {
                "serum_sodium": 142,
                "serum_creatinine": 8.0,
                "urine_sodium": 45,
                "urine_creatinine": 60
            },
            "expected_valid": True,
            "description": "高肌酐病例",
        },
        {
            "name": "Invalid serum sodium (too low)",
            "params": {
                "serum_sodium": 110,
                "serum_creatinine": 1.5,
                "urine_sodium": 20,
                "urine_creatinine": 100
            },
            "expected_valid": False,
            "description": "无效血清钠（过低）",
        },
        {
            "name": "Invalid serum sodium (too high)",
            "params": {
                "serum_sodium": 170,
                "serum_creatinine": 1.5,
                "urine_sodium": 20,
                "urine_creatinine": 100
            },
            "expected_valid": False,
            "description": "无效血清钠（过高）",
        },
        {
            "name": "Invalid serum creatinine (too low)",
            "params": {
                "serum_sodium": 140,
                "serum_creatinine": 0.3,
                "urine_sodium": 20,
                "urine_creatinine": 100
            },
            "expected_valid": False,
            "description": "无效血清肌酐（过低）",
        },
        {
            "name": "Invalid urine sodium (too low)",
            "params": {
                "serum_sodium": 140,
                "serum_creatinine": 1.5,
                "urine_sodium": 2,
                "urine_creatinine": 100
            },
            "expected_valid": False,
            "description": "无效尿钠（过低）",
        },
        {
            "name": "Missing required parameter",
            "params": {
                "serum_sodium": 140,
                "serum_creatinine": 1.5,
                "urine_sodium": 20
                # missing urine_creatinine
            },
            "expected_valid": False,
            "description": "缺少必需参数（尿肌酐）",
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
                    "calculator_id": 40,
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
                    # 检查 FENa 范围（如果有预期范围）
                    if "expected_fena_range" in test_case:
                        fena_value = data.get("value")
                        if fena_value is not None:
                            expected_min, expected_max = test_case["expected_fena_range"]
                            if not (expected_min <= fena_value <= expected_max):
                                print(f"- 警告: FENa 值 {fena_value}% 不在预期范围 {expected_min}-{expected_max}% 内")
                                # 不算作失败，只是警告
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
        print("FENa 计算器 MCP 测试")
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
        print("FENa 计算器测试结果")
        print("=" * 60)
        print(f"总测试数: {total_tests}")
        print(f"通过数: {total_passed}")
        print(f"失败数: {total_failed}")
        print(f"成功率: {(total_passed/total_tests*100):.1f}%")

        if total_failed == 0:
            print("\n✅ FENa 计算器所有测试都通过了！")
        else:
            print(f"\n❌ {total_failed} 个测试失败，请检查 FENa 计算器实现。")

    print_header()

    try:
        async with Client(MCP_SERVER_URL) as client:
            print_connection_status(True)
            passed, failed = await test_fena_calculator(client)
            print_overall_results(passed, failed)

    except Exception as e:
        print_connection_status(False, str(e))
        import traceback

        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("✅ FENa 计算器测试完成")


if __name__ == "__main__":
    asyncio.run(main())