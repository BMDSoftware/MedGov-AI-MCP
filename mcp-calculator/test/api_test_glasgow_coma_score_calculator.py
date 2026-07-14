import asyncio
import json
import sys
import os
from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVER_URL


async def test_glasgow_coma_score_calculator(client):
    """测试格拉斯哥昏迷评分计算器的各种功能"""

    def print_header():
        print("\n" + "=" * 60)
        print("Glasgow Coma Score 计算器测试套件")
        print("=" * 60)

    def print_test_case(i, test_case):
        print(f"\n测试 {i:2d} | {test_case['name']}")
        print(f"- {test_case['description']}")
        print(f"- 输入参数: {test_case['params']}")

    def print_calculation_result(data):
        """打印完整的计算结果"""
        gcs_value = data.get("value", "N/A")
        unit = data.get("unit", "")
        explanation = data.get("explanation", "")
        metadata = data.get("metadata", {})
        warnings = data.get("warnings", [])

        # 基本结果
        print(f"- GCS 评分: {gcs_value} {unit}")

        # 详细信息
        if metadata:
            eye_response = metadata.get("eye_response", "N/A")
            verbal_response = metadata.get("verbal_response", "N/A")
            motor_response = metadata.get("motor_response", "N/A")
            eye_score = metadata.get("eye_score", "N/A")
            verbal_score = metadata.get("verbal_score", "N/A")
            motor_score = metadata.get("motor_score", "N/A")
            severity = metadata.get("severity", "N/A")

            print(f"- 眼部反应: {eye_response} (评分: {eye_score})")
            print(f"- 言语反应: {verbal_response} (评分: {verbal_score})")
            print(f"- 运动反应: {motor_response} (评分: {motor_score})")
            print(f"- 严重程度: {severity}")

        # 警告信息
        if warnings:
            for warning in warnings:
                print(f"- ⚠️  警告: {warning}")

        # 解释（截取前几行显示）
        if explanation:
            explanation_lines = explanation.strip().split('\n')[:3]
            print(f"- 解释: {' '.join(explanation_lines)[:200]}...")

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
            print("\n✅ 所有测试都通过了！Glasgow Coma Score 计算器工作正常。")
        else:
            print(f"\n❌ {failed} 个测试失败，请检查实现。")

        print("\n测试覆盖范围:")
        features = [
            "眼部反应评分 (4种状态)",
            "言语反应评分 (6种状态)",
            "运动反应评分 (6种状态)",
            "总评分计算",
            "严重程度分类",
            "不可测试情况处理",
            "参数验证",
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
            "name": "Normal consciousness (highest scores)",
            "params": {
                "best_eye_response": "eyes open spontaneously",
                "best_verbal_response": "oriented",
                "best_motor_response": "obeys commands"
            },
            "expected_valid": True,
            "expected_score": 15,
            "description": "正常意识状态（最高评分：4+5+6=15）",
        },
        {
            "name": "Moderate impairment",
            "params": {
                "best_eye_response": "eye opening to verbal command",
                "best_verbal_response": "confused",
                "best_motor_response": "localizes pain"
            },
            "expected_valid": True,
            "expected_score": 12,
            "description": "中等程度损伤（3+4+5=12）",
        },
        {
            "name": "Severe impairment",
            "params": {
                "best_eye_response": "eye opening to pain",
                "best_verbal_response": "inappropriate words",
                "best_motor_response": "withdrawal from pain"
            },
            "expected_valid": True,
            "expected_score": 9,
            "description": "严重损伤（2+3+4=9）",
        },
        {
            "name": "Critical state (lowest scores)",
            "params": {
                "best_eye_response": "no eye opening",
                "best_verbal_response": "no verbal response",
                "best_motor_response": "no motor response"
            },
            "expected_valid": True,
            "expected_score": 3,
            "description": "危重状态（最低评分：1+1+1=3）",
        },
        {
            "name": "Eye not testable",
            "params": {
                "best_eye_response": "not testable",
                "best_verbal_response": "oriented",
                "best_motor_response": "obeys commands"
            },
            "expected_valid": True,
            "expected_score": 15,
            "description": "眼部反应不可测试（假设最佳：4+5+6=15）",
        },
        {
            "name": "Verbal not testable",
            "params": {
                "best_eye_response": "eyes open spontaneously",
                "best_verbal_response": "not testable",
                "best_motor_response": "obeys commands"
            },
            "expected_valid": True,
            "expected_score": 14,
            "description": "言语反应不可测试（假设较好：4+4+6=14）",
        },
        {
            "name": "Mixed responses",
            "params": {
                "best_eye_response": "eye opening to verbal command",
                "best_verbal_response": "incomprehensible sounds",
                "best_motor_response": "flexion to pain"
            },
            "expected_valid": True,
            "expected_score": 8,
            "description": "混合反应（3+2+3=8）",
        },
        {
            "name": "Missing eye response",
            "params": {
                "best_verbal_response": "oriented",
                "best_motor_response": "obeys commands"
            },
            "expected_valid": False,
            "description": "缺少眼部反应参数（应该验证失败）",
        },
        {
            "name": "Missing verbal response",
            "params": {
                "best_eye_response": "eyes open spontaneously",
                "best_motor_response": "obeys commands"
            },
            "expected_valid": False,
            "description": "缺少言语反应参数（应该验证失败）",
        },
        {
            "name": "Missing motor response",
            "params": {
                "best_eye_response": "eyes open spontaneously",
                "best_verbal_response": "oriented"
            },
            "expected_valid": False,
            "description": "缺少运动反应参数（应该验证失败）",
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
                    "calculator_id": 21,  # Glasgow Coma Score calculator ID
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
                        print(f"- 错误: 预期评分 {test_case['expected_score']}, 实际评分 {actual_score}")
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
        print("Glasgow Coma Score 计算器 MCP 测试")
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
        print("Glasgow Coma Score 计算器测试结果")
        print("=" * 60)
        print(f"总测试数: {total_tests}")
        print(f"通过数: {total_passed}")
        print(f"失败数: {total_failed}")
        print(f"成功率: {(total_passed/total_tests*100):.1f}%")

        if total_failed == 0:
            print("\n✅ Glasgow Coma Score 计算器所有测试都通过了！")
        else:
            print(f"\n❌ {total_failed} 个测试失败，请检查 Glasgow Coma Score 计算器实现。")

    print_header()

    try:
        async with Client(MCP_SERVER_URL) as client:
            print_connection_status(True)
            passed, failed = await test_glasgow_coma_score_calculator(client)
            print_overall_results(passed, failed)

    except Exception as e:
        print_connection_status(False, str(e))
        import traceback

        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("✅ Glasgow Coma Score 计算器测试完成")


if __name__ == "__main__":
    asyncio.run(main())