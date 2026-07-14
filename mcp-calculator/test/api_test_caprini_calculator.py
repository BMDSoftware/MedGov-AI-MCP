import asyncio
import json
import sys
import os
from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVER_URL


async def test_caprini_calculator(client):
    """测试 Caprini 分数计算器的各种功能"""

    def print_header():
        print("\n" + "=" * 60)
        print("Caprini Score 计算器测试套件")
        print("=" * 60)

    def print_test_case(i, test_case):
        print(f"\n测试 {i:2d} | {test_case['name']}")
        print(f"- {test_case['description']}")
        print(f"- 输入参数: {test_case['params']}")

    def print_calculation_result(data):
        """打印完整的计算结果"""
        value = data.get("value", "N/A")
        unit = data.get("unit", "")
        explanation = data.get("explanation", "")
        metadata = data.get("metadata", {})
        warnings = data.get("warnings", [])

        # 基本结果
        print(f"- Caprini Score: {value} {unit}")

        # 风险分层信息
        if metadata:
            risk_level = metadata.get("risk_level", "N/A")
            vte_risk = metadata.get("vte_risk", "N/A") 
            recommendation = metadata.get("recommendation", "N/A")
            
            print(f"- 风险等级: {risk_level}")
            print(f"- VTE 风险: {vte_risk}")
            print(f"- 建议: {recommendation}")

        # 警告信息
        if warnings:
            for warning in warnings:
                print(f"- ⚠️  警告: {warning}")

        # 详细解释（截取前几行显示）
        if explanation:
            lines = explanation.split('\n')[:5]  # 只显示前5行
            print(f"- 解释摘要: {lines[0] if lines else 'N/A'}")

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
            print("\n✅ 所有测试都通过了！Caprini 计算器工作正常。")
        else:
            print(f"\n❌ {failed} 个测试失败，请检查实现。")

        print("\n测试覆盖范围:")
        features = [
            "年龄分组评分 (≤40, 41-60, 61-74, ≥75)",
            "性别评分",
            "手术类型评分",
            "近期疾病和外伤",
            "静脉疾病和血栓史",
            "活动能力评估",
            "BMI 评分",
            "参数验证",
            "风险分层",
            "预防建议"
        ]
        for feature in features:
            print(f"  - {feature}")

    # Test statistics
    total_tests = 0
    passed_tests = 0

    # Test cases - 基于Caprini评分系统的各种场景
    test_cases = [
        {
            "name": "Low risk young male",
            "params": {
                "age": 30,
                "sex": "Male",
                "bmi": 22.5,
                "surgery_type": "none",
                "mobility": "normal"
            },
            "expected_valid": True,
            "expected_score": 0,  # Age: 0, Male: 0, BMI<25: 0
            "description": "低风险年轻男性，无手术史"
        },
        {
            "name": "Moderate risk female with minor surgery",
            "params": {
                "age": 45,
                "sex": "Female", 
                "bmi": 28.0,
                "surgery_type": "minor",
                "mobility": "normal"
            },
            "expected_valid": True,
            "expected_score": 5,  # Age(41-60): 1, Female: 1, BMI≥25: 2, Minor surgery: 1 = 5
            "description": "中等风险女性，有小手术"
        },
        {
            "name": "High risk elderly with major surgery",
            "params": {
                "age": 80,
                "sex": "Female",
                "bmi": 30.0,
                "surgery_type": "major",
                "malignancy": True,
                "previous_dvt": True,
                "mobility": "bed_rest"
            },
            "expected_valid": True,
            "expected_score": 14,  # Age(≥75): 3, Female: 1, BMI≥25: 2, Major surgery: 2, Malignancy: 2, Previous DVT: 3, Bed rest: 1 = 14
            "description": "高风险老年患者，多个危险因素"
        },
        {
            "name": "Patient with multiple thrombophilia",
            "params": {
                "age": 55,
                "sex": "Female",
                "bmi": 32.0,
                "positive_factor_v": True,
                "positive_prothrombin": True,
                "family_history_thrombosis": True,
                "varicose_veins": True
            },
            "expected_valid": True,
            "expected_score": 14,  # Age: 1, Female: 1, BMI: 2, Factor V: 3, Prothrombin: 3, Family history: 3, Varicose veins: 1 = 14
            "description": "多种血栓形成倾向患者"
        },
        {
            "name": "Post-surgical with complications",
            "params": {
                "age": 65,
                "sex": "Male",
                "bmi": 26.5,
                "surgery_type": "elective_major_lower_extremity_arthroplasty",
                "chf": True,
                "pneumonia": True,
                "current_central_venous": True
            },
            "expected_valid": True,
            "expected_score": 13,  # Age: 2, Male: 0, BMI: 2, Elective major LE: 5, CHF: 1, Pneumonia: 1, Central venous: 2 = 13
            "description": "术后并发症患者"
        },
        {
            "name": "Trauma patient with immobilization", 
            "params": {
                "age": 40,
                "sex": "Male",
                "bmi": 24.0,
                "multiple_trauma": True,
                "hip_pelvis_leg_fracture": True,
                "immobilizing_plaster_cast": True,
                "mobility": "confined_bed_72h"
            },
            "expected_valid": True,
            "expected_score": 14,  # Age: 0, Male: 0, BMI: 0, Multiple trauma: 5, Hip fracture: 5, Plaster cast: 2, Confined bed: 2 = 14
            "description": "外伤患者伴制动"
        },
        {
            "name": "Invalid age (negative)",
            "params": {
                "age": -5,
                "sex": "Male",
                "bmi": 25.0
            },
            "expected_valid": False,
            "description": "无效年龄（负数）"
        },
        {
            "name": "Invalid BMI (too high)",
            "params": {
                "age": 50,
                "sex": "Female", 
                "bmi": 100.0
            },
            "expected_valid": False,
            "description": "无效BMI（过高）"
        },
        {
            "name": "Extreme high risk scenario",
            "params": {
                "age": 85,
                "sex": "Female",
                "bmi": 35.0,
                "surgery_type": "elective_major_lower_extremity_arthroplasty",
                "stroke": True,
                "acute_spinal_cord_injury": True,
                "previous_pe": True,
                "malignancy": True,
                "mobility": "confined_bed_72h",
                "copd": True
            },
            "expected_valid": True,
            "expected_score": 29,  # Age: 3, Female: 1, BMI: 2, Surgery: 5, Stroke: 5, Spinal injury: 5, Previous PE: 3, Malignancy: 2, Confined bed: 2, COPD: 1
            "description": "极高风险场景"
        }
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
                    "calculator_id": 36,
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
                    if actual_score != test_case["expected_score"]:
                        print(f"- 错误: 预期分数 {test_case['expected_score']}, 实际分数 {actual_score}")
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
        print("Caprini Score 计算器 MCP 测试")
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
        print("Caprini Score 计算器测试结果")
        print("=" * 60)
        print(f"总测试数: {total_tests}")
        print(f"通过数: {total_passed}")
        print(f"失败数: {total_failed}")
        print(f"成功率: {(total_passed/total_tests*100):.1f}%")

        if total_failed == 0:
            print("\n✅ Caprini Score 计算器所有测试都通过了！")
        else:
            print(f"\n❌ {total_failed} 个测试失败，请检查 Caprini Score 计算器实现。")

    print_header()

    try:
        async with Client(MCP_SERVER_URL) as client:
            print_connection_status(True)
            passed, failed = await test_caprini_calculator(client)
            print_overall_results(passed, failed)

    except Exception as e:
        print_connection_status(False, str(e))
        import traceback
        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("✅ Caprini Score 计算器测试完成")


if __name__ == "__main__":
    asyncio.run(main())