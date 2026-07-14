import asyncio
import json
import sys
import os
from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVER_URL


async def test_delta_ratio_calculator(client):
    """测试 Delta Ratio 计算器的各种功能和参数验证"""

    def print_header():
        print("\n" + "=" * 60)
        print("Delta Ratio 计算器测试套件")
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

    def print_calculation_result(data, expected_result=None):
        """打印完整的计算结果"""
        delta_ratio_value = data.get("value", "N/A")
        unit = data.get("unit", "")
        explanation = data.get("explanation", "")
        metadata = data.get("metadata", {})
        warnings = data.get("warnings", [])

        # 基本结果
        print(f"- Delta Ratio: {delta_ratio_value} {unit}")
        
        # 预期结果比较
        if expected_result is not None:
            if abs(float(delta_ratio_value) - float(expected_result)) < 0.1:
                print(f"- ✅ 结果匹配预期: {expected_result}")
            else:
                print(f"- ❌ 结果不匹配: 预期 {expected_result}, 实际 {delta_ratio_value}")

        # 元数据
        if metadata:
            sodium = metadata.get("sodium", "N/A")
            chloride = metadata.get("chloride", "N/A")
            bicarbonate = metadata.get("bicarbonate", "N/A")
            anion_gap = metadata.get("anion_gap", "N/A")
            delta_gap = metadata.get("delta_gap", "N/A")
            clinical_note = metadata.get("clinical_note", "")

            print(f"- 输入 - Na+: {sodium} mEq/L, Cl-: {chloride} mEq/L, HCO3-: {bicarbonate} mEq/L")
            print(f"- 计算 - 阴离子间隙: {anion_gap}, Delta Gap: {delta_gap}")
            if clinical_note:
                print(f"- 临床意义: {clinical_note}")

        # 警告信息
        if warnings:
            for warning in warnings:
                print(f"- ⚠️  警告: {warning}")

        # 解释（显示部分）
        if explanation and len(explanation) > 100:
            print(f"- 解释: {explanation[:100]}...")
        elif explanation:
            print(f"- 解释: {explanation}")

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
            print("\n✅ 所有测试都通过了！Delta Ratio 计算器工作正常。")
        else:
            print(f"\n❌ {failed} 个测试失败，请检查实现。")

        print("\n测试覆盖范围:")
        features = [
            "基本Delta Ratio计算",
            "阴离子间隙计算",
            "参数验证 (Na+, Cl-, HCO3-)",
            "边界值测试",
            "错误处理",
            "临床解释",
        ]
        for feature in features:
            print(f"  - {feature}")

    # Test statistics
    total_tests = 0
    passed_tests = 0

    # Test cases based on the data file and additional edge cases
    test_cases = [
        {
            "name": "Standard case 1",
            "params": {"sodium": 143, "chloride": 112, "bicarbonate": 22},
            "expected_valid": True,
            "expected_result": -1.5,
            "description": "标准计算 (Na+=143, Cl-=112, HCO3-=22)",
        },
        {
            "name": "Standard case 2",
            "params": {"sodium": 140, "chloride": 101, "bicarbonate": 22},
            "expected_valid": True,
            "expected_result": 2.5,
            "description": "标准计算 (Na+=140, Cl-=101, HCO3-=22)",
        },
        {
            "name": "High anion gap case",
            "params": {"sodium": 139, "chloride": 95.3, "bicarbonate": 13.8},
            "expected_valid": True,
            "expected_result": 1.755,
            "description": "高阴离子间隙病例",
        },
        {
            "name": "Normal gap case",
            "params": {"sodium": 137, "chloride": 100, "bicarbonate": 25},
            "expected_valid": True,
            "expected_result": 0,
            "description": "正常间隙病例",
        },
        {
            "name": "Low bicarbonate case",
            "params": {"sodium": 136, "chloride": 101, "bicarbonate": 5},
            "expected_valid": True,
            "expected_result": 0.947,
            "description": "低碳酸氢盐病例",
        },
        {
            "name": "Invalid sodium (too low)",
            "params": {"sodium": 110, "chloride": 100, "bicarbonate": 20},
            "expected_valid": False,
            "description": "无效钠离子（过低）",
        },
        {
            "name": "Invalid chloride (too high)",
            "params": {"sodium": 140, "chloride": 130, "bicarbonate": 20},
            "expected_valid": False,
            "description": "无效氯离子（过高）",
        },
        {
            "name": "Invalid bicarbonate (too low)",
            "params": {"sodium": 140, "chloride": 100, "bicarbonate": 5},
            "expected_valid": True,  # 5 is at the lower limit but valid
            "expected_result": 1.211,
            "description": "边界碳酸氢盐值（下限）",
        },
        {
            "name": "Bicarbonate = 24 (denominator = 0)",
            "params": {"sodium": 140, "chloride": 100, "bicarbonate": 24},
            "expected_valid": False,  # This should cause division by zero
            "description": "分母为零的情况 (HCO3-=24)",
        },
        {
            "name": "String parameters test",
            "params": {"sodium": "140", "chloride": "100", "bicarbonate": "20"},
            "expected_valid": True,
            "expected_result": 2.0,
            "description": "字符串参数测试",
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
                    "calculator_id": 64,
                    "parameters": test_case["params"],
                },
            )

            # 使用 structured_content 或 data 属性获取实际数据
            calc_data = calc_result.structured_content or calc_result.data or {}

            if isinstance(calc_data, dict) and calc_data.get("success") and "result" in calc_data:
                # 成功计算
                data = calc_data["result"]
                expected_result = test_case.get("expected_result")
                print_calculation_result(data, expected_result)

                # 检查是否符合预期
                if not test_case["expected_valid"]:
                    print("- 错误: 预期失败但计算成功")
                    test_passed = False
                elif expected_result is not None:
                    actual_result = float(data.get("value", 0))
                    if abs(actual_result - expected_result) > 0.1:
                        print(f"- 错误: 计算结果不准确，预期 {expected_result}, 实际 {actual_result}")
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
        print("Delta Ratio 计算器 MCP 测试")
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
        print("Delta Ratio 计算器测试结果")
        print("=" * 60)
        print(f"总测试数: {total_tests}")
        print(f"通过数: {total_passed}")
        print(f"失败数: {total_failed}")
        print(f"成功率: {(total_passed/total_tests*100):.1f}%")

        if total_failed == 0:
            print("\n✅ Delta Ratio 计算器所有测试都通过了！")
        else:
            print(f"\n❌ {total_failed} 个测试失败，请检查 Delta Ratio 计算器实现。")

    print_header()

    try:
        async with Client(MCP_SERVER_URL) as client:
            print_connection_status(True)
            passed, failed = await test_delta_ratio_calculator(client)
            print_overall_results(passed, failed)

    except Exception as e:
        print_connection_status(False, str(e))
        import traceback

        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("✅ Delta Ratio 计算器测试完成")


if __name__ == "__main__":
    asyncio.run(main())