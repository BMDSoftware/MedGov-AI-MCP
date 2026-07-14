# -*- coding: utf-8 -*-
import asyncio
import json
import sys
import os
from fastmcp import Client

# Set UTF-8 encoding for output
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVER_URL


async def test_cardiac_risk_index_calculator(client):
    """测试 Revised Cardiac Risk Index 计算器的各种功能"""

    def print_header():
        print("\n" + "=" * 60)
        print("Revised Cardiac Risk Index 计算器测试套件")
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
        print(f"- RCRI 分数: {score} {unit}")

        # 风险分类
        if metadata:
            risk_category = metadata.get("risk_category", "N/A")
            criteria_met = metadata.get("criteria_met", {})
            
            print(f"- 风险分类: {risk_category}")
            
            # 显示满足的标准
            print("- 满足的标准:")
            for criterion, met in criteria_met.items():
                status = "是" if met else "否"
                print(f"  - {criterion}: {status}")

        # 警告信息
        if warnings:
            for warning in warnings:
                print(f"- ⚠️  警告: {warning}")

        # 详细解释（截取前几行显示）
        if explanation:
            explanation_lines = explanation.split('\n')[:5]
            print(f"- 解释: {explanation_lines[0][:100]}..." if len(explanation_lines[0]) > 100 else explanation_lines[0])

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
            print("\n✅ 所有测试都通过了！Revised Cardiac Risk Index 计算器工作正常。")
        else:
            print(f"\n❌ {failed} 个测试失败，请检查实现。")

        print("\n测试覆盖范围:")
        features = [
            "不同风险因子组合",
            "肌酐水平变化",
            "边界值测试",
            "参数验证",
            "风险分层",
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
            "name": "最低风险 (无风险因子)",
            "params": {
                "elevated_risk_surgery": False,
                "ischemic_heart_disease": False,
                "congestive_heart_failure": False,
                "cerebrovascular_disease": False,
                "pre_operative_insulin_treatment": False,
                "pre_operative_creatinine": 1.0
            },
            "expected_valid": True,
            "expected_score": 0,
            "description": "所有风险因子为假，肌酐正常",
        },
        {
            "name": "单一风险因子 - 高风险手术",
            "params": {
                "elevated_risk_surgery": True,
                "ischemic_heart_disease": False,
                "congestive_heart_failure": False,
                "cerebrovascular_disease": False,
                "pre_operative_insulin_treatment": False,
                "pre_operative_creatinine": 1.5
            },
            "expected_valid": True,
            "expected_score": 1,
            "description": "仅高风险手术为真",
        },
        {
            "name": "单一风险因子 - 肌酐升高",
            "params": {
                "elevated_risk_surgery": False,
                "ischemic_heart_disease": False,
                "congestive_heart_failure": False,
                "cerebrovascular_disease": False,
                "pre_operative_insulin_treatment": False,
                "pre_operative_creatinine": 2.5
            },
            "expected_valid": True,
            "expected_score": 1,
            "description": "仅肌酐>2.0 mg/dL",
        },
        {
            "name": "多个风险因子",
            "params": {
                "elevated_risk_surgery": True,
                "ischemic_heart_disease": True,
                "congestive_heart_failure": False,
                "cerebrovascular_disease": True,
                "pre_operative_insulin_treatment": False,
                "pre_operative_creatinine": 1.8
            },
            "expected_valid": True,
            "expected_score": 3,
            "description": "3个风险因子为真",
        },
        {
            "name": "所有风险因子",
            "params": {
                "elevated_risk_surgery": True,
                "ischemic_heart_disease": True,
                "congestive_heart_failure": True,
                "cerebrovascular_disease": True,
                "pre_operative_insulin_treatment": True,
                "pre_operative_creatinine": 3.0
            },
            "expected_valid": True,
            "expected_score": 6,
            "description": "所有风险因子为真",
        },
        {
            "name": "肌酐边界值 - 正好2.0",
            "params": {
                "elevated_risk_surgery": False,
                "ischemic_heart_disease": False,
                "congestive_heart_failure": False,
                "cerebrovascular_disease": False,
                "pre_operative_insulin_treatment": False,
                "pre_operative_creatinine": 2.0
            },
            "expected_valid": True,
            "expected_score": 0,
            "description": "肌酐正好2.0 mg/dL (不应加分)",
        },
        {
            "name": "肌酐边界值 - 刚超过2.0",
            "params": {
                "elevated_risk_surgery": False,
                "ischemic_heart_disease": False,
                "congestive_heart_failure": False,
                "cerebrovascular_disease": False,
                "pre_operative_insulin_treatment": False,
                "pre_operative_creatinine": 2.1
            },
            "expected_valid": True,
            "expected_score": 1,
            "description": "肌酐2.1 mg/dL (应加分)",
        },
        {
            "name": "无效肌酐 - 负值",
            "params": {
                "elevated_risk_surgery": False,
                "ischemic_heart_disease": False,
                "congestive_heart_failure": False,
                "cerebrovascular_disease": False,
                "pre_operative_insulin_treatment": False,
                "pre_operative_creatinine": -1.0
            },
            "expected_valid": False,
            "description": "肌酐为负值 (应失败)",
        },
        {
            "name": "无效肌酐 - 过高",
            "params": {
                "elevated_risk_surgery": False,
                "ischemic_heart_disease": False,
                "congestive_heart_failure": False,
                "cerebrovascular_disease": False,
                "pre_operative_insulin_treatment": False,
                "pre_operative_creatinine": 25.0
            },
            "expected_valid": False,
            "description": "肌酐过高 (应失败)",
        },
        {
            "name": "极值测试 - 最高肌酐",
            "params": {
                "elevated_risk_surgery": True,
                "ischemic_heart_disease": False,
                "congestive_heart_failure": False,
                "cerebrovascular_disease": False,
                "pre_operative_insulin_treatment": False,
                "pre_operative_creatinine": 20.0
            },
            "expected_valid": True,
            "expected_score": 2,
            "description": "最高允许肌酐值",
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
                    "calculator_id": 17,
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
                        print(f"- 错误: 分数不匹配 (期望: {expected_score}, 实际: {actual_score})")
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
        print("Revised Cardiac Risk Index 计算器 MCP 测试")
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
        print("Revised Cardiac Risk Index 计算器测试结果")
        print("=" * 60)
        print(f"总测试数: {total_tests}")
        print(f"通过数: {total_passed}")
        print(f"失败数: {total_failed}")
        print(f"成功率: {(total_passed/total_tests*100):.1f}%")

        if total_failed == 0:
            print("\n✅ Revised Cardiac Risk Index 计算器所有测试都通过了！")
        else:
            print(f"\n❌ {total_failed} 个测试失败，请检查 Revised Cardiac Risk Index 计算器实现。")

    print_header()

    try:
        async with Client(MCP_SERVER_URL) as client:
            print_connection_status(True)
            passed, failed = await test_cardiac_risk_index_calculator(client)
            print_overall_results(passed, failed)

    except Exception as e:
        print_connection_status(False, str(e))
        import traceback

        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("✅ Revised Cardiac Risk Index 计算器测试完成")


if __name__ == "__main__":
    asyncio.run(main())