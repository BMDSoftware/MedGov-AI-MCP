import asyncio
import json
import sys
import os
from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVER_URL


async def test_maintenance_fluid_calculator(client):
    """测试维持液体计算器的各种功能和单位转换"""

    def print_header():
        print("\n" + "=" * 60)
        print("维持液体计算器测试套件")
        print("=" * 60)

    def print_test_case(i, test_case):
        print(f"\n测试 {i:2d} | {test_case['name']}")
        print(f"- {test_case['description']}")
        print(f"- 输入参数: {test_case['params']}")
        if "expected_result" in test_case:
            print(f"- 预期结果: {test_case['expected_result']} mL/hr")

    def print_calculation_result(data):
        """打印完整的计算结果"""
        result = data.get("value", "N/A")
        unit = data.get("unit", "")
        explanation = data.get("explanation", "")
        metadata = data.get("metadata", {})
        warnings = data.get("warnings", [])

        # 基本结果
        print(f"- 计算结果: {result} {unit}")

        # 元数据
        if metadata:
            weight_kg = metadata.get("weight_kg")
            fluid_rate = metadata.get("fluid_rate_ml_per_hr") 
            daily_total = metadata.get("daily_total_ml")
            formula = metadata.get("formula")
            rule = metadata.get("rule")

            if weight_kg:
                print(f"- 体重: {weight_kg} kg")
            if fluid_rate:
                print(f"- 液体速率: {fluid_rate} mL/hr")
            if daily_total:
                print(f"- 每日总量: {daily_total} mL/day")
            if formula:
                print(f"- 公式: {formula}")
            if rule:
                print(f"- 规则: {rule}")

        # 警告信息
        if warnings:
            for warning in warnings:
                print(f"- ⚠️  警告: {warning}")

        # 解释
        if explanation:
            print(f"- 解释: {explanation[:100]}...")

    def print_test_result(i, passed, expected_result=None, actual_result=None):
        if passed:
            status = "✅ 通过"
        else:
            status = "❌ 失败"
        print(f"- 测试结果: {status}")
        if expected_result is not None and actual_result is not None:
            print(f"- 预期: {expected_result}, 实际: {actual_result}")
        print("-" * 60)

    def print_summary(total, passed, failed):
        print(f"\n测试总结:")
        print(f"  总测试数: {total}")
        print(f"  通过数: {passed}")
        print(f"  失败数: {failed}")
        print(f"  成功率: {(passed/total*100):.1f}%")

        if failed == 0:
            print("\n✅ 所有测试都通过了！维持液体计算器工作正常。")
        else:
            print(f"\n❌ {failed} 个测试失败，请检查实现。")

        print("\n测试覆盖范围:")
        features = [
            "多种体重单位 (kg, lbs, g)",
            "Holliday-Segar 方法",
            "三段式计算规则",
            "参数验证",
            "错误处理",
            "边界测试",
        ]
        for feature in features:
            print(f"  - {feature}")

    # Test statistics
    total_tests = 0
    passed_tests = 0

    # Test cases based on data file
    test_cases = [
        # 正常测试案例（来自数据文件）
        {
            "name": "Adult weight 90kg",
            "params": {"weight": "90kg"},
            "expected_valid": True,
            "expected_result": 130.0,
            "description": "成人体重90kg，预期130 mL/hr",
        },
        {
            "name": "Adult weight 120kg",
            "params": {"weight": "120kg"},
            "expected_valid": True,
            "expected_result": 160.0,
            "description": "成人体重120kg，预期160 mL/hr",
        },
        {
            "name": "Adult weight 68kg", 
            "params": {"weight": "68kg"},
            "expected_valid": True,
            "expected_result": 108.0,
            "description": "成人体重68kg，预期108 mL/hr",
        },
        {
            "name": "Infant weight 2.8kg",
            "params": {"weight": "2.8kg"},
            "expected_valid": True,
            "expected_result": 11.2,
            "description": "婴儿体重2.8kg，预期11.2 mL/hr",
        },
        {
            "name": "Child weight 30kg",
            "params": {"weight": "30kg"},
            "expected_valid": True,
            "expected_result": 70.0,
            "description": "儿童体重30kg，预期70 mL/hr",
        },
        {
            "name": "Adult weight 88kg",
            "params": {"weight": "88kg"},
            "expected_valid": True,
            "expected_result": 128.0,
            "description": "成人体重88kg，预期128 mL/hr",
        },
        {
            "name": "Weight in pounds 30lbs",
            "params": {"weight": "30lbs"},
            "expected_valid": True,
            "expected_result": 47.216,
            "description": "磅单位30lbs，预期47.216 mL/hr",
        },
        {
            "name": "Child weight 12kg",
            "params": {"weight": "12kg"},
            "expected_valid": True,
            "expected_result": 44.0,
            "description": "儿童体重12kg，预期44 mL/hr",
        },
        {
            "name": "Weight in pounds 22lbs",
            "params": {"weight": "22lbs"},
            "expected_valid": True,
            "expected_result": 39.916,
            "description": "磅单位22lbs，预期39.916 mL/hr",
        },
        {
            "name": "Weight in grams 6300g",
            "params": {"weight": "6300g"},
            "expected_valid": True,
            "expected_result": 25.2,
            "description": "克单位6300g，预期25.2 mL/hr",
        },
        # 边界测试案例
        {
            "name": "Minimum weight 1kg",
            "params": {"weight": "1kg"},
            "expected_valid": True,
            "expected_result": 4.0,
            "description": "最小体重1kg，预期4 mL/hr",
        },
        {
            "name": "Weight at 10kg boundary",
            "params": {"weight": "10kg"},
            "expected_valid": True,
            "expected_result": 40.0,
            "description": "体重边界10kg，预期40 mL/hr",
        },
        {
            "name": "Weight at 20kg boundary",
            "params": {"weight": "20kg"},
            "expected_valid": True,
            "expected_result": 60.0,
            "description": "体重边界20kg，预期60 mL/hr",
        },
        # 错误测试案例
        {
            "name": "Invalid weight (negative)",
            "params": {"weight": "-5kg"},
            "expected_valid": False,
            "description": "无效体重（负数）",
        },
        {
            "name": "Invalid weight (zero)",
            "params": {"weight": "0kg"},
            "expected_valid": False,
            "description": "无效体重（零）",
        },
        {
            "name": "Invalid weight (too large)",
            "params": {"weight": "250kg"},
            "expected_valid": False,
            "description": "无效体重（过大）",
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
                    "calculator_id": 22,
                    "parameters": test_case["params"],
                },
            )

            # 获取计算结果数据
            calc_data = calc_result.structured_content or calc_result.data or {}

            if isinstance(calc_data, dict) and calc_data.get("success") and "result" in calc_data:
                # 成功计算
                data = calc_data["result"]
                print_calculation_result(data)

                # 检查预期结果
                if "expected_result" in test_case:
                    actual_result = data.get("value")
                    expected_result = test_case["expected_result"]
                    
                    # 允许5%的误差
                    if actual_result and abs(actual_result - expected_result) / expected_result > 0.05:
                        print(f"- 错误: 结果不匹配，预期 {expected_result}，实际 {actual_result}")
                        test_passed = False

                # 检查是否符合预期
                if not test_case["expected_valid"]:
                    print("- 错误: 预期失败但计算成功")
                    test_passed = False
            else:
                # 计算失败
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

        expected_result = test_case.get("expected_result")
        actual_result = None
        if "calc_result" in locals() and calc_result:
            try:
                calc_data = calc_result.structured_content or calc_result.data or {}
                if isinstance(calc_data, dict) and calc_data.get("success"):
                    actual_result = calc_data["result"].get("value")
            except:
                pass

        print_test_result(i, test_passed, expected_result, actual_result)

    print_summary(total_tests, passed_tests, total_tests - passed_tests)
    return passed_tests, total_tests - passed_tests


async def main():
    def print_header():
        print("维持液体计算器 MCP 测试")
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
        print("维持液体计算器测试结果")
        print("=" * 60)
        print(f"总测试数: {total_tests}")
        print(f"通过数: {total_passed}")
        print(f"失败数: {total_failed}")
        print(f"成功率: {(total_passed/total_tests*100):.1f}%")

        if total_failed == 0:
            print("\n✅ 维持液体计算器所有测试都通过了！")
        else:
            print(f"\n❌ {total_failed} 个测试失败，请检查维持液体计算器实现。")

    print_header()

    try:
        async with Client(MCP_SERVER_URL) as client:
            print_connection_status(True)
            passed, failed = await test_maintenance_fluid_calculator(client)
            print_overall_results(passed, failed)

    except Exception as e:
        print_connection_status(False, str(e))
        import traceback
        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("✅ 维持液体计算器测试完成")


if __name__ == "__main__":
    asyncio.run(main())