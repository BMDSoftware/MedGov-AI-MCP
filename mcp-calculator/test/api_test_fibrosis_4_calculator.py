import asyncio
import json
import sys
import os
from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVER_URL


async def test_fibrosis_4_calculator(client):
    """测试 Fibrosis-4 (FIB-4) 指数计算器的各种功能"""

    def print_header():
        print("\n" + "=" * 60)
        print("Fibrosis-4 (FIB-4) 指数计算器测试套件")
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
        fib4_value = data.get("value", "N/A")
        unit = data.get("unit", "")
        explanation = data.get("explanation", "")
        metadata = data.get("metadata", {})
        warnings = data.get("warnings", [])

        # 基本结果
        print(f"- FIB-4 值: {fib4_value} {unit}")

        # 原始输入值
        if metadata:
            age = metadata.get("age")
            ast = metadata.get("ast")
            alt = metadata.get("alt")
            platelet_count = metadata.get("platelet_count")
            risk_assessment = metadata.get("risk_assessment", "N/A")

            if age:
                print(f"- 年龄: {age} years")
            if ast:
                print(f"- AST: {ast} U/L")
            if alt:
                print(f"- ALT: {alt} U/L")
            if platelet_count:
                print(f"- 血小板计数: {platelet_count} ×10⁹/L")
            if risk_assessment:
                print(f"- 风险评估: {risk_assessment}")

        # 警告信息
        if warnings:
            for warning in warnings:
                print(f"- ⚠️  警告: {warning}")

        # 详细解释（截取前几行显示）
        if explanation:
            print(f"- 解释: {explanation.strip()[:200]}...")

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
            print("\n✅ 所有测试都通过了！Fibrosis-4 计算器工作正常。")
        else:
            print(f"\n❌ {failed} 个测试失败，请检查实现。")

        print("\n测试覆盖范围:")
        features = [
            "年龄验证 (18-120岁)",
            "AST/ALT 酶值验证",
            "血小板计数验证",
            "FIB-4 计算",
            "风险评估分类",
            "参数验证",
            "错误处理",
            "边界测试",
        ]
        for feature in features:
            print(f"  - {feature}")

    # Test statistics
    total_tests = 0
    passed_tests = 0

    # 基于真实医学数据的测试用例 (来自 data/medcalc_train_testcase_s20.jsonl)
    test_cases = [
        {
            "name": "Standard case 1",
            "params": {"age": "68", "ast": "42.0", "alt": "20.0", "platelet_count": "172"},
            "expected_valid": True,
            "expected_result": 3.713,
            "description": "标准计算 (68岁, AST:42, ALT:20, 血小板:172×10⁹/L)",
        },
        {
            "name": "Low risk case",
            "params": {"age": "35", "ast": "13.0", "alt": "16.0", "platelet_count": "261"},
            "expected_valid": True,
            "expected_result": 0.436,
            "description": "低风险病例 (35岁, AST:13, ALT:16, 血小板:261×10⁹/L)",
        },
        {
            "name": "High risk case",
            "params": {"age": "70", "ast": "55.0", "alt": "42.0", "platelet_count": "137"},
            "expected_valid": True,
            "expected_result": 4.336,
            "description": "高风险病例 (70岁, AST:55, ALT:42, 血小板:137×10⁹/L)",
        },
        {
            "name": "Intermediate case",
            "params": {"age": "49", "ast": "30.0", "alt": "29.0", "platelet_count": "112"},
            "expected_valid": True,
            "expected_result": 2.437,
            "description": "中等风险病例 (49岁, AST:30, ALT:29, 血小板:112×10⁹/L)",
        },
        {
            "name": "Young adult case",
            "params": {"age": "31", "ast": "157.0", "alt": "199.0", "platelet_count": "309"},
            "expected_valid": True,
            "expected_result": 1.117,
            "description": "年轻成人病例 (31岁, AST:157, ALT:199, 血小板:309×10⁹/L)",
        },
        {
            "name": "Invalid age (too young)",
            "params": {"age": "16", "ast": "42.0", "alt": "20.0", "platelet_count": "172"},
            "expected_valid": False,
            "description": "无效年龄（太年轻）",
        },
        {
            "name": "Invalid age (too old)",
            "params": {"age": "130", "ast": "42.0", "alt": "20.0", "platelet_count": "172"},
            "expected_valid": False,
            "description": "无效年龄（过大）",
        },
        {
            "name": "Invalid AST (too low)",
            "params": {"age": "68", "ast": "2.0", "alt": "20.0", "platelet_count": "172"},
            "expected_valid": False,
            "description": "无效AST（过低）",
        },
        {
            "name": "Invalid ALT (too high)",
            "params": {"age": "68", "ast": "42.0", "alt": "1200.0", "platelet_count": "172"},
            "expected_valid": False,
            "description": "无效ALT（过高）",
        },
        {
            "name": "Invalid platelet count (too low)",
            "params": {"age": "68", "ast": "42.0", "alt": "20.0", "platelet_count": "5"},
            "expected_valid": False,
            "description": "无效血小板计数（过低）",
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
                    "calculator_id": 19,
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
                
                # 检查计算结果是否接近预期值（如果有预期结果）
                if "expected_result" in test_case:
                    actual_value = data.get("value")
                    expected_value = test_case["expected_result"]
                    if actual_value is not None:
                        # 允许5%的误差
                        tolerance = abs(expected_value * 0.05)
                        if abs(actual_value - expected_value) > tolerance:
                            print(f"- 错误: 计算结果不匹配 (期望: {expected_value:.3f}, 实际: {actual_value:.3f})")
                            test_passed = False
                        else:
                            print(f"- ✅ 计算结果匹配 (期望: {expected_value:.3f}, 实际: {actual_value:.3f})")
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
        print("Fibrosis-4 (FIB-4) 指数计算器 MCP 测试")
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
        print("Fibrosis-4 指数计算器测试结果")
        print("=" * 60)
        print(f"总测试数: {total_tests}")
        print(f"通过数: {total_passed}")
        print(f"失败数: {total_failed}")
        print(f"成功率: {(total_passed/total_tests*100):.1f}%")

        if total_failed == 0:
            print("\n✅ Fibrosis-4 指数计算器所有测试都通过了！")
        else:
            print(f"\n❌ {total_failed} 个测试失败，请检查 Fibrosis-4 指数计算器实现。")

    print_header()

    try:
        async with Client(MCP_SERVER_URL) as client:
            print_connection_status(True)
            passed, failed = await test_fibrosis_4_calculator(client)
            print_overall_results(passed, failed)

    except Exception as e:
        print_connection_status(False, str(e))
        import traceback

        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("✅ Fibrosis-4 指数计算器测试完成")


if __name__ == "__main__":
    asyncio.run(main())