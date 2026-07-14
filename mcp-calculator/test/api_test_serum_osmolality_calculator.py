import asyncio
import json
import sys
import os
from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVER_URL


async def test_serum_osmolality_calculator(client):
    """测试血清渗透压计算器的各种功能"""

    def print_header():
        print("\n" + "=" * 60)
        print("血清渗透压计算器测试套件")
        print("=" * 60)

    def print_test_case(i, test_case):
        print(f"\n测试 {i:2d} | {test_case['name']}")
        print(f"- {test_case['description']}")
        print(f"- 输入参数: {test_case['params']}")

    def print_calculation_result(data, expected=None):
        """打印完整的计算结果"""
        osmolality_value = data.get("value", "N/A")
        unit = data.get("unit", "")
        explanation = data.get("explanation", "")
        metadata = data.get("metadata", {})
        
        # 基本结果
        print(f"- 计算结果: {osmolality_value} {unit}")
        if expected is not None:
            print(f"- 期望值: {expected}")
            if osmolality_value != "N/A":
                diff = abs(float(osmolality_value) - float(expected))
                print(f"- 误差: {diff:.3f}")
        
        # 元数据
        if metadata:
            sodium = metadata.get("sodium")
            bun = metadata.get("bun") 
            glucose = metadata.get("glucose")
            clinical_note = metadata.get("clinical_note", "N/A")
            
            if sodium:
                print(f"- 钠离子: {sodium} mmol/L")
            if bun:
                print(f"- BUN: {bun} mg/dL")
            if glucose:
                print(f"- 葡萄糖: {glucose} mg/dL")
            if clinical_note:
                print(f"- 临床意义: {clinical_note}")

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
            print("\n✅ 所有测试都通过了！血清渗透压计算器工作正常。")
        else:
            print(f"\n❌ {failed} 个测试失败，请检查实现。")

    # Test statistics
    total_tests = 0
    passed_tests = 0

    # Test cases from the data file
    test_cases = [
        {
            "name": "Standard case 1",
            "params": {"sodium": "137", "bun": "16", "glucose": "140"},
            "expected": "287.492",
            "description": "Na=137 mEq/L, BUN=16 mg/dL, Glucose=140 mg/dL",
        },
        {
            "name": "Standard case 2", 
            "params": {"sodium": "140", "bun": "6", "glucose": "158"},
            "expected": "290.921",
            "description": "Na=140 mmol/L, BUN=6 mg/dL, Glucose=158 mg/dL",
        },
        {
            "name": "Standard case 3",
            "params": {"sodium": "139", "bun": "20", "glucose": "99"},
            "expected": "290.643", 
            "description": "Na=139 mEq/L, BUN=20 mg/dL, Glucose=99 mg/dL",
        },
        {
            "name": "High BUN case",
            "params": {"sodium": "140", "bun": "30", "glucose": "96"},
            "expected": "296.048",
            "description": "Na=140 mEq/L, BUN=30 mg/dL, Glucose=96 mg/dL",
        },
        {
            "name": "High glucose case",
            "params": {"sodium": "139", "bun": "11", "glucose": "141"},
            "expected": "289.762",
            "description": "Na=139 mmol/L, BUN=11 mg/dL, Glucose=141 mg/dL",
        },
        {
            "name": "High sodium case",
            "params": {"sodium": "145", "bun": "33", "glucose": "155"},
            "expected": "310.397",
            "description": "Na=145 mEq/L, BUN=33 mg/dL, Glucose=155 mg/dL",
        },
        {
            "name": "Low sodium case",
            "params": {"sodium": "131", "bun": "21", "glucose": "110"},
            "expected": "275.611",
            "description": "Na=131 mEq/L, BUN=21 mg/dL, Glucose=110 mg/dL",
        },
        {
            "name": "Very high BUN case", 
            "params": {"sodium": "142", "bun": "121", "glucose": "170"},
            "expected": "336.659",
            "description": "Na=142 mEq/L, BUN=121 mg/dL, Glucose=170 mg/dL",
        },
        {
            "name": "High glucose case 2",
            "params": {"sodium": "142", "bun": "24", "glucose": "292"},
            "expected": "308.794",
            "description": "Na=142 mEq/L, BUN=24 mg/dL, Glucose=292 mg/dL",
        },
        {
            "name": "High BUN case 2",
            "params": {"sodium": "141", "bun": "56.3", "glucose": "137"},
            "expected": "309.718",
            "description": "Na=141 mmol/L, BUN=56.3 mg/dL, Glucose=137 mg/dL",
        },
        {
            "name": "Standard case 4",
            "params": {"sodium": "140", "bun": "34", "glucose": "86"},
            "expected": "296.921",
            "description": "Na=140 mEq/L, BUN=34 mg/dL, Glucose=86 mg/dL",
        },
        {
            "name": "Very high BUN case 2",
            "params": {"sodium": "138", "bun": "70", "glucose": "87"},
            "expected": "305.833",
            "description": "Na=138 mmol/L, BUN=70 mg/dL, Glucose=87 mg/dL",
        },
        {
            "name": "Low sodium case 2",
            "params": {"sodium": "131", "bun": "42", "glucose": "90"},
            "expected": "282.0",
            "description": "Na=131 mEq/L, BUN=42 mg/dL, Glucose=90 mg/dL",
        },
        {
            "name": "Mixed case 1",
            "params": {"sodium": "132", "bun": "34", "glucose": "168"},
            "expected": "285.476",
            "description": "Na=132 mmol/L, BUN=34 mg/dL, Glucose=168 mg/dL",
        },
        {
            "name": "Mixed case 2",
            "params": {"sodium": "134", "bun": "48.7", "glucose": "282"},
            "expected": "301.06",
            "description": "Na=134 mmol/L, BUN=48.7 mg/dL, Glucose=282 mg/dL",
        },
        {
            "name": "High sodium case 2",
            "params": {"sodium": "143", "bun": "15", "glucose": "144"},
            "expected": "299.357",
            "description": "Na=143 mEq/L, BUN=15 mg/dL, Glucose=144 mg/dL",
        },
        {
            "name": "Standard case 5",
            "params": {"sodium": "136", "bun": "14", "glucose": "82"},
            "expected": "281.556",
            "description": "Na=136 mmol/L, BUN=14 mg/dL, Glucose=82 mg/dL",
        },
        # 添加边界测试用例
        {
            "name": "Invalid - negative sodium",
            "params": {"sodium": "-10", "bun": "20", "glucose": "100"},
            "expected_valid": False,
            "description": "无效钠离子值（负数）",
        },
        {
            "name": "Invalid - zero BUN",
            "params": {"sodium": "140", "bun": "0", "glucose": "100"},
            "expected_valid": False,
            "description": "无效BUN值（零）",
        },
        {
            "name": "Invalid - negative glucose",
            "params": {"sodium": "140", "bun": "20", "glucose": "-50"},
            "expected_valid": False,
            "description": "无效葡萄糖值（负数）",
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
                    "calculator_id": 30,
                    "parameters": test_case["params"],
                },
            )

            # 使用 structured_content 或 data 属性获取实际数据
            calc_data = calc_result.structured_content or calc_result.data or {}

            if isinstance(calc_data, dict) and calc_data.get("success") and "result" in calc_data:
                # 成功计算
                data = calc_data["result"]
                expected = test_case.get("expected")
                print_calculation_result(data, expected)

                # 检查结果准确性
                if expected and "value" in data:
                    calculated_value = float(data["value"])
                    expected_value = float(expected)
                    tolerance = 0.1  # 允许0.1的误差
                    if abs(calculated_value - expected_value) > tolerance:
                        print(f"- 错误: 计算结果与期望值差异过大 (tolerance: {tolerance})")
                        test_passed = False

                # 检查是否符合预期
                if test_case.get("expected_valid") == False:
                    print("- 错误: 预期失败但计算成功")
                    test_passed = False
            else:
                # 计算失败（可能是参数验证失败）
                error_msg = calc_data.get("error", "未知错误") if isinstance(calc_data, dict) else str(calc_data)
                print(f"- 计算失败: {error_msg}")

                # 检查是否符合预期
                if test_case.get("expected_valid", True):
                    print("- 错误: 预期成功但计算失败")
                    test_passed = False

        except Exception as e:
            print(f"- 计算错误: {e}")
            # 检查是否符合预期
            if test_case.get("expected_valid", True):
                test_passed = False

        # Update statistics
        if test_passed:
            passed_tests += 1

        print_test_result(i, test_passed)

    print_summary(total_tests, passed_tests, total_tests - passed_tests)
    return passed_tests, total_tests - passed_tests


async def main():
    def print_header():
        print("血清渗透压计算器 MCP 测试")
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
        print("血清渗透压计算器测试结果")
        print("=" * 60)
        print(f"总测试数: {total_tests}")
        print(f"通过数: {total_passed}")
        print(f"失败数: {total_failed}")
        print(f"成功率: {(total_passed/total_tests*100):.1f}%")

        if total_failed == 0:
            print("\n✅ 血清渗透压计算器所有测试都通过了！")
        else:
            print(f"\n❌ {total_failed} 个测试失败，请检查血清渗透压计算器实现。")

    print_header()

    try:
        async with Client(MCP_SERVER_URL) as client:
            print_connection_status(True)
            passed, failed = await test_serum_osmolality_calculator(client)
            print_overall_results(passed, failed)

    except Exception as e:
        print_connection_status(False, str(e))
        import traceback
        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("✅ 血清渗透压计算器测试完成")


if __name__ == "__main__":
    asyncio.run(main())