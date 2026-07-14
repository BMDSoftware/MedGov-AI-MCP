import asyncio
import json
import sys
import os
from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVER_URL


async def test_has_bled_calculator(client):
    """测试 HAS-BLED 出血风险评分计算器的各种功能"""

    def print_header():
        print("\n" + "=" * 60)
        print("HAS-BLED 出血风险评分计算器测试套件")
        print("=" * 60)

    def print_test_case(i, test_case):
        print(f"\n测试 {i:2d} | {test_case['name']}")
        print(f"- {test_case['description']}")
        print(f"- 输入参数: {test_case['params']}")

    def print_calculation_result(data):
        """打印完整的计算结果"""
        score = data.get("value", "N/A")
        explanation = data.get("explanation", "")
        details = data.get("metadata", {})

        # 基本结果
        print(f"- HAS-BLED 评分: {score}")

        # 详细信息
        if details:
            age = details.get("age", "N/A")
            total_score = details.get("total_score", "N/A")
            risk_level = details.get("risk_level", "N/A")
            score_breakdown = details.get("score_breakdown", {})

            print(f"- 年龄: {age} 岁")
            print(f"- 总评分: {total_score}")
            print(f"- 风险等级: {risk_level}")

            # 评分细分
            if score_breakdown:
                print("- 评分细分:")
                criteria = {
                    "age": "年龄 >65岁",
                    "hypertension": "未控制的高血压",
                    "renal_disease": "肾脏疾病",
                    "liver_disease": "肝脏疾病",
                    "stroke_history": "卒中史",
                    "prior_bleeding": "既往出血史",
                    "labile_inr": "不稳定的INR",
                    "medications_for_bleeding": "出血倾向药物",
                    "alcohol": "酒精使用"
                }
                for key, value in score_breakdown.items():
                    criterion_name = criteria.get(key, key)
                    print(f"  - {criterion_name}: {value} 分")

        # 解释（截取前几行显示）
        if explanation:
            explanation_lines = explanation.split('\n')
            print(f"- 解释: 显示前5行...")
            for line in explanation_lines[:5]:
                if line.strip():
                    print(f"  {line.strip()}")

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
            print("\n✅ 所有测试都通过了！HAS-BLED 计算器工作正常。")
        else:
            print(f"\n❌ {failed} 个测试失败，请检查实现。")

        print("\n测试覆盖范围:")
        features = [
            "年龄评估 (>65岁)",
            "高血压风险因子",
            "肾脏疾病风险因子",
            "肝脏疾病风险因子",
            "卒中史风险因子",
            "既往出血史风险因子",
            "不稳定INR风险因子",
            "出血倾向药物风险因子",
            "酒精使用风险因子 (≥8次/周)",
            "参数验证",
            "风险等级分类",
            "错误处理",
            "边界测试",
        ]
        for feature in features:
            print(f"  - {feature}")

    # Test statistics
    total_tests = 0
    passed_tests = 0

    # Test cases based on HAS-BLED scoring criteria
    test_cases = [
        {
            "name": "Low risk (score 0) - Young healthy patient",
            "params": {
                "age": 45,
                "hypertension": False,
                "renal_disease": False,
                "liver_disease": False,
                "stroke_history": False,
                "prior_bleeding": False,
                "labile_inr": False,
                "medications_for_bleeding": False,
                "alcoholic_drinks": 2
            },
            "expected_valid": True,
            "expected_score": 0,
            "description": "低风险患者 (45岁，无风险因子，少量饮酒)"
        },
        {
            "name": "Low-moderate risk (score 1) - Age factor only",
            "params": {
                "age": 70,
                "hypertension": False,
                "renal_disease": False,
                "liver_disease": False,
                "stroke_history": False,
                "prior_bleeding": False,
                "labile_inr": False,
                "medications_for_bleeding": False,
                "alcoholic_drinks": 3
            },
            "expected_valid": True,
            "expected_score": 1,
            "description": "低-中等风险 (70岁，仅年龄因子)"
        },
        {
            "name": "Moderate risk (score 2) - Age and hypertension",
            "params": {
                "age": 68,
                "hypertension": True,
                "renal_disease": False,
                "liver_disease": False,
                "stroke_history": False,
                "prior_bleeding": False,
                "labile_inr": False,
                "medications_for_bleeding": False,
                "alcoholic_drinks": 5
            },
            "expected_valid": True,
            "expected_score": 2,
            "description": "中等风险 (68岁，高血压)"
        },
        {
            "name": "High risk (score 3) - Multiple factors",
            "params": {
                "age": 72,
                "hypertension": True,
                "renal_disease": True,
                "liver_disease": False,
                "stroke_history": False,
                "prior_bleeding": False,
                "labile_inr": False,
                "medications_for_bleeding": False,
                "alcoholic_drinks": 4
            },
            "expected_valid": True,
            "expected_score": 3,
            "description": "高风险 (72岁，高血压，肾脏疾病)"
        },
        {
            "name": "Very high risk - Multiple factors including alcohol",
            "params": {
                "age": 75,
                "hypertension": True,
                "renal_disease": False,
                "liver_disease": True,
                "stroke_history": True,
                "prior_bleeding": False,
                "labile_inr": False,
                "medications_for_bleeding": True,
                "alcoholic_drinks": 10
            },
            "expected_valid": True,
            "expected_score": 6,
            "description": "极高风险 (75岁，多个风险因子，酒精≥8次/周)"
        },
        {
            "name": "Maximum risk score",
            "params": {
                "age": 80,
                "hypertension": True,
                "renal_disease": True,
                "liver_disease": True,
                "stroke_history": True,
                "prior_bleeding": True,
                "labile_inr": True,
                "medications_for_bleeding": True,
                "alcoholic_drinks": 15
            },
            "expected_valid": True,
            "expected_score": 9,
            "description": "最高风险评分 (所有风险因子都存在)"
        },
        {
            "name": "Invalid age (too young)",
            "params": {
                "age": 17,
                "hypertension": False,
                "renal_disease": False,
                "liver_disease": False,
                "stroke_history": False,
                "prior_bleeding": False,
                "labile_inr": False,
                "medications_for_bleeding": False,
                "alcoholic_drinks": 0
            },
            "expected_valid": False,
            "description": "无效年龄 (17岁，小于18岁)"
        },
        {
            "name": "Invalid age (too old)",
            "params": {
                "age": 125,
                "hypertension": False,
                "renal_disease": False,
                "liver_disease": False,
                "stroke_history": False,
                "prior_bleeding": False,
                "labile_inr": False,
                "medications_for_bleeding": False,
                "alcoholic_drinks": 0
            },
            "expected_valid": False,
            "description": "无效年龄 (125岁，大于120岁)"
        },
        {
            "name": "Invalid alcoholic drinks (negative)",
            "params": {
                "age": 65,
                "hypertension": False,
                "renal_disease": False,
                "liver_disease": False,
                "stroke_history": False,
                "prior_bleeding": False,
                "labile_inr": False,
                "medications_for_bleeding": False,
                "alcoholic_drinks": -1
            },
            "expected_valid": False,
            "description": "无效酒精次数 (负数)"
        },
        {
            "name": "Boundary test - Age exactly 65",
            "params": {
                "age": 65,
                "hypertension": False,
                "renal_disease": False,
                "liver_disease": False,
                "stroke_history": False,
                "prior_bleeding": False,
                "labile_inr": False,
                "medications_for_bleeding": False,
                "alcoholic_drinks": 0
            },
            "expected_valid": True,
            "expected_score": 0,
            "description": "边界测试 (年龄恰好65岁，不计分)"
        },
        {
            "name": "Boundary test - Alcohol exactly 8 drinks",
            "params": {
                "age": 50,
                "hypertension": False,
                "renal_disease": False,
                "liver_disease": False,
                "stroke_history": False,
                "prior_bleeding": False,
                "labile_inr": False,
                "medications_for_bleeding": False,
                "alcoholic_drinks": 8
            },
            "expected_valid": True,
            "expected_score": 1,
            "description": "边界测试 (酒精恰好8次/周，计1分)"
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
                    "calculator_id": 25,  # HAS-BLED calculator ID
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
                    actual_score = data.get("value")
                    expected_score = test_case["expected_score"]
                    if actual_score != expected_score:
                        print(f"- 错误: 预期评分 {expected_score}，实际评分 {actual_score}")
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
        print("HAS-BLED 出血风险评分计算器 MCP 测试")
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
        print("HAS-BLED 计算器测试结果")
        print("=" * 60)
        print(f"总测试数: {total_tests}")
        print(f"通过数: {total_passed}")
        print(f"失败数: {total_failed}")
        print(f"成功率: {(total_passed/total_tests*100):.1f}%")

        if total_failed == 0:
            print("\n✅ HAS-BLED 计算器所有测试都通过了！")
        else:
            print(f"\n❌ {total_failed} 个测试失败，请检查 HAS-BLED 计算器实现。")

    print_header()

    try:
        async with Client(MCP_SERVER_URL) as client:
            print_connection_status(True)
            passed, failed = await test_has_bled_calculator(client)
            print_overall_results(passed, failed)

    except Exception as e:
        print_connection_status(False, str(e))
        import traceback

        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("✅ HAS-BLED 计算器测试完成")


if __name__ == "__main__":
    asyncio.run(main())