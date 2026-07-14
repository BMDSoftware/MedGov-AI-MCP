import asyncio
import json
import sys
import os
from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVER_URL


async def test_target_weight_calculator(client):
    """测试目标体重计算器的各种功能和参数验证"""

    def print_header():
        print("\n" + "=" * 60)
        print("目标体重计算器测试套件")
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
        target_weight = data.get("value", "N/A")
        unit = data.get("unit", "")
        explanation = data.get("explanation", "")
        metadata = data.get("metadata", {})
        warnings = data.get("warnings", [])

        # 基本结果
        print(f"- 目标体重: {target_weight} {unit}")

        # 详细信息
        if metadata:
            height_value = metadata.get("height_value")
            height_unit = metadata.get("height_unit", "cm")
            height_m = metadata.get("height_m")
            target_bmi = metadata.get("target_bmi")
            bmi_category = metadata.get("bmi_category")

            print(f"- 身高: {height_value} {height_unit} ({height_m:.3f} m)")
            print(f"- 目标BMI: {target_bmi} kg/m²")
            print(f"- BMI分类: {bmi_category}")

        # 警告信息
        if warnings:
            for warning in warnings:
                print(f"- ⚠️  警告: {warning}")

        # 计算说明
        if explanation:
            print(f"- 计算说明:")
            for line in explanation.split("\n"):
                if line.strip():
                    print(f"  {line}")

    # 测试用例定义
    test_cases = [
        # 正常测试用例
        {
            "name": "正常体重目标",
            "description": "身高175cm，目标BMI 22（正常范围）",
            "params": {"height": 175, "target_bmi": 22},
            "should_pass": True,
            "expected_weight_range": (65, 70),  # 大约67.4kg
        },
        {
            "name": "偏瘦目标",
            "description": "身高170cm，目标BMI 18.5（正常下限）",
            "params": {"height": 170, "target_bmi": 18.5},
            "should_pass": True,
            "expected_weight_range": (53, 54),  # 大约53.5kg
        },
        {
            "name": "偏胖目标",
            "description": "身高180cm，目标BMI 24.9（正常上限）",
            "params": {"height": 180, "target_bmi": 24.9},
            "should_pass": True,
            "expected_weight_range": (80, 82),  # 大约80.7kg
        },
        {
            "name": "超重目标",
            "description": "身高165cm，目标BMI 28（超重）",
            "params": {"height": 165, "target_bmi": 28},
            "should_pass": True,
            "expected_weight_range": (76, 77),  # 大约76.2kg
        },
        {
            "name": "字符串数值输入",
            "description": "使用字符串格式的数值输入",
            "params": {"height": "170", "target_bmi": "23"},
            "should_pass": True,
            "expected_weight_range": (66, 67),  # 大约66.5kg
        },
        {
            "name": "浮点数输入",
            "description": "使用浮点数格式输入",
            "params": {"height": 175.5, "target_bmi": 21.5},
            "should_pass": True,
            "expected_weight_range": (66, 67),  # 大约66.3kg
        },
        # 边界值测试
        {
            "name": "最小身高",
            "description": "身高100cm（最小值）",
            "params": {"height": 100, "target_bmi": 20},
            "should_pass": True,
            "expected_weight_range": (19, 21),  # 大约20kg
        },
        {
            "name": "最大身高",
            "description": "身高250cm（最大值）",
            "params": {"height": 250, "target_bmi": 20},
            "should_pass": True,
            "expected_weight_range": (124, 126),  # 大约125kg
        },
        {
            "name": "最小BMI",
            "description": "目标BMI 15（最小值）",
            "params": {"height": 170, "target_bmi": 15},
            "should_pass": True,
            "expected_weight_range": (43, 44),  # 大约43.4kg
        },
        {
            "name": "最大BMI",
            "description": "目标BMI 40（最大值）",
            "params": {"height": 170, "target_bmi": 40},
            "should_pass": True,
            "expected_weight_range": (115, 116),  # 大约115.6kg
        },
        # 错误输入测试
        {
            "name": "缺少身高参数",
            "description": "未提供身高参数",
            "params": {"target_bmi": 22},
            "should_pass": False,
            "expected_error": "Height is required",
        },
        {
            "name": "缺少目标BMI参数",
            "description": "未提供目标BMI参数",
            "params": {"height": 170},
            "should_pass": False,
            "expected_error": "Target BMI is required",
        },
        {
            "name": "身高过小",
            "description": "身高99cm（低于最小值）",
            "params": {"height": 99, "target_bmi": 22},
            "should_pass": False,
            "expected_error": "Height must be between 100-250 cm, 1.0-2.5 m, 3.28-8.2 ft, or 39-98 in",
        },
        {
            "name": "身高过大",
            "description": "身高251cm（超过最大值）",
            "params": {"height": 251, "target_bmi": 22},
            "should_pass": False,
            "expected_error": "Height must be between 100-250 cm, 1.0-2.5 m, 3.28-8.2 ft, or 39-98 in",
        },
        {
            "name": "BMI过小",
            "description": "目标BMI 14.9（低于最小值）",
            "params": {"height": 170, "target_bmi": 14.9},
            "should_pass": False,
            "expected_error": "Target BMI must be between 15 and 40 kg/m²",
        },
        {
            "name": "BMI过大",
            "description": "目标BMI 40.1（超过最大值）",
            "params": {"height": 170, "target_bmi": 40.1},
            "should_pass": False,
            "expected_error": "Target BMI must be between 15 and 40 kg/m²",
        },
        {
            "name": "无效身高格式",
            "description": "身高使用无效字符串",
            "params": {"height": "abc", "target_bmi": 22},
            "should_pass": False,
            "expected_error": "Height must be a valid number",
        },
        {
            "name": "无效BMI格式",
            "description": "目标BMI使用无效字符串",
            "params": {"height": 170, "target_bmi": "xyz"},
            "should_pass": False,
            "expected_error": "Target BMI must be a valid number",
        },
        {
            "name": "负数身高",
            "description": "身高为负数",
            "params": {"height": -170, "target_bmi": 22},
            "should_pass": False,
            "expected_error": "Height must be between 100-250 cm, 1.0-2.5 m, 3.28-8.2 ft, or 39-98 in",
        },
        {
            "name": "负数BMI",
            "description": "目标BMI为负数",
            "params": {"height": 170, "target_bmi": -22},
            "should_pass": False,
            "expected_error": "Target BMI must be between 15 and 40 kg/m²",
        },
        # 多单位支持测试用例
        {
            "name": "厘米单位测试",
            "description": "身高175cm，目标BMI 22",
            "params": {"height": 175, "height_unit": "cm", "target_bmi": 22},
            "should_pass": True,
            "expected_weight_range": (67.3, 67.4),
        },
        {
            "name": "米单位测试",
            "description": "身高1.75m，目标BMI 22",
            "params": {"height": 1.75, "height_unit": "m", "target_bmi": 22},
            "should_pass": True,
            "expected_weight_range": (67.3, 67.4),
        },
        {
            "name": "英尺单位测试",
            "description": "身高5.74ft，目标BMI 22",
            "params": {"height": 5.74, "height_unit": "ft", "target_bmi": 22},
            "should_pass": True,
            "expected_weight_range": (67.3, 67.4),
        },
        {
            "name": "英寸单位测试",
            "description": "身高68.9in，目标BMI 22",
            "params": {"height": 68.9, "height_unit": "in", "target_bmi": 22},
            "should_pass": True,
            "expected_weight_range": (67.3, 67.4),
        },
        {
            "name": "默认单位测试",
            "description": "身高175（默认cm），目标BMI 22",
            "params": {"height": 175, "target_bmi": 22},
            "should_pass": True,
            "expected_weight_range": (67.3, 67.4),
        },
        {
            "name": "不同BMI测试",
            "description": "身高1.8m，目标BMI 25",
            "params": {"height": 1.8, "height_unit": "m", "target_bmi": 25},
            "should_pass": True,
            "expected_weight_range": (80.9, 81.1),
        },
        {
            "name": "无效单位测试",
            "description": "使用不支持的单位",
            "params": {"height": 175, "height_unit": "mm", "target_bmi": 22},
            "should_pass": False,
            "expected_error": "Height unit must be one of: cm, m, ft, in",
        },
    ]

    print_header()

    passed_tests = 0
    total_tests = len(test_cases)

    for i, test_case in enumerate(test_cases, 1):
        print_test_case(i, test_case)

        try:
            # 调用计算器
            result = await client.call_tool(
                "calculate", {"calculator_id": 61, "parameters": test_case["params"]}
            )

            # 使用 structured_content 或 data 属性获取实际数据
            calc_data = result.structured_content or result.data or {}

            if test_case["should_pass"]:
                # 期望成功的测试
                if isinstance(calc_data, dict) and calc_data.get("success") and "result" in calc_data:
                    # 成功计算
                    data = calc_data["result"]
                    print_calculation_result(data)

                    # 验证计算结果范围（如果提供）
                    if "expected_weight_range" in test_case:
                        target_weight = data.get("value")
                        min_weight, max_weight = test_case["expected_weight_range"]
                        if min_weight <= target_weight <= max_weight:
                            print(f"- ✅ 计算结果在预期范围内: {min_weight}-{max_weight} kg")
                            passed_tests += 1
                        else:
                            print(
                                f"- ❌ 计算结果超出预期范围: 期望 {min_weight}-{max_weight} kg，实际 {target_weight} kg"
                            )
                    else:
                        passed_tests += 1
                else:
                    # 计算失败
                    error_msg = calc_data.get("error", "未知错误") if isinstance(calc_data, dict) else str(calc_data)
                    print(f"- ❌ 失败: 期望成功但出现错误: {error_msg}")
            else:
                # 期望失败的测试
                if isinstance(calc_data, dict) and calc_data.get("success") and "result" in calc_data:
                    # 计算成功但期望失败
                    print(f"- ❌ 失败: 期望出现错误但计算成功")
                    data = calc_data["result"]
                    print_calculation_result(data)
                else:
                    # 计算失败，符合预期
                    error_msg = calc_data.get("error", "未知错误") if isinstance(calc_data, dict) else str(calc_data)
                    expected_error = test_case.get("expected_error", "")
                    if expected_error in error_msg:
                        print(f"- ✅ 正确捕获预期错误: {error_msg}")
                        passed_tests += 1
                    else:
                        print(f"- ❌ 错误信息不匹配:")
                        print(f"  期望包含: {expected_error}")
                        print(f"  实际错误: {error_msg}")

        except Exception as e:
            print(f"- ❌ 测试异常: {str(e)}")

    # 打印测试总结
    print(f"\n" + "=" * 60)
    print(f"测试总结")
    print(f"=" * 60)
    print(f"总测试数: {total_tests}")
    print(f"通过测试: {passed_tests}")
    print(f"失败测试: {total_tests - passed_tests}")
    print(f"成功率: {passed_tests/total_tests*100:.1f}%")

    if passed_tests == total_tests:
        print("🎉 所有测试通过！目标体重计算器工作正常。")
    else:
        print("⚠️  部分测试失败，请检查计算器实现。")

    # 测试覆盖范围
    print(f"\n测试覆盖范围:")
    features = [
        "多种身高单位 (cm, m, ft, in)",
        "自动单位转换",
        "参数验证和范围检查",
        "BMI 分类判断",
        "错误处理和友好错误信息",
        "边界值测试",
        "字符串和数值输入支持",
        "详细计算解释",
    ]
    for feature in features:
        print(f"  - {feature}")


async def main():
    """主函数"""
    print("连接到 FastMCP 服务器...")

    try:
        async with Client(MCP_SERVER_URL) as client:
            print("✅ 连接成功")
            await test_target_weight_calculator(client)
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        print("请确保 API 服务器正在运行")


if __name__ == "__main__":
    asyncio.run(main())
