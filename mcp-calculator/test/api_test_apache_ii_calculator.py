import asyncio
import json
import sys
import os
from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVER_URL


async def test_apache_ii_calculator(client):
    """测试 APACHE II 计算器的各种功能和参数验证"""

    def print_header():
        print("\n" + "=" * 60)
        print("APACHE II 评分计算器测试套件")
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
        apache_ii_value = data.get("value", "N/A")
        unit = data.get("unit", "")
        explanation = data.get("explanation", "")
        metadata = data.get("metadata", {})
        warnings = data.get("warnings", [])

        # 基本结果
        print(f"- APACHE II 评分: {apache_ii_value} {unit}")

        # 风险分类
        if metadata:
            risk_category = metadata.get("risk_category", "N/A")
            mortality_risk = metadata.get("mortality_risk", "N/A")
            print(f"- 风险分类: {risk_category}")
            print(f"- 预计死亡率: {mortality_risk}")

        # 警告信息
        if warnings:
            for warning in warnings:
                print(f"- ⚠️  警告: {warning}")

        # 详细解释（截取前几行显示）
        if explanation:
            lines = explanation.split('\n')[:5]  # 显示前5行
            print(f"- 解释: {lines[0]}")
            if len(lines) > 1:
                print(f"  (... 共 {len(explanation.split())} 行详细计算)")

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
            print("\n✅ 所有测试都通过了！APACHE II 计算器工作正常。")
        else:
            print(f"\n❌ {failed} 个测试失败，请检查实现。")

        print("\n测试覆盖范围:")
        features = [
            "低风险患者评估",
            "中风险患者评估", 
            "高风险患者评估",
            "极高风险患者评估",
            "FiO2 < 50% (使用 PaO2)",
            "FiO2 >= 50% (使用 A-a 梯度)",
            "急性肾功能衰竭",
            "慢性肾功能衰竭",
            "器官衰竭/免疫缺陷史",
            "手术类型分类",
            "参数验证",
            "边界值测试",
        ]
        for feature in features:
            print(f"  - {feature}")

    # Test statistics
    total_tests = 0
    passed_tests = 0

    # Test cases covering different risk levels and edge cases
    test_cases = [
        {
            "name": "Low risk patient",
            "params": {
                "age": 35,
                "temperature": 37.0,
                "systolic_bp": 120,
                "diastolic_bp": 80,
                "heart_rate": 75,
                "respiratory_rate": 16,
                "fio2": 21,
                "pao2": 95,
                "ph": 7.4,
                "sodium": 140,
                "potassium": 4.0,
                "creatinine": 1.0,
                "hematocrit": 40,
                "wbc": 8.0,
                "gcs": 15,
                "acute_renal_failure": False,
                "chronic_renal_failure": False,
                "organ_failure_immunocompromise": False,
                "surgery_type": "none"
            },
            "expected_valid": True,
            "description": "低风险患者 - 正常生理参数",
        },
        {
            "name": "Moderate risk patient",
            "params": {
                "age": 65,
                "temperature": 38.5,
                "systolic_bp": 90,
                "diastolic_bp": 60,
                "heart_rate": 110,
                "respiratory_rate": 26,
                "fio2": 40,
                "pao2": 65,
                "ph": 7.3,
                "sodium": 135,
                "potassium": 3.2,
                "creatinine": 1.8,
                "hematocrit": 32,
                "wbc": 15.0,
                "gcs": 13,
                "acute_renal_failure": False,
                "chronic_renal_failure": False,
                "organ_failure_immunocompromise": False,
                "surgery_type": "none"
            },
            "expected_valid": True,
            "description": "中风险患者 - 轻度异常生理参数",
        },
        {
            "name": "High risk patient",
            "params": {
                "age": 75,
                "temperature": 35.0,
                "systolic_bp": 70,
                "diastolic_bp": 45,
                "heart_rate": 150,
                "respiratory_rate": 35,
                "fio2": 60,
                "aa_gradient": 350,
                "ph": 7.2,
                "sodium": 125,
                "potassium": 5.8,
                "creatinine": 2.5,
                "hematocrit": 25,
                "wbc": 25.0,
                "gcs": 10,
                "acute_renal_failure": True,
                "chronic_renal_failure": False,
                "organ_failure_immunocompromise": True,
                "surgery_type": "emergency"
            },
            "expected_valid": True,
            "description": "高风险患者 - 严重异常生理参数",
        },
        {
            "name": "Very high risk patient",
            "params": {
                "age": 85,
                "temperature": 32.0,
                "systolic_bp": 60,
                "diastolic_bp": 35,
                "heart_rate": 180,
                "respiratory_rate": 50,
                "fio2": 80,
                "aa_gradient": 500,
                "ph": 7.1,
                "sodium": 115,
                "potassium": 6.5,
                "creatinine": 4.0,
                "hematocrit": 18,
                "wbc": 35.0,
                "gcs": 6,
                "acute_renal_failure": True,
                "chronic_renal_failure": False,
                "organ_failure_immunocompromise": True,
                "surgery_type": "emergency"
            },
            "expected_valid": True,
            "description": "极高风险患者 - 极度异常生理参数",
        },
        {
            "name": "Patient with chronic renal failure",
            "params": {
                "age": 60,
                "temperature": 37.5,
                "systolic_bp": 100,
                "diastolic_bp": 70,
                "heart_rate": 85,
                "respiratory_rate": 20,
                "fio2": 30,
                "pao2": 80,
                "ph": 7.35,
                "sodium": 138,
                "potassium": 4.5,
                "creatinine": 3.0,
                "hematocrit": 35,
                "wbc": 10.0,
                "gcs": 14,
                "acute_renal_failure": False,
                "chronic_renal_failure": True,
                "organ_failure_immunocompromise": True,
                "surgery_type": "elective"
            },
            "expected_valid": True,
            "description": "慢性肾功能衰竭患者",
        },
        {
            "name": "Patient requiring high FiO2",
            "params": {
                "age": 55,
                "temperature": 39.0,
                "systolic_bp": 95,
                "diastolic_bp": 65,
                "heart_rate": 120,
                "respiratory_rate": 30,
                "fio2": 70,
                "aa_gradient": 300,
                "ph": 7.25,
                "sodium": 130,
                "potassium": 5.2,
                "creatinine": 1.5,
                "hematocrit": 30,
                "wbc": 18.0,
                "gcs": 12,
                "acute_renal_failure": False,
                "chronic_renal_failure": False,
                "organ_failure_immunocompromise": False,
                "surgery_type": "none"
            },
            "expected_valid": True,
            "description": "高氧浓度需求患者 (FiO2 >= 50%)",
        },
        {
            "name": "Invalid: Missing PaO2 for low FiO2",
            "params": {
                "age": 45,
                "temperature": 37.0,
                "systolic_bp": 120,
                "diastolic_bp": 80,
                "heart_rate": 75,
                "respiratory_rate": 16,
                "fio2": 30,
                "ph": 7.4,
                "sodium": 140,
                "potassium": 4.0,
                "creatinine": 1.0,
                "hematocrit": 40,
                "wbc": 8.0,
                "gcs": 15
            },
            "expected_valid": False,
            "description": "无效：FiO2 < 50% 但缺少 PaO2 参数",
        },
        {
            "name": "Invalid: Missing A-a gradient for high FiO2",
            "params": {
                "age": 45,
                "temperature": 37.0,
                "systolic_bp": 120,
                "diastolic_bp": 80,
                "heart_rate": 75,
                "respiratory_rate": 16,
                "fio2": 60,
                "ph": 7.4,
                "sodium": 140,
                "potassium": 4.0,
                "creatinine": 1.0,
                "hematocrit": 40,
                "wbc": 8.0,
                "gcs": 15
            },
            "expected_valid": False,
            "description": "无效：FiO2 >= 50% 但缺少 A-a 梯度参数",
        },
        {
            "name": "Invalid: Both acute and chronic renal failure",
            "params": {
                "age": 60,
                "temperature": 37.0,
                "systolic_bp": 120,
                "diastolic_bp": 80,
                "heart_rate": 75,
                "respiratory_rate": 16,
                "fio2": 25,
                "pao2": 90,
                "ph": 7.4,
                "sodium": 140,
                "potassium": 4.0,
                "creatinine": 2.0,
                "hematocrit": 40,
                "wbc": 8.0,
                "gcs": 15,
                "acute_renal_failure": True,
                "chronic_renal_failure": True
            },
            "expected_valid": False,
            "description": "无效：同时有急性和慢性肾功能衰竭",
        },
        {
            "name": "Invalid: Out of range parameters",
            "params": {
                "age": 150,  # 超出范围
                "temperature": 50,  # 超出范围
                "systolic_bp": 400,  # 超出范围
                "diastolic_bp": 80,
                "heart_rate": 75,
                "respiratory_rate": 16,
                "fio2": 25,
                "pao2": 90,
                "ph": 7.4,
                "sodium": 140,
                "potassium": 4.0,
                "creatinine": 1.0,
                "hematocrit": 40,
                "wbc": 8.0,
                "gcs": 15
            },
            "expected_valid": False,
            "description": "无效：参数超出正常范围",
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
                    "calculator_id": 28,  # APACHE II calculator ID
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
        print("APACHE II 计算器 MCP 测试")
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
        print("APACHE II 计算器测试结果")
        print("=" * 60)
        print(f"总测试数: {total_tests}")
        print(f"通过数: {total_passed}")
        print(f"失败数: {total_failed}")
        print(f"成功率: {(total_passed/total_tests*100):.1f}%")

        if total_failed == 0:
            print("\n✅ APACHE II 计算器所有测试都通过了！")
        else:
            print(f"\n❌ {total_failed} 个测试失败，请检查 APACHE II 计算器实现。")

    print_header()

    try:
        async with Client(MCP_SERVER_URL) as client:
            print_connection_status(True)
            passed, failed = await test_apache_ii_calculator(client)
            print_overall_results(passed, failed)

    except Exception as e:
        print_connection_status(False, str(e))
        import traceback

        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("✅ APACHE II 计算器测试完成")


if __name__ == "__main__":
    asyncio.run(main())