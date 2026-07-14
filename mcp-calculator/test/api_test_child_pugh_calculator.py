import asyncio
import json
import sys
import os
from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVER_URL


async def test_child_pugh_calculator(client):
    """测试 Child-Pugh 计算器的各种功能"""

    def print_header():
        print("\n" + "=" * 60)
        print("Child-Pugh Score 计算器测试套件")
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
        score_value = data.get("value", "N/A")
        unit = data.get("unit", "")
        explanation = data.get("explanation", "")
        metadata = data.get("metadata", {})
        warnings = data.get("warnings", [])

        # 基本结果
        print(f"- Child-Pugh Score: {score_value} {unit}")

        # 元数据信息
        if metadata:
            bilirubin = metadata.get("bilirubin")
            albumin = metadata.get("albumin")
            inr = metadata.get("inr")
            ascites = metadata.get("ascites")
            encephalopathy = metadata.get("encephalopathy")
            child_pugh_class = metadata.get("class", "N/A")

            if bilirubin is not None:
                print(f"- 总胆红素: {bilirubin} mg/dL")
            if albumin is not None:
                print(f"- 白蛋白: {albumin} g/dL")
            if inr is not None:
                print(f"- INR: {inr}")
            if ascites:
                print(f"- 腹水: {ascites}")
            if encephalopathy:
                print(f"- 肝性脑病: {encephalopathy}")
            if child_pugh_class:
                print(f"- Child-Pugh 分级: {child_pugh_class}")

        # 警告信息
        if warnings:
            for warning in warnings:
                print(f"- ⚠️  警告: {warning}")

        # 详细解释（截取前几行显示）
        if explanation:
            lines = explanation.strip().split('\n')
            print(f"- 解释: {lines[0][:100]}...")

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
            print("\n✅ 所有测试都通过了！Child-Pugh 计算器工作正常。")
        else:
            print(f"\n❌ {failed} 个测试失败，请检查实现。")

        print("\n测试覆盖范围:")
        features = [
            "Child-Pugh Score 计算",
            "多种分级判断 (Class A, B, C)",
            "参数验证",
            "边界值测试",
            "错误处理",
            "肝功能评估参数",
        ]
        for feature in features:
            print(f"  - {feature}")

    # Test statistics
    total_tests = 0
    passed_tests = 0

    # Test cases
    test_cases = [
        {
            "name": "Child-Pugh Class A (Score 5)",
            "params": {"bilirubin": 1.5, "albumin": 3.8, "inr": 1.2, "ascites": "Absent", "encephalopathy": "No Encephalopathy"},
            "expected_valid": True,
            "expected_score": 5,
            "expected_class": "Class A",
            "description": "典型的 Class A 患者 (轻度肝硬化)",
        },
        {
            "name": "Child-Pugh Class A (Score 6)",
            "params": {"bilirubin": 2.5, "albumin": 3.2, "inr": 1.5, "ascites": "Absent", "encephalopathy": "No Encephalopathy"},
            "expected_valid": True,
            "expected_score": 7,
            "expected_class": "Class B",
            "description": "Class A/B 边界测试 (实际为 Class B)",
        },
        {
            "name": "Child-Pugh Class B (Score 7)",
            "params": {"bilirubin": 1.8, "albumin": 3.6, "inr": 1.6, "ascites": "Absent", "encephalopathy": "No Encephalopathy"},
            "expected_valid": True,
            "expected_score": 5,
            "expected_class": "Class A",
            "description": "Class A 边界值测试",
        },
        {
            "name": "Child-Pugh Class B (Score 8)",
            "params": {"bilirubin": 2.2, "albumin": 3.0, "inr": 1.8, "ascites": "Absent", "encephalopathy": "Grade 1-2"},
            "expected_valid": True,
            "expected_score": 9,
            "expected_class": "Class B",
            "description": "Class B 测试",
        },
        {
            "name": "Child-Pugh Class B (Score 9)",
            "params": {"bilirubin": 3.5, "albumin": 2.5, "inr": 2.0, "ascites": "Slight", "encephalopathy": "No Encephalopathy"},
            "expected_valid": True,
            "expected_score": 11,
            "expected_class": "Class C",
            "description": "Class C 测试（修正）",
        },
        {
            "name": "Child-Pugh Class C (Score 10)",
            "params": {"bilirubin": 4.0, "albumin": 2.5, "inr": 2.5, "ascites": "Slight", "encephalopathy": "No Encephalopathy"},
            "expected_valid": True,
            "expected_score": 12,
            "expected_class": "Class C",
            "description": "Class C 测试（修正）",
        },
        {
            "name": "Child-Pugh Class C (Score 15 - Maximum)",
            "params": {"bilirubin": 5.0, "albumin": 2.0, "inr": 3.0, "ascites": "Moderate", "encephalopathy": "Grade 3-4"},
            "expected_valid": True,
            "expected_score": 15,
            "expected_class": "Class C",
            "description": "最高分数测试 (最严重肝硬化)",
        },
        {
            "name": "With Grade 1-2 Encephalopathy",
            "params": {"bilirubin": 2.0, "albumin": 3.0, "inr": 1.5, "ascites": "Absent", "encephalopathy": "Grade 1-2"},
            "expected_valid": True,
            "expected_score": 8,
            "expected_class": "Class B",
            "description": "包含轻度肝性脑病（修正）",
        },
        {
            "name": "Boundary Values - Low Normal",
            "params": {"bilirubin": 0.5, "albumin": 4.0, "inr": 1.0, "ascites": "Absent", "encephalopathy": "No Encephalopathy"},
            "expected_valid": True,
            "expected_score": 5,
            "expected_class": "Class A",
            "description": "正常低值边界测试",
        },
        {
            "name": "Invalid bilirubin (negative)",
            "params": {"bilirubin": -1.0, "albumin": 3.5, "inr": 1.2, "ascites": "Absent", "encephalopathy": "No Encephalopathy"},
            "expected_valid": False,
            "description": "无效胆红素值 (负数)",
        },
        {
            "name": "Invalid bilirubin (too high)",
            "params": {"bilirubin": 35.0, "albumin": 3.5, "inr": 1.2, "ascites": "Absent", "encephalopathy": "No Encephalopathy"},
            "expected_valid": False,
            "description": "胆红素值超出范围",
        },
        {
            "name": "Invalid albumin (too low)",
            "params": {"bilirubin": 2.0, "albumin": 0.5, "inr": 1.2, "ascites": "Absent", "encephalopathy": "No Encephalopathy"},
            "expected_valid": False,
            "description": "白蛋白值过低",
        },
        {
            "name": "Invalid INR (too low)",
            "params": {"bilirubin": 2.0, "albumin": 3.5, "inr": 0.5, "ascites": "Absent", "encephalopathy": "No Encephalopathy"},
            "expected_valid": False,
            "description": "INR 值过低",
        },
        {
            "name": "Invalid INR (too high)",
            "params": {"bilirubin": 2.0, "albumin": 3.5, "inr": 15.0, "ascites": "Absent", "encephalopathy": "No Encephalopathy"},
            "expected_valid": False,
            "description": "INR 值过高",
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
                    "calculator_id": 15,
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
                    # 验证分数和分级
                    if "expected_score" in test_case:
                        actual_score = data.get("value")
                        expected_score = test_case["expected_score"]
                        if actual_score != expected_score:
                            print(f"- 错误: 预期分数 {expected_score}, 实际分数 {actual_score}")
                            test_passed = False
                    
                    if "expected_class" in test_case:
                        metadata = data.get("metadata", {})
                        actual_class = metadata.get("class")
                        expected_class = test_case["expected_class"]
                        if actual_class != expected_class:
                            print(f"- 错误: 预期分级 {expected_class}, 实际分级 {actual_class}")
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
        print("Child-Pugh Score 计算器 MCP 测试")
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
        print("Child-Pugh Score 计算器测试结果")
        print("=" * 60)
        print(f"总测试数: {total_tests}")
        print(f"通过数: {total_passed}")
        print(f"失败数: {total_failed}")
        print(f"成功率: {(total_passed/total_tests*100):.1f}%")

        if total_failed == 0:
            print("\n✅ Child-Pugh Score 计算器所有测试都通过了！")
        else:
            print(f"\n❌ {total_failed} 个测试失败，请检查 Child-Pugh Score 计算器实现。")

    print_header()

    try:
        async with Client(MCP_SERVER_URL) as client:
            print_connection_status(True)
            passed, failed = await test_child_pugh_calculator(client)
            print_overall_results(passed, failed)

    except Exception as e:
        print_connection_status(False, str(e))
        import traceback

        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("✅ Child-Pugh Score 计算器测试完成")


if __name__ == "__main__":
    asyncio.run(main())