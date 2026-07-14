import asyncio
import json
import sys
import os
from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVER_URL


async def test_glasgow_bleeding_score_calculator(client):
    """测试 Glasgow Bleeding Score 计算器的各种功能"""

    def print_header():
        print("\n" + "=" * 60)
        print("Glasgow Bleeding Score 计算器测试套件")
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
        print(f"- Glasgow Bleeding Score: {score_value} {unit}")

        # 输入参数
        if metadata:
            hemoglobin = metadata.get("hemoglobin")
            bun = metadata.get("bun")
            systolic_bp = metadata.get("systolic_bp")
            sex = metadata.get("sex")
            heart_rate = metadata.get("heart_rate")
            melena_present = metadata.get("melena_present", False)
            syncope = metadata.get("syncope", False)
            hepatic_disease_history = metadata.get("hepatic_disease_history", False)
            cardiac_failure = metadata.get("cardiac_failure", False)

            print(f"- 血红蛋白: {hemoglobin} g/dL")
            print(f"- BUN: {bun} mg/dL")
            print(f"- 收缩压: {systolic_bp} mmHg")
            print(f"- 性别: {sex}")
            print(f"- 心率: {heart_rate} bpm")
            print(f"- 黑便: {'是' if melena_present else '否'}")
            print(f"- 晕厥: {'是' if syncope else '否'}")
            print(f"- 肝病史: {'是' if hepatic_disease_history else '否'}")
            print(f"- 心衰: {'是' if cardiac_failure else '否'}")

        # 警告信息
        if warnings:
            for warning in warnings:
                print(f"- ⚠️  警告: {warning}")

        # 详细解释（截取前几行显示）
        if explanation:
            lines = explanation.split('\n')[:3]
            print(f"- 解释: {' '.join(lines)}")

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
            print("\n✅ 所有测试都通过了！Glasgow Bleeding Score 计算器工作正常。")
        else:
            print(f"\n❌ {failed} 个测试失败，请检查实现。")

        print("\n测试覆盖范围:")
        features = [
            "血红蛋白水平计分",
            "BUN水平计分",
            "血压计分",
            "心率计分",
            "性别差异化计分",
            "临床症状计分（黑便、晕厥、肝病史、心衰）",
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
            "name": "Normal male patient",
            "params": {
                "hemoglobin": 14.0,
                "bun": 15.0,
                "sys_bp": 120,
                "sex": "Male",
                "heart_rate": 70,
                "melena_present": False,
                "syncope": False,
                "hepatic_disease_history": False,
                "cardiac_failure": False
            },
            "expected_valid": True,
            "expected_score": 0,
            "description": "正常男性患者（无风险因素）",
        },
        {
            "name": "High risk male patient",
            "params": {
                "hemoglobin": 9.5,
                "bun": 75.0,
                "sys_bp": 85,
                "sex": "Male",
                "heart_rate": 110,
                "melena_present": True,
                "syncope": True,
                "hepatic_disease_history": True,
                "cardiac_failure": True
            },
            "expected_valid": True,
            "expected_score": 23,  # 6(Hb)+6(BUN)+3(BP)+1(HR)+1(melena)+2(syncope)+2(hepatic)+2(cardiac) = 23
            "description": "高风险男性患者（多重风险因素）",
        },
        {
            "name": "Normal female patient",
            "params": {
                "hemoglobin": 13.0,
                "bun": 12.0,
                "sys_bp": 115,
                "sex": "Female",
                "heart_rate": 75,
                "melena_present": False,
                "syncope": False,
                "hepatic_disease_history": False,
                "cardiac_failure": False
            },
            "expected_valid": True,
            "expected_score": 0,
            "description": "正常女性患者（无风险因素）",
        },
        {
            "name": "Moderate risk female patient",
            "params": {
                "hemoglobin": 11.0,
                "bun": 25.0,
                "sys_bp": 95,
                "sex": "Female",
                "heart_rate": 90,
                "melena_present": True,
                "syncope": False,
                "hepatic_disease_history": False,
                "cardiac_failure": False
            },
            "expected_valid": True,
            "expected_score": 7,  # 1+3+2+1 = 7
            "description": "中等风险女性患者",
        },
        {
            "name": "Low hemoglobin male",
            "params": {
                "hemoglobin": 11.5,
                "bun": 20.0,
                "sys_bp": 105,
                "sex": "Male",
                "heart_rate": 85,
            },
            "expected_valid": True,
            "expected_score": 6,  # 3(Hb: 10<=11.5<12) + 2(BUN: 18.2<=20<22.4) + 1(BP: 100<=105<110) = 6
            "description": "血红蛋白偏低的男性患者",
        },
        {
            "name": "Very low hemoglobin female",
            "params": {
                "hemoglobin": 8.5,
                "bun": 15.0,
                "sys_bp": 110,
                "sex": "Female",
                "heart_rate": 95,
            },
            "expected_valid": True,
            "expected_score": 6,  # 6 = 6
            "description": "血红蛋白极低的女性患者",
        },
        {
            "name": "Invalid hemoglobin (too low)",
            "params": {
                "hemoglobin": 2.0,
                "bun": 15.0,
                "sys_bp": 110,
                "sex": "Male",
                "heart_rate": 75,
            },
            "expected_valid": False,
            "description": "无效血红蛋白（过低）",
        },
        {
            "name": "Invalid BUN (too high)",
            "params": {
                "hemoglobin": 14.0,
                "bun": 200.0,
                "sys_bp": 110,
                "sex": "Male",
                "heart_rate": 75,
            },
            "expected_valid": False,
            "description": "无效BUN（过高）",
        },
        {
            "name": "Invalid blood pressure (too low)",
            "params": {
                "hemoglobin": 14.0,
                "bun": 15.0,
                "sys_bp": 50,
                "sex": "Male",
                "heart_rate": 75,
            },
            "expected_valid": False,
            "description": "无效血压（过低）",
        },
        {
            "name": "Invalid heart rate (too high)",
            "params": {
                "hemoglobin": 14.0,
                "bun": 15.0,
                "sys_bp": 110,
                "sex": "Male",
                "heart_rate": 250,
            },
            "expected_valid": False,
            "description": "无效心率（过高）",
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
                    "calculator_id": 27,
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
                        print(f"- 错误: 预期分数 {test_case['expected_score']}，实际分数 {actual_score}")
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
        print("Glasgow Bleeding Score 计算器 MCP 测试")
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
        print("Glasgow Bleeding Score 计算器测试结果")
        print("=" * 60)
        print(f"总测试数: {total_tests}")
        print(f"通过数: {total_passed}")
        print(f"失败数: {total_failed}")
        print(f"成功率: {(total_passed/total_tests*100):.1f}%")

        if total_failed == 0:
            print("\n✅ Glasgow Bleeding Score 计算器所有测试都通过了！")
        else:
            print(f"\n❌ {total_failed} 个测试失败，请检查 Glasgow Bleeding Score 计算器实现。")

    print_header()

    try:
        async with Client(MCP_SERVER_URL) as client:
            print_connection_status(True)
            passed, failed = await test_glasgow_bleeding_score_calculator(client)
            print_overall_results(passed, failed)

    except Exception as e:
        print_connection_status(False, str(e))
        import traceback

        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("✅ Glasgow Bleeding Score 计算器测试完成")


if __name__ == "__main__":
    asyncio.run(main())