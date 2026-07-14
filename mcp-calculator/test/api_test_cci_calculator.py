import asyncio
import json
import sys
import os
from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVER_URL


async def test_cci_calculator(client):
    """测试 CCI 计算器的各种功能"""

    def print_header():
        print("\n" + "=" * 60)
        print("CCI 计算器测试套件")
        print("=" * 60)

    def print_test_case(i, test_case):
        print(f"\n测试 {i:2d} | {test_case['name']}")
        print(f"- {test_case['description']}")
        print(f"- 输入参数: {test_case['params']}")

    def print_calculation_result(data):
        """打印完整的计算结果"""
        score = data.get("value", "N/A")
        unit = data.get("unit", "")
        explanation = data.get("explanation", "")
        metadata = data.get("metadata", {})
        warnings = data.get("warnings", [])

        # 基本结果
        print(f"- CCI 评分: {score} {unit}")

        # 元数据信息
        if metadata:
            age_points = metadata.get("age_points", "N/A")
            ten_year_survival = metadata.get("ten_year_survival", "N/A")
            breakdown = metadata.get("comorbidity_breakdown", {})

            print(f"- 年龄评分: {age_points}")
            print(f"- 10年生存率: {ten_year_survival}")

            # 按系统分组的评分
            if breakdown:
                print("- 疾病分组评分:")
                for system, points in breakdown.items():
                    if points > 0:
                        print(f"  - {system}: {points} points")

        # 警告信息
        if warnings:
            for warning in warnings:
                print(f"- ⚠️  警告: {warning}")

        # 详细解释（截取前几行显示）
        if explanation:
            explanation_lines = explanation.split('\n')[:5]
            print(f"- 解释摘要: {explanation_lines[0] if explanation_lines else ''}")

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
            print("\n✅ 所有测试都通过了！CCI 计算器工作正常。")
        else:
            print(f"\n❌ {failed} 个测试失败，请检查实现。")

        print("\n测试覆盖范围:")
        features = [
            "年龄评分计算",
            "心血管疾病",
            "神经系统疾病",
            "肺部疾病",
            "胃肠道疾病",
            "内分泌疾病",
            "肾脏疾病",
            "恶性肿瘤",
            "免疫系统疾病",
            "10年生存率预测",
            "参数验证",
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
            "name": "健康年轻人 (无合并症)",
            "params": {"age": 25},
            "expected_valid": True,
            "expected_score": 0,
            "description": "25岁，无任何合并症",
        },
        {
            "name": "中年人单一合并症",
            "params": {"age": 55, "mi": True},
            "expected_valid": True,
            "expected_score": 2,
            "description": "55岁（1分），有心肌梗死史（1分）",
        },
        {
            "name": "老年人多重合并症",
            "params": {
                "age": 75,
                "mi": True,
                "chf": True,
                "diabetes_mellitus": "uncomplicated",
                "copd": True
            },
            "expected_valid": True,
            "expected_score": 7,
            "description": "75岁，心梗+心衰+糖尿病+COPD",
        },
        {
            "name": "高分值疾病",
            "params": {
                "age": 65,
                "solid_tumor": "metastatic",
                "liver_disease": "moderate_to_severe"
            },
            "expected_valid": True,
            "expected_score": 11,
            "description": "65岁，转移性肿瘤+中重度肝病",
        },
        {
            "name": "糖尿病终末器官损害",
            "params": {
                "age": 60,
                "diabetes_mellitus": "end_organ_damage",
                "moderate_to_severe_ckd": True
            },
            "expected_valid": True,
            "expected_score": 6,
            "description": "60岁，糖尿病终末器官损害+CKD",
        },
        {
            "name": "脑血管疾病",
            "params": {
                "age": 70,
                "cva": True,
                "tia": True,
                "hemiplegia": True
            },
            "expected_valid": True,
            "expected_score": 6,
            "description": "70岁，CVA+TIA+偏瘫",
        },
        {
            "name": "血液恶性肿瘤",
            "params": {
                "age": 50,
                "leukemia": True,
                "lymphoma": True
            },
            "expected_valid": True,
            "expected_score": 5,
            "description": "50岁，白血病+淋巴瘤",
        },
        {
            "name": "AIDS患者",
            "params": {
                "age": 40,
                "aids": True,
                "connective_tissue_disease": True
            },
            "expected_valid": True,
            "expected_score": 7,
            "description": "40岁，AIDS+结缔组织病",
        },
        {
            "name": "肝病分级测试",
            "params": {
                "age": 55,
                "liver_disease": "mild"
            },
            "expected_valid": True,
            "expected_score": 2,
            "description": "55岁，轻度肝病",
        },
        {
            "name": "边界年龄测试 (80岁)",
            "params": {"age": 80},
            "expected_valid": True,
            "expected_score": 4,
            "description": "80岁，测试年龄边界",
        },
        {
            "name": "无效年龄 (负数)",
            "params": {"age": -5},
            "expected_valid": False,
            "description": "无效年龄测试",
        },
        {
            "name": "无效年龄 (超出范围)",
            "params": {"age": 150},
            "expected_valid": False,
            "description": "年龄超出范围测试",
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
                    "calculator_id": 32,
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
                elif "expected_score" in test_case:
                    actual_score = data.get("value", 0)
                    if actual_score != test_case["expected_score"]:
                        print(f"- 错误: 预期评分 {test_case['expected_score']}，实际评分 {actual_score}")
                        test_passed = False
                    else:
                        print(f"- ✅ 评分正确: {actual_score}")
            else:
                # 计算失败（可能是参数验证失败）
                error_msg = calc_data.get("error", "未知错误") if isinstance(calc_data, dict) else str(calc_data)
                print(f"- 计算失败: {error_msg}")

                # 检查是否符合预期
                if test_case["expected_valid"]:
                    print("- 错误: 预期成功但计算失败")
                    test_passed = False
                else:
                    print("- ✅ 正确拒绝了无效输入")

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
        print("CCI 计算器 MCP 测试")
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
        print("CCI 计算器测试结果")
        print("=" * 60)
        print(f"总测试数: {total_tests}")
        print(f"通过数: {total_passed}")
        print(f"失败数: {total_failed}")
        print(f"成功率: {(total_passed/total_tests*100):.1f}%")

        if total_failed == 0:
            print("\n✅ CCI 计算器所有测试都通过了！")
        else:
            print(f"\n❌ {total_failed} 个测试失败，请检查 CCI 计算器实现。")

    print_header()

    try:
        async with Client(MCP_SERVER_URL) as client:
            print_connection_status(True)
            passed, failed = await test_cci_calculator(client)
            print_overall_results(passed, failed)

    except Exception as e:
        print_connection_status(False, str(e))
        import traceback

        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("✅ CCI 计算器测试完成")


if __name__ == "__main__":
    asyncio.run(main())