import asyncio
import json
import sys
import os
from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVER_URL


async def test_bsa_calculator(client):
    """测试 BSA 计算器的各种功能和边界情况"""

    def print_header():
        print("\n" + "=" * 60)
        print("BSA (体表面积) 计算器测试套件")
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
        bsa_value = data.get("value", "N/A")
        unit = data.get("unit", "")
        explanation = data.get("explanation", "")
        metadata = data.get("metadata", {})
        warnings = data.get("warnings", [])

        # 基本结果
        print(f"- BSA 值: {bsa_value} {unit}")

        # 输入参数和计算详情
        if metadata:
            height_cm = metadata.get("height_cm")
            weight_kg = metadata.get("weight_kg")
            formula = metadata.get("formula", "N/A")
            clinical_note = metadata.get("clinical_note", "")

            if height_cm:
                print(f"- 输入身高: {height_cm} cm")
            if weight_kg:
                print(f"- 输入体重: {weight_kg} kg")
            if formula:
                print(f"- 计算公式: {formula}")
            if clinical_note:
                print(f"- 临床意义: {clinical_note}")

        # 警告信息
        if warnings:
            for warning in warnings:
                print(f"- ⚠️  警告: {warning}")

        # 详细解释（截取前几行显示）
        if explanation:
            print(f"- 计算过程: {[explanation.strip()]}")

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
            print("\n✅ 所有测试都通过了！BSA 计算器工作正常。")
        else:
            print(f"\n❌ {failed} 个测试失败，请检查实现。")

        print("\n测试覆盖范围:")
        features = [
            "Mosteller 公式计算",
            "标准成人参数",
            "儿童参数",
            "极值边界测试",
            "参数验证",
            "单位转换测试",
            "字符串格式解析",
            "混合单位支持",
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
            "name": "Standard adult male",
            "params": {"height": 175, "weight": 70},
            "expected_valid": True,
            "description": "标准成年男性 (175cm, 70kg)",
        },
        {
            "name": "Standard adult female",
            "params": {"height": 165, "weight": 60},
            "expected_valid": True,
            "description": "标准成年女性 (165cm, 60kg)",
        },
        {
            "name": "Large adult",
            "params": {"height": 185, "weight": 90},
            "expected_valid": True,
            "description": "大体型成人 (185cm, 90kg)",
        },
        {
            "name": "Small adult",
            "params": {"height": 150, "weight": 45},
            "expected_valid": True,
            "description": "小体型成人 (150cm, 45kg)",
        },
        {
            "name": "Child (10 years old)",
            "params": {"height": 140, "weight": 35},
            "expected_valid": True,
            "description": "儿童 (140cm, 35kg)",
        },
        {
            "name": "Toddler (3 years old)",
            "params": {"height": 95, "weight": 15},
            "expected_valid": True,
            "description": "幼儿 (95cm, 15kg)",
        },
        {
            "name": "Very tall person",
            "params": {"height": 220, "weight": 120},
            "expected_valid": True,
            "description": "极高身材 (220cm, 120kg)",
        },
        {
            "name": "Minimum valid height",
            "params": {"height": 30, "weight": 2},
            "expected_valid": True,
            "description": "最小有效身高 (30cm, 2kg)",
        },
        {
            "name": "Maximum valid height",
            "params": {"height": 300, "weight": 200},
            "expected_valid": True,
            "description": "最大有效身高 (300cm, 200kg)",
        },
        {
            "name": "Invalid height (too small)",
            "params": {"height": 25, "weight": 70},
            "expected_valid": False,
            "description": "无效身高（过小）",
        },
        {
            "name": "Invalid height (too large)",
            "params": {"height": 350, "weight": 70},
            "expected_valid": False,
            "description": "无效身高（过大）",
        },
        {
            "name": "Invalid weight (zero)",
            "params": {"height": 175, "weight": 0},
            "expected_valid": False,
            "description": "无效体重（零）",
        },
        {
            "name": "Invalid weight (negative)",
            "params": {"height": 175, "weight": -10},
            "expected_valid": False,
            "description": "无效体重（负数）",
        },
        {
            "name": "Invalid weight (too large)",
            "params": {"height": 175, "weight": 600},
            "expected_valid": False,
            "description": "无效体重（过大）",
        },
        {
            "name": "Missing height",
            "params": {"weight": 70},
            "expected_valid": False,
            "description": "缺少身高参数",
        },
        {
            "name": "Missing weight",
            "params": {"height": 175},
            "expected_valid": False,
            "description": "缺少体重参数",
        },
        # 单位转换测试用例
        {
            "name": "Height in meters",
            "params": {"height": 1.75, "height_unit": "m", "weight": 70},
            "expected_valid": True,
            "description": "高度使用米单位 (1.75m, 70kg)",
        },
        {
            "name": "Height in feet",
            "params": {"height": 5.74, "height_unit": "ft", "weight": 70},
            "expected_valid": True,
            "description": "高度使用英尺单位 (5.74ft, 70kg)",
        },
        {
            "name": "Height in inches",
            "params": {"height": 68.9, "height_unit": "in", "weight": 70},
            "expected_valid": True,
            "description": "高度使用英寸单位 (68.9in, 70kg)",
        },
        {
            "name": "Weight in pounds",
            "params": {"height": 175, "weight": 154.32, "weight_unit": "lbs"},
            "expected_valid": True,
            "description": "体重使用磅单位 (175cm, 154.32lbs)",
        },
        {
            "name": "Weight in grams",
            "params": {"height": 175, "weight": 70000, "weight_unit": "g"},
            "expected_valid": True,
            "description": "体重使用克单位 (175cm, 70000g)",
        },
        {
            "name": "String format height",
            "params": {"height": "175cm", "weight": 70},
            "expected_valid": True,
            "description": "字符串格式高度 (175cm, 70kg)",
        },
        {
            "name": "String format weight",
            "params": {"height": 175, "weight": "70kg"},
            "expected_valid": True,
            "description": "字符串格式体重 (175cm, 70kg)",
        },
        {
            "name": "Both string format",
            "params": {"height": "175cm", "weight": "70kg"},
            "expected_valid": True,
            "description": "字符串格式高度和体重 (175cm, 70kg)",
        },
        {
            "name": "Mixed units (ft + lbs)",
            "params": {"height": 5.74, "height_unit": "ft", "weight": 154.32, "weight_unit": "lbs"},
            "expected_valid": True,
            "description": "混合单位英制 (5.74ft, 154.32lbs)",
        },
        {
            "name": "Mixed units (m + g)",
            "params": {"height": 1.75, "height_unit": "m", "weight": 70000, "weight_unit": "g"},
            "expected_valid": True,
            "description": "混合单位公制 (1.75m, 70000g)",
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
                    "calculator_id": 60,
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
                    # 验证计算结果的合理性
                    bsa_value = data.get("value")
                    if bsa_value is not None:
                        if bsa_value <= 0:
                            print("- 错误: BSA 值应该大于 0")
                            test_passed = False
                        elif bsa_value > 10:  # 极不合理的大值
                            print("- 警告: BSA 值异常大，可能有问题")
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
        print("BSA 计算器 MCP 测试")
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
        print("BSA 计算器测试结果")
        print("=" * 60)
        print(f"总测试数: {total_tests}")
        print(f"通过数: {total_passed}")
        print(f"失败数: {total_failed}")
        print(f"成功率: {(total_passed/total_tests*100):.1f}%")

        if total_failed == 0:
            print("\n✅ BSA 计算器所有测试都通过了！")
        else:
            print(f"\n❌ {total_failed} 个测试失败，请检查 BSA 计算器实现。")

    print_header()

    try:
        async with Client(MCP_SERVER_URL) as client:
            print_connection_status(True)
            passed, failed = await test_bsa_calculator(client)
            print_overall_results(passed, failed)

    except Exception as e:
        print_connection_status(False, str(e))
        import traceback

        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("✅ BSA 计算器测试完成")


if __name__ == "__main__":
    asyncio.run(main())
