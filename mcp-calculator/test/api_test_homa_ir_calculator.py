import asyncio
import json
import sys
import os
from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVER_URL


async def test_homa_ir_calculator(client):
    """测试 HOMA-IR 计算器的各种功能"""

    def print_header():
        print("\n" + "=" * 60)
        print("HOMA-IR 计算器测试套件")
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
        homa_ir_value = data.get("value", "N/A")
        unit = data.get("unit", "")
        explanation = data.get("explanation", "")
        metadata = data.get("metadata", {})
        warnings = data.get("warnings", [])

        # 基本结果
        print(f"- HOMA-IR 值: {homa_ir_value} {unit}")

        # 原始输入值
        if metadata:
            insulin = metadata.get("insulin")
            glucose = metadata.get("glucose")
            clinical_note = metadata.get("clinical_note", "N/A")
            interpretation = metadata.get("interpretation", "")

            if insulin is not None:
                print(f"- 胰岛素: {insulin} µIU/mL")
            if glucose is not None:
                print(f"- 血糖: {glucose} mg/dL")
            if clinical_note:
                print(f"- 临床意义: {clinical_note}")
            if interpretation:
                print(f"- 解释: {interpretation}")

        # 警告信息
        if warnings:
            for warning in warnings:
                print(f"- ⚠️  警告: {warning}")

        # 详细解释（截取前几行显示）
        if explanation:
            lines = explanation.split('\n')
            print(f"- 计算过程: {lines[0] if lines else explanation}")

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
            print("\n✅ 所有测试都通过了！HOMA-IR 计算器工作正常。")
        else:
            print(f"\n❌ {failed} 个测试失败，请检查实现。")

        print("\n测试覆盖范围:")
        features = [
            "正常胰岛素敏感性测试",
            "早期胰岛素抵抗测试", 
            "显著胰岛素抵抗测试",
            "严重胰岛素抵抗测试",
            "参数验证",
            "边界值测试",
            "错误处理",
        ]
        for feature in features:
            print(f"  - {feature}")

    # Test statistics
    total_tests = 0
    passed_tests = 0

    # Test cases based on HOMA-IR clinical ranges
    test_cases = [
        {
            "name": "Normal insulin sensitivity",
            "params": {"insulin": 5, "glucose": 80},
            "expected_valid": True,
            "description": "正常胰岛素敏感性 (预期 HOMA-IR < 1.0)",
            "expected_homa_ir": (5 * 80) / 405,  # ≈ 0.99
        },
        {
            "name": "Early insulin resistance", 
            "params": {"insulin": 10, "glucose": 90},
            "expected_valid": True,
            "description": "早期胰岛素抵抗 (预期 HOMA-IR 1.0-2.5)",
            "expected_homa_ir": (10 * 90) / 405,  # ≈ 2.22
        },
        {
            "name": "Significant insulin resistance",
            "params": {"insulin": 15, "glucose": 120},
            "expected_valid": True,
            "description": "显著胰岛素抵抗 (预期 HOMA-IR 2.5-5.0)",
            "expected_homa_ir": (15 * 120) / 405,  # ≈ 4.44
        },
        {
            "name": "Severe insulin resistance",
            "params": {"insulin": 25, "glucose": 150},
            "expected_valid": True,
            "description": "严重胰岛素抵抗 (预期 HOMA-IR > 5.0)",
            "expected_homa_ir": (25 * 150) / 405,  # ≈ 9.26
        },
        {
            "name": "Minimum valid values",
            "params": {"insulin": 1, "glucose": 50},
            "expected_valid": True,
            "description": "最小有效值测试",
            "expected_homa_ir": (1 * 50) / 405,  # ≈ 0.12
        },
        {
            "name": "Maximum valid values",
            "params": {"insulin": 100, "glucose": 400},
            "expected_valid": True,
            "description": "最大有效值测试",
            "expected_homa_ir": (100 * 400) / 405,  # ≈ 98.77
        },
        {
            "name": "Invalid insulin (below minimum)",
            "params": {"insulin": 0.5, "glucose": 80},
            "expected_valid": False,
            "description": "胰岛素值低于最小值 (< 1)",
        },
        {
            "name": "Invalid insulin (above maximum)",
            "params": {"insulin": 150, "glucose": 80},
            "expected_valid": False,
            "description": "胰岛素值高于最大值 (> 100)",
        },
        {
            "name": "Invalid glucose (below minimum)",
            "params": {"insulin": 10, "glucose": 30},
            "expected_valid": False,
            "description": "血糖值低于最小值 (< 50)",
        },
        {
            "name": "Invalid glucose (above maximum)",
            "params": {"insulin": 10, "glucose": 500},
            "expected_valid": False,
            "description": "血糖值高于最大值 (> 400)",
        },
        {
            "name": "Missing insulin parameter",
            "params": {"glucose": 80},
            "expected_valid": False,
            "description": "缺少胰岛素参数",
        },
        {
            "name": "Missing glucose parameter",
            "params": {"insulin": 10},
            "expected_valid": False,
            "description": "缺少血糖参数",
        },
    ]

    print_header()

    # Execute test cases
    for i, test_case in enumerate(test_cases, 1):
        total_tests += 1
        test_passed = True

        print_test_case(i, test_case)

        # Calculation test
        try:
            calc_result = await client.call_tool(
                "calculate",
                {
                    "calculator_id": 31,  # HOMA-IR calculator ID
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
                    # 验证计算结果
                    actual_value = data.get("value")
                    if "expected_homa_ir" in test_case:
                        expected_value = round(test_case["expected_homa_ir"], 2)
                        if actual_value is not None:
                            if abs(float(actual_value) - expected_value) > 0.01:
                                print(f"- 错误: 预期值 {expected_value}, 实际值 {actual_value}")
                                test_passed = False
                            else:
                                print(f"- ✅ 计算值验证通过: {actual_value}")
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
        print("HOMA-IR 计算器 MCP 测试")
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
        print("HOMA-IR 计算器测试结果")
        print("=" * 60)
        print(f"总测试数: {total_tests}")
        print(f"通过数: {total_passed}")
        print(f"失败数: {total_failed}")
        print(f"成功率: {(total_passed/total_tests*100):.1f}%")

        if total_failed == 0:
            print("\n✅ HOMA-IR 计算器所有测试都通过了！")
        else:
            print(f"\n❌ {total_failed} 个测试失败，请检查 HOMA-IR 计算器实现。")

    print_header()

    try:
        async with Client(MCP_SERVER_URL) as client:
            print_connection_status(True)
            passed, failed = await test_homa_ir_calculator(client)
            print_overall_results(passed, failed)

    except Exception as e:
        print_connection_status(False, str(e))
        import traceback

        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("✅ HOMA-IR 计算器测试完成")


if __name__ == "__main__":
    asyncio.run(main())