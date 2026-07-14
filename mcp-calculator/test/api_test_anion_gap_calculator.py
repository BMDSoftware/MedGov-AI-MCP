import asyncio
import json
import sys
import os
from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVER_URL


async def test_anion_gap_calculator(client):
    """测试阴离子间隙计算器的各种功能和单位"""

    def print_header():
        print("\n" + "=" * 60)
        print("阴离子间隙计算器测试套件")
        print("=" * 60)

    def print_test_case(i, test_case):
        print(f"\n测试 {i:2d} | {test_case['name']}")
        print(f"- {test_case['description']}")
        print(f"- 输入参数: {test_case['params']}")

    def print_calculation_result(data):
        """打印完整的计算结果"""
        anion_gap_value = data.get("value", "N/A")
        unit = data.get("unit", "")
        explanation = data.get("explanation", "")
        metadata = data.get("metadata", {})
        warnings = data.get("warnings", [])

        # 基本结果
        print(f"- 阴离子间隙值: {anion_gap_value} {unit}")

        # 原始输入值
        if metadata:
            sodium = metadata.get("sodium")
            chloride = metadata.get("chloride")
            bicarbonate = metadata.get("bicarbonate")
            formula = metadata.get("formula", "N/A")

            if sodium is not None:
                print(f"- 钠: {sodium} mEq/L")
            if chloride is not None:
                print(f"- 氯: {chloride} mEq/L")
            if bicarbonate is not None:
                print(f"- 碳酸氢盐: {bicarbonate} mEq/L")
            if formula:
                print(f"- 公式: {formula}")

        # 警告信息
        if warnings:
            for warning in warnings:
                print(f"- ⚠️  警告: {warning}")

        # 详细解释（截取前几行显示）
        if explanation:
            print(f"- 解释: {[explanation.strip()[:200]]}...")

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
            print("\n✅ 所有测试都通过了！阴离子间隙计算器工作正常。")
        else:
            print(f"\n❌ {failed} 个测试失败，请检查实现。")

        print("\n测试覆盖范围:")
        features = [
            "标准参数范围测试",
            "边界值测试",
            "不同数值精度测试",
            "参数验证",
            "错误处理",
            "公式计算准确性",
        ]
        for feature in features:
            print(f"  - {feature}")

    # Test statistics
    total_tests = 0
    passed_tests = 0

    # Test cases based on the data found
    test_cases = [
        {
            "name": "Standard case 1",
            "params": {"sodium": 142.0, "chloride": 123.0, "bicarbonate": 2.0},
            "expected_valid": True,
            "expected_result": 17.0,
            "description": "标准测试用例 (Na: 142, Cl: 123, HCO3: 2)",
        },
        {
            "name": "Standard case 2",
            "params": {"sodium": 139.0, "chloride": 100.0, "bicarbonate": 25.0},
            "expected_valid": True,
            "expected_result": 14.0,
            "description": "标准测试用例 (Na: 139, Cl: 100, HCO3: 25)",
        },
        {
            "name": "Standard case 3",
            "params": {"sodium": 135.0, "chloride": 101.0, "bicarbonate": 20.0},
            "expected_valid": True,
            "expected_result": 14.0,
            "description": "标准测试用例 (Na: 135, Cl: 101, HCO3: 20)",
        },
        {
            "name": "Low anion gap",
            "params": {"sodium": 135.0, "chloride": 113.0, "bicarbonate": 20.0},
            "expected_valid": True,
            "expected_result": 2.0,
            "description": "低阴离子间隙测试 (Na: 135, Cl: 113, HCO3: 20)",
        },
        {
            "name": "High anion gap",
            "params": {"sodium": 140.0, "chloride": 102.0, "bicarbonate": 19.0},
            "expected_valid": True,
            "expected_result": 19.0,
            "description": "高阴离子间隙测试 (Na: 140, Cl: 102, HCO3: 19)",
        },
        {
            "name": "Very high anion gap",
            "params": {"sodium": 144.0, "chloride": 95.0, "bicarbonate": 23.0},
            "expected_valid": True,
            "expected_result": 26.0,
            "description": "极高阴离子间隙测试 (Na: 144, Cl: 95, HCO3: 23)",
        },
        {
            "name": "Decimal values",
            "params": {"sodium": 137.0, "chloride": 104.0, "bicarbonate": 17.7},
            "expected_valid": True,
            "expected_result": 15.3,
            "description": "小数值测试 (Na: 137, Cl: 104, HCO3: 17.7)",
        },
        {
            "name": "Invalid sodium (too low)",
            "params": {"sodium": 100.0, "chloride": 100.0, "bicarbonate": 25.0},
            "expected_valid": False,
            "description": "无效钠值（过低）",
        },
        {
            "name": "Invalid sodium (too high)",
            "params": {"sodium": 200.0, "chloride": 100.0, "bicarbonate": 25.0},
            "expected_valid": False,
            "description": "无效钠值（过高）",
        },
        {
            "name": "Invalid chloride (too low)",
            "params": {"sodium": 140.0, "chloride": 50.0, "bicarbonate": 25.0},
            "expected_valid": False,
            "description": "无效氯值（过低）",
        },
        {
            "name": "Invalid chloride (too high)",
            "params": {"sodium": 140.0, "chloride": 150.0, "bicarbonate": 25.0},
            "expected_valid": False,
            "description": "无效氯值（过高）",
        },
        {
            "name": "Invalid bicarbonate (too low)",
            "params": {"sodium": 140.0, "chloride": 100.0, "bicarbonate": 1.0},
            "expected_valid": False,
            "description": "无效碳酸氢盐值（过低）",
        },
        {
            "name": "Invalid bicarbonate (too high)",
            "params": {"sodium": 140.0, "chloride": 100.0, "bicarbonate": 50.0},
            "expected_valid": False,
            "description": "无效碳酸氢盐值（过高）",
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
                    "calculator_id": 39,
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
                elif "expected_result" in test_case:
                    # 检查结果是否接近预期值（允许小的浮点误差）
                    actual_value = data.get("value", 0)
                    expected_value = test_case["expected_result"]
                    if abs(actual_value - expected_value) > 0.1:
                        print(f"- 错误: 预期结果 {expected_value}，实际结果 {actual_value}")
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
        print("阴离子间隙计算器 MCP 测试")
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
        print("阴离子间隙计算器测试结果")
        print("=" * 60)
        print(f"总测试数: {total_tests}")
        print(f"通过数: {total_passed}")
        print(f"失败数: {total_failed}")
        print(f"成功率: {(total_passed/total_tests*100):.1f}%")

        if total_failed == 0:
            print("\n✅ 阴离子间隙计算器所有测试都通过了！")
        else:
            print(f"\n❌ {total_failed} 个测试失败，请检查阴离子间隙计算器实现。")

    print_header()

    try:
        async with Client(MCP_SERVER_URL) as client:
            print_connection_status(True)
            passed, failed = await test_anion_gap_calculator(client)
            print_overall_results(passed, failed)

    except Exception as e:
        print_connection_status(False, str(e))
        import traceback

        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("✅ 阴离子间隙计算器测试完成")


if __name__ == "__main__":
    asyncio.run(main())