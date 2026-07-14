import asyncio
import json
import sys
import os
from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVER_URL


async def test_ideal_body_weight_calculator(client):
    """测试理想体重计算器的各种功能和单位转换"""

    def print_header():
        print("\n" + "=" * 60)
        print("理想体重计算器测试套件")
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
        ibw_value = data.get("value", "N/A")
        unit = data.get("unit", "")
        explanation = data.get("explanation", "")
        metadata = data.get("metadata", {})
        warnings = data.get("warnings", [])

        # 基本结果
        print(f"- 理想体重: {ibw_value} {unit}")

        # 原始输入和转换后的值
        if metadata:
            height = metadata.get("height")
            height_unit = metadata.get("height_unit")
            height_inches = metadata.get("height_inches")
            sex = metadata.get("sex")
            formula = metadata.get("formula")

            if height and height_unit:
                print(f"- 输入身高: {height} {height_unit}")
                if height_unit != "inches" and height_inches:
                    print(f"- 转换身高: {height_inches:.1f} inches")
            if sex:
                print(f"- 性别: {sex}")
            if formula:
                print(f"- 公式: {formula}")

        # 警告信息
        if warnings:
            for warning in warnings:
                print(f"- ⚠️  警告: {warning}")

        # 详细解释（截取前几行显示）
        if explanation:
            explanation_lines = explanation.strip().split("\n")
            if len(explanation_lines) > 3:
                print(f"- 解释: {explanation_lines[0]}...")
            else:
                print(f"- 解释: {explanation.strip()}")

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
            print("\n✅ 所有测试都通过了！理想体重计算器工作正常。")
        else:
            print(f"\n❌ {failed} 个测试失败，请检查实现。")

        print("\n测试覆盖范围:")
        features = [
            "多种身高单位 (cm, inches, feet)",
            "性别差异计算 (Male/Female)",
            "自动单位转换",
            "参数验证",
            "Devine公式计算",
            "错误处理",
            "边界测试",
            "详细计算解释",
        ]
        for feature in features:
            print(f"  - {feature}")

    # Test statistics
    total_tests = 0
    passed_tests = 0

    # Test cases
    test_cases = [
        {
            "name": "Standard male (cm)",
            "params": {"height": 175, "sex": "Male", "height_unit": "cm"},
            "expected_valid": True,
            "description": "标准男性身高计算 (175cm)",
        },
        {
            "name": "Standard female (cm)",
            "params": {"height": 165, "sex": "Female", "height_unit": "cm"},
            "expected_valid": True,
            "description": "标准女性身高计算 (165cm)",
        },
        {
            "name": "Male height in inches",
            "params": {"height": 70, "sex": "Male", "height_unit": "inches"},
            "expected_valid": True,
            "description": "男性英寸身高 (70 inches)",
        },
        {
            "name": "Female height in inches",
            "params": {"height": 65, "sex": "Female", "height_unit": "inches"},
            "expected_valid": True,
            "description": "女性英寸身高 (65 inches)",
        },
        {
            "name": "Male height in feet",
            "params": {"height": 5.83, "sex": "Male", "height_unit": "feet"},
            "expected_valid": True,
            "description": "男性英尺身高 (5.83 feet)",
        },
        {
            "name": "Female height in feet",
            "params": {"height": 5.42, "sex": "Female", "height_unit": "feet"},
            "expected_valid": True,
            "description": "女性英尺身高 (5.42 feet)",
        },
        {
            "name": "Default unit (cm)",
            "params": {"height": 180, "sex": "Male"},
            "expected_valid": True,
            "description": "默认单位测试 (180cm, 无height_unit)",
        },
        {
            "name": "Tall male",
            "params": {"height": 200, "sex": "Male", "height_unit": "cm"},
            "expected_valid": True,
            "description": "高个男性 (200cm)",
        },
        {
            "name": "Short female",
            "params": {"height": 150, "sex": "Female", "height_unit": "cm"},
            "expected_valid": True,
            "description": "矮个女性 (150cm)",
        },
        {
            "name": "Very tall person (inches)",
            "params": {"height": 84, "sex": "Male", "height_unit": "inches"},
            "expected_valid": True,
            "description": "非常高的人 (84 inches)",
        },
        {
            "name": "Invalid height (too short)",
            "params": {"height": 50, "sex": "Male", "height_unit": "cm"},
            "expected_valid": False,
            "description": "无效身高（太矮）",
        },
        {
            "name": "Invalid height (too tall)",
            "params": {"height": 300, "sex": "Male", "height_unit": "cm"},
            "expected_valid": False,
            "description": "无效身高（太高）",
        },
        {
            "name": "Invalid sex",
            "params": {"height": 175, "sex": "Unknown", "height_unit": "cm"},
            "expected_valid": False,
            "description": "无效性别",
        },
        {
            "name": "Missing sex parameter",
            "params": {"height": 175, "height_unit": "cm"},
            "expected_valid": False,
            "description": "缺少性别参数",
        },
        {
            "name": "Missing height parameter",
            "params": {"sex": "Male", "height_unit": "cm"},
            "expected_valid": False,
            "description": "缺少身高参数",
        },
        {
            "name": "Invalid height (negative)",
            "params": {"height": -10, "sex": "Male", "height_unit": "cm"},
            "expected_valid": False,
            "description": "无效身高（负数）",
        },
        {
            "name": "Boundary test (min height cm)",
            "params": {"height": 100, "sex": "Female", "height_unit": "cm"},
            "expected_valid": True,
            "description": "边界测试（最小身高 100cm）",
        },
        {
            "name": "Boundary test (max height cm)",
            "params": {"height": 250, "sex": "Male", "height_unit": "cm"},
            "expected_valid": True,
            "description": "边界测试（最大身高 250cm）",
        },
        {
            "name": "Boundary test (min height inches)",
            "params": {"height": 39, "sex": "Female", "height_unit": "inches"},
            "expected_valid": True,
            "description": "边界测试（最小身高 39 inches）",
        },
        {
            "name": "Boundary test (max height inches)",
            "params": {"height": 98, "sex": "Male", "height_unit": "inches"},
            "expected_valid": True,
            "description": "边界测试（最大身高 98 inches）",
        },
        {
            "name": "String height parameter",
            "params": {"height": "168", "sex": "Male"},
            "expected_valid": True,
            "description": "字符串类型身高参数测试 (\"168\")",
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
                    "calculator_id": 10,
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
                    ibw_value = data.get("value")
                    if ibw_value is not None:
                        # 理想体重应该在合理范围内 (30-150 kg)
                        if not (30 <= ibw_value <= 150):
                            print(f"- 警告: 计算结果可能不合理 ({ibw_value} kg)")
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
    """主函数"""
    print("正在启动理想体重计算器测试...")

    try:
        # 连接到 MCP 服务器
        async with Client(MCP_SERVER_URL) as client:
            # 运行测试
            passed, failed = await test_ideal_body_weight_calculator(client)

            # 返回测试结果
            if failed == 0:
                print("\n🎉 所有测试通过！")
                return True
            else:
                print(f"\n❌ {failed} 个测试失败")
                return False

    except Exception as e:
        print(f"测试运行错误: {e}")
        return False


if __name__ == "__main__":
    asyncio.run(main())
