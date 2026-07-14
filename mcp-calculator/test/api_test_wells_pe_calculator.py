import asyncio
import os
import sys
from typing import Dict, Any

from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVER_URL  # noqa: E402


async def test_wells_pe_calculator(client: Client):
    """测试 Wells PE 计算器的各种功能和参数组合"""

    def print_header():
        print("\n" + "=" * 60)
        print("Wells PE 计算器测试套件")
        print("=" * 60)

    def print_test_case(i, test_case):
        print(f"\n测试 {i:2d} | {test_case['name']}")
        print(f"- {test_case['description']}")
        print(f"- 输入参数: {test_case['params']}")

    def print_calculation_result(data):
        """打印完整的计算结果"""
        wells_value = data.get("value", "N/A")
        unit = data.get("unit", "")
        explanation = data.get("explanation", "")
        metadata = data.get("metadata", {})
        warnings = data.get("warnings", [])

        # 基本结果
        print(f"- Wells PE 评分: {wells_value} {unit}")

        # 元数据信息
        if metadata:
            heart_rate = metadata.get("heart_rate")
            risk_category = metadata.get("risk_category")

            if heart_rate is not None:
                print(f"- 心率: {heart_rate} bpm")
            if risk_category:
                print(f"- 风险分层: {risk_category}")

            # 显示阳性标准
            positive_criteria = []
            if metadata.get("clinical_dvt"):
                positive_criteria.append("临床DVT症状")
            if metadata.get("pe_number_one"):
                positive_criteria.append("PE为第一诊断")
            if metadata.get("heart_rate_over_100"):
                positive_criteria.append("心率>100")
            if metadata.get("immobilization_surgery"):
                positive_criteria.append("制动/手术史")
            if metadata.get("previous_pe_dvt"):
                positive_criteria.append("既往PE/DVT史")
            if metadata.get("hemoptysis"):
                positive_criteria.append("咯血")
            if metadata.get("malignancy"):
                positive_criteria.append("恶性肿瘤")

            if positive_criteria:
                print(f"- 阳性标准: {', '.join(positive_criteria)}")
            else:
                print(f"- 阳性标准: 无")

        # 警告信息
        if warnings:
            for warning in warnings:
                print(f"- ⚠️  警告: {warning}")

        # 详细解释（截取显示）
        if explanation:
            print(f"- 解释: {explanation.strip()}")

    def print_validation_result(expected, actual):
        if expected == actual:
            status = "✅ 通过"
        else:
            status = "❌ 失败"
        print(f"- 验证结果: {status} (期望: {expected}, 实际: {actual})")

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
            print("\n✅ 所有测试都通过了！Wells PE 计算器工作正常。")
        else:
            print(f"\n❌ {failed} 个测试失败，请检查实现。")

        print("\n测试覆盖范围:")
        features = [
            "心率参数验证",
            "多种临床条件组合",
            "Wells PE 风险分层",
            "低/中/高风险测试",
            "边界值测试",
            "错误处理",
            "临床解释生成",
        ]
        for feature in features:
            print(f"  - {feature}")

    # Test statistics
    total_tests = 0
    passed_tests = 0

    # Test cases
    test_cases = [
        {
            "name": "Wells PE 低风险 - 健康患者",
            "params": {
                "heart_rate": 75,
                "clinical_dvt": False,
                "pe_number_one": False,
                "immobilization_for_3days": False,
                "surgery_in_past4weeks": False,
                "previous_pe": False,
                "previous_dvt": False,
                "hemoptysis": False,
                "malignancy_with_treatment": False,
            },
            "expected_value": 0.0,
            "expected_valid": True,
            "description": "心率75，无任何阳性标准，应为低风险",
        },
        {
            "name": "Wells PE 低风险 - 单项心率>100",
            "params": {
                "heart_rate": 110,
                "clinical_dvt": False,
                "pe_number_one": False,
                "immobilization_for_3days": False,
                "surgery_in_past4weeks": False,
                "previous_pe": False,
                "previous_dvt": False,
                "hemoptysis": False,
                "malignancy_with_treatment": False,
            },
            "expected_value": 1.5,
            "expected_valid": True,
            "description": "心率110，仅心率>100一项阳性 (+1.5分)",
        },
        {
            "name": "Wells PE 低风险 - 咯血+恶性肿瘤",
            "params": {
                "heart_rate": 80,
                "clinical_dvt": False,
                "pe_number_one": False,
                "immobilization_for_3days": False,
                "surgery_in_past4weeks": False,
                "previous_pe": False,
                "previous_dvt": False,
                "hemoptysis": True,
                "malignancy_with_treatment": True,
            },
            "expected_value": 2.0,
            "expected_valid": True,
            "description": "咯血(+1)+恶性肿瘤(+1) = 2分，边界低风险",
        },
        {
            "name": "Wells PE 中风险 - 既往史+制动",
            "params": {
                "heart_rate": 85,
                "clinical_dvt": False,
                "pe_number_one": False,
                "immobilization_for_3days": True,
                "surgery_in_past4weeks": False,
                "previous_pe": True,
                "previous_dvt": False,
                "hemoptysis": False,
                "malignancy_with_treatment": False,
            },
            "expected_value": 3.0,
            "expected_valid": True,
            "description": "制动(+1.5)+既往PE史(+1.5) = 3分，中风险",
        },
        {
            "name": "Wells PE 中风险 - 手术史+心率+咯血",
            "params": {
                "heart_rate": 105,
                "clinical_dvt": False,
                "pe_number_one": False,
                "immobilization_for_3days": False,
                "surgery_in_past4weeks": True,
                "previous_pe": False,
                "previous_dvt": False,
                "hemoptysis": True,
                "malignancy_with_treatment": True,
            },
            "expected_value": 5.0,
            "expected_valid": True,
            "description": "手术史(+1.5)+心率>100(+1.5)+咯血(+1)+恶性肿瘤(+1) = 5分，中风险",
        },
        {
            "name": "Wells PE 高风险边界 - 6.5分",
            "params": {
                "heart_rate": 110,
                "clinical_dvt": False,
                "pe_number_one": False,
                "immobilization_for_3days": True,
                "surgery_in_past4weeks": False,
                "previous_pe": True,
                "previous_dvt": False,
                "hemoptysis": True,
                "malignancy_with_treatment": True,
            },
            "expected_value": 6.5,
            "expected_valid": True,
            "description": "心率(+1.5)+制动(+1.5)+既往PE(+1.5)+咯血(+1)+恶性肿瘤(+1) = 6.5分，高风险边界",
        },
        {
            "name": "Wells PE 高风险 - PE第一诊断",
            "params": {
                "heart_rate": 105,
                "clinical_dvt": False,
                "pe_number_one": True,
                "immobilization_for_3days": True,
                "surgery_in_past4weeks": False,
                "previous_pe": False,
                "previous_dvt": False,
                "hemoptysis": True,
                "malignancy_with_treatment": False,
            },
            "expected_value": 7.0,
            "expected_valid": True,
            "description": "PE第一诊断(+3)+制动(+1.5)+心率>100(+1.5)+咯血(+1) = 7分，高风险",
        },
        {
            "name": "Wells PE 高风险 - 临床DVT症状",
            "params": {
                "heart_rate": 120,
                "clinical_dvt": True,
                "pe_number_one": False,
                "immobilization_for_3days": False,
                "surgery_in_past4weeks": True,
                "previous_pe": True,
                "previous_dvt": False,
                "hemoptysis": False,
                "malignancy_with_treatment": True,
            },
            "expected_value": 8.5,
            "expected_valid": True,
            "description": "临床DVT(+3)+心率>100(+1.5)+手术史(+1.5)+既往PE(+1.5)+恶性肿瘤(+1) = 8.5分，高风险",
        },
        {
            "name": "Wells PE 最高风险 - 多项阳性",
            "params": {
                "heart_rate": 125,
                "clinical_dvt": True,
                "pe_number_one": True,
                "immobilization_for_3days": True,
                "surgery_in_past4weeks": False,
                "previous_pe": True,
                "previous_dvt": False,
                "hemoptysis": True,
                "malignancy_with_treatment": True,
            },
            "expected_value": 12.5,
            "expected_valid": True,
            "description": "临床DVT(+3)+PE第一诊断(+3)+心率>100(+1.5)+制动(+1.5)+既往PE(+1.5)+咯血(+1)+恶性肿瘤(+1) = 12.5分，极高风险",
        },
        {
            "name": "参数验证 - 无效心率",
            "params": {
                "heart_rate": 25,
                "clinical_dvt": False,
                "pe_number_one": False,
                "immobilization_for_3days": False,
                "surgery_in_past4weeks": False,
                "previous_pe": False,
                "previous_dvt": False,
                "hemoptysis": False,
                "malignancy_with_treatment": False,
            },
            "expected_valid": False,
            "description": "无效心率（<30）",
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
                    "calculator_id": 8,
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
                elif "expected_value" in test_case:
                    actual_value = data.get("value")
                    expected_value = test_case["expected_value"]
                    if abs(float(actual_value) - expected_value) > 1e-6:
                        test_passed = False
                    print_validation_result(expected_value, actual_value)
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
        print("Wells PE 计算器 MCP 测试")
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
        print("Wells PE 计算器测试结果")
        print("=" * 60)
        print(f"总测试数: {total_tests}")
        print(f"通过数: {total_passed}")
        print(f"失败数: {total_failed}")
        print(f"成功率: {(total_passed/total_tests*100):.1f}%")

        if total_failed == 0:
            print("\n✅ Wells PE 计算器所有测试都通过了！")
        else:
            print(f"\n❌ {total_failed} 个测试失败，请检查 Wells PE 计算器实现。")

    print_header()

    try:
        async with Client(MCP_SERVER_URL) as client:
            print_connection_status(True)
            passed, failed = await test_wells_pe_calculator(client)
            print_overall_results(passed, failed)

    except Exception as e:
        print_connection_status(False, str(e))
        import traceback

        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("✅ Wells PE 计算器测试完成")


if __name__ == "__main__":
    asyncio.run(main())
