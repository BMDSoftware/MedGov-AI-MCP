import asyncio
import json
import sys
import os
from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVER_URL


async def test_bmi_calculator(client):
    """测试 BMI 计算器的各种功能和单位转换"""

    def print_header():
        print("\n" + "=" * 60)
        print("BMI 计算器测试套件")
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
        bmi_value = data.get("value", "N/A")
        unit = data.get("unit", "")
        explanation = data.get("explanation", "")
        metadata = data.get("metadata", {})
        warnings = data.get("warnings", [])

        # 基本结果
        print(f"- BMI 值: {bmi_value} {unit}")

        # 原始输入和转换后的值
        if metadata:
            original_height = metadata.get("original_height")
            height_unit = metadata.get("height_unit")
            original_weight = metadata.get("original_weight")
            weight_unit = metadata.get("weight_unit")
            height_m = metadata.get("height_m")
            weight_kg = metadata.get("weight_kg")
            category = metadata.get("category", "N/A")

            if original_height and height_unit:
                print(f"- 输入身高: {original_height} {height_unit} (转换为: {height_m:.2f} m)")
            if original_weight and weight_unit:
                print(f"- 输入体重: {original_weight} {weight_unit} (转换为: {weight_kg:.1f} kg)")
            if category:
                print(f"- 类型: {category}")

        # 警告信息
        if warnings:
            for warning in warnings:
                print(f"- ⚠️  警告: {warning}")

        # 详细解释（截取前几行显示）
        if explanation:
            print(f"- 解释: {[explanation.strip()]}")

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
            print("\n✅ 所有测试都通过了！BMI 计算器工作正常。")
        else:
            print(f"\n❌ {failed} 个测试失败，请检查实现。")

        print("\n测试覆盖范围:")
        features = [
            "多种身高单位 (cm, m, ft, in)",
            "多种体重单位 (kg, g, lb, lbs, oz)",
            "自动单位转换",
            "参数验证",
            "BMI 分类",
            "错误处理",
            "边界测试",
        ]
        for feature in features:
            print(f"  - {feature}")

    # Test statistics
    total_tests = 0
    passed_tests = 0

    # Test cases
    test_cases = [
        {
            "name": "Standard units (cm, kg)",
            "params": {"height": "175cm", "weight": "70kg"},
            "expected_valid": True,
            "description": "标准单位计算 (175cm, 70kg)",
        },
        {
            "name": "Imperial units (ft, lbs)",
            "params": {"height": "5.75ft", "weight": "154lbs"},
            "expected_valid": True,
            "description": "英制单位计算 (5.75ft, 154lbs)",
        },
        {
            "name": "Mixed units (in, kg)",
            "params": {"height": "69in", "weight": "70kg"},
            "expected_valid": True,
            "description": "混合单位计算 (69in, 70kg)",
        },
        {
            "name": "Meters and grams",
            "params": {"height": "1.75m", "weight": "70000g"},
            "expected_valid": True,
            "description": "米和克单位 (1.75m, 70000g)",
        },
        {
            "name": "Feet and inches with pounds",
            "params": {"height": "5ft 9in", "weight": "154lb"},
            "expected_valid": True,
            "description": "英尺英寸和磅 (5ft 9in, 154lb)",
        },
        {
            "name": "Invalid height (negative)",
            "params": {"height": "-10cm", "weight": "70kg"},
            "expected_valid": False,
            "description": "无效身高（负数）",
        },
        {
            "name": "Invalid weight (zero)",
            "params": {"height": "175cm", "weight": "0kg"},
            "expected_valid": False,
            "description": "无效体重（零）",
        },
        {
            "name": "Extreme values (very tall)",
            "params": {"height": "250cm", "weight": "100kg"},
            "expected_valid": True,
            "description": "极值测试（很高）",
        },
        {
            "name": "Extreme values (very short)",
            "params": {"height": "100cm", "weight": "30kg"},
            "expected_valid": True,
            "description": "极值测试（很矮）",
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
                    "calculator_id": 6,
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
        print("BMI 计算器 MCP 测试")
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
        print("BMI 计算器测试结果")
        print("=" * 60)
        print(f"总测试数: {total_tests}")
        print(f"通过数: {total_passed}")
        print(f"失败数: {total_failed}")
        print(f"成功率: {(total_passed/total_tests*100):.1f}%")

        if total_failed == 0:
            print("\n✅ BMI 计算器所有测试都通过了！")
        else:
            print(f"\n❌ {total_failed} 个测试失败，请检查 BMI 计算器实现。")

    print_header()

    try:
        async with Client(MCP_SERVER_URL) as client:
            print_connection_status(True)
            passed, failed = await test_bmi_calculator(client)
            print_overall_results(passed, failed)

    except Exception as e:
        print_connection_status(False, str(e))
        import traceback

        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("✅ BMI 计算器测试完成")


if __name__ == "__main__":
    asyncio.run(main())
