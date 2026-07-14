import asyncio
import json
import sys
import os
from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVER_URL


async def test_framingham_calculator(client):
    """测试 Framingham 风险评分计算器的各种功能"""

    def print_header():
        print("\n" + "=" * 60)
        print("Framingham 风险评分计算器测试套件")
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
        risk_percentage = data.get("value", "N/A")
        unit = data.get("unit", "")
        explanation = data.get("explanation", "")
        metadata = data.get("metadata", {})
        warnings = data.get("warnings", [])

        # 基本结果
        print(f"- 风险值: {risk_percentage}{unit}")

        # 元数据信息
        if metadata:
            risk_score = metadata.get("risk_score")
            risk_category = metadata.get("risk_category")
            recommendation = metadata.get("recommendation")
            risk_factors = metadata.get("risk_factors", {})

            if risk_score is not None:
                print(f"- 风险评分: {risk_score}")
            if risk_category:
                print(f"- 风险分类: {risk_category}")
            if recommendation:
                print(f"- 建议: {recommendation}")

            # 显示风险因素
            if risk_factors:
                print("- 风险因素:")
                for factor, value in risk_factors.items():
                    print(f"  • {factor}: {value}")

        # 警告信息
        if warnings:
            for warning in warnings:
                print(f"- ⚠️  警告: {warning}")

        # 解释（截取前几行显示）
        if explanation:
            lines = explanation.split('\n')[:3]
            print(f"- 解释摘要: {' '.join(lines).strip()}")

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
            print("\n✅ 所有测试都通过了！Framingham 计算器工作正常。")
        else:
            print(f"\n❌ {failed} 个测试失败，请检查实现。")

        print("\n测试覆盖范围:")
        features = [
            "男性和女性计算",
            "多种年龄范围",
            "不同胆固醇水平",
            "血压和用药状态",
            "吸烟和糖尿病状态",
            "参数验证",
            "边界测试",
            "风险分层",
        ]
        for feature in features:
            print(f"  - {feature}")

    # Test statistics
    total_tests = 0
    passed_tests = 0

    # Test cases
    test_cases = [
        {
            "name": "低风险男性",
            "params": {
                "age": 45,
                "sex": "Male",
                "total_cholesterol": 180,
                "hdl_cholesterol": 50,
                "systolic_bp": 120,
                "bp_medication": False,
                "smoker": False,
                "diabetes": False
            },
            "expected_valid": True,
            "description": "45岁男性，胆固醇正常，无其他危险因素",
        },
        {
            "name": "高风险女性",
            "params": {
                "age": 65,
                "sex": "Female",
                "total_cholesterol": 280,
                "hdl_cholesterol": 35,
                "systolic_bp": 160,
                "bp_medication": True,
                "smoker": True,
                "diabetes": True
            },
            "expected_valid": True,
            "description": "65岁女性，多个危险因素",
        },
        {
            "name": "中等风险男性",
            "params": {
                "age": 55,
                "sex": "Male",
                "total_cholesterol": 220,
                "hdl_cholesterol": 40,
                "systolic_bp": 140,
                "bp_medication": False,
                "smoker": True,
                "diabetes": False
            },
            "expected_valid": True,
            "description": "55岁男性，吸烟者，胆固醇偏高",
        },
        {
            "name": "年轻女性",
            "params": {
                "age": 35,
                "sex": "Female",
                "total_cholesterol": 160,
                "hdl_cholesterol": 60,
                "systolic_bp": 110,
                "bp_medication": False,
                "smoker": False,
                "diabetes": False
            },
            "expected_valid": True,
            "description": "35岁女性，低风险",
        },
        {
            "name": "边界年龄（最小）",
            "params": {
                "age": 30,
                "sex": "Male",
                "total_cholesterol": 200,
                "hdl_cholesterol": 45,
                "systolic_bp": 130,
                "bp_medication": False,
                "smoker": False,
                "diabetes": False
            },
            "expected_valid": True,
            "description": "30岁男性（最小年龄）",
        },
        {
            "name": "边界年龄（最大）",
            "params": {
                "age": 79,
                "sex": "Female",
                "total_cholesterol": 250,
                "hdl_cholesterol": 40,
                "systolic_bp": 150,
                "bp_medication": True,
                "smoker": False,
                "diabetes": True
            },
            "expected_valid": True,
            "description": "79岁女性（最大年龄）",
        },
        {
            "name": "无效年龄（太小）",
            "params": {
                "age": 25,
                "sex": "Male",
                "total_cholesterol": 200,
                "hdl_cholesterol": 45,
                "systolic_bp": 130,
                "bp_medication": False,
                "smoker": False,
                "diabetes": False
            },
            "expected_valid": False,
            "description": "25岁（年龄过小）",
        },
        {
            "name": "无效年龄（太大）",
            "params": {
                "age": 85,
                "sex": "Male",
                "total_cholesterol": 200,
                "hdl_cholesterol": 45,
                "systolic_bp": 130,
                "bp_medication": False,
                "smoker": False,
                "diabetes": False
            },
            "expected_valid": False,
            "description": "85岁（年龄过大）",
        },
        {
            "name": "无效胆固醇（过低）",
            "params": {
                "age": 50,
                "sex": "Male",
                "total_cholesterol": 80,
                "hdl_cholesterol": 45,
                "systolic_bp": 130,
                "bp_medication": False,
                "smoker": False,
                "diabetes": False
            },
            "expected_valid": False,
            "description": "总胆固醇过低（80 mg/dL）",
        },
        {
            "name": "无效血压（过低）",
            "params": {
                "age": 50,
                "sex": "Male",
                "total_cholesterol": 200,
                "hdl_cholesterol": 45,
                "systolic_bp": 80,
                "bp_medication": False,
                "smoker": False,
                "diabetes": False
            },
            "expected_valid": False,
            "description": "收缩压过低（80 mmHg）",
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
                    "calculator_id": 46,
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
        print("Framingham 风险评分计算器 MCP 测试")
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
        print("Framingham 计算器测试结果")
        print("=" * 60)
        print(f"总测试数: {total_tests}")
        print(f"通过数: {total_passed}")
        print(f"失败数: {total_failed}")
        print(f"成功率: {(total_passed/total_tests*100):.1f}%")

        if total_failed == 0:
            print("\n✅ Framingham 计算器所有测试都通过了！")
        else:
            print(f"\n❌ {total_failed} 个测试失败，请检查 Framingham 计算器实现。")

    print_header()

    try:
        async with Client(MCP_SERVER_URL) as client:
            print_connection_status(True)
            passed, failed = await test_framingham_calculator(client)
            print_overall_results(passed, failed)

    except Exception as e:
        print_connection_status(False, str(e))
        import traceback

        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("✅ Framingham 计算器测试完成")


if __name__ == "__main__":
    asyncio.run(main())