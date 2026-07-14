import asyncio
import os
import sys
from typing import Dict, Any

from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVER_URL


async def test_perc_calculator(client: Client):
    """测试 PERC 计算器的各种功能和参数组合"""

    def print_header():
        print("\n" + "=" * 60)
        print("PERC 计算器测试套件")
        print("=" * 60)

    def print_test_case(i, test_case):
        print(f"\n测试 {i:2d} | {test_case['name']}")
        print(f"- {test_case['description']}")
        print(f"- 输入参数: {test_case['params']}")

    def print_calculation_result(data):
        """打印完整的计算结果"""
        perc_value = data.get("value", "N/A")
        unit = data.get("unit", "")
        explanation = data.get("explanation", "")
        metadata = data.get("metadata", {})
        warnings = data.get("warnings", [])

        # 基本结果
        print(f"- PERC 标准数: {perc_value} {unit}")

        # 元数据信息
        if metadata:
            age = metadata.get("age")
            heart_rate = metadata.get("heart_rate")
            oxygen_sat = metadata.get("oxygen_saturation")

            if age is not None:
                print(f"- 年龄: {age} 岁")
            if heart_rate is not None:
                print(f"- 心率: {heart_rate} bpm")
            if oxygen_sat is not None:
                print(f"- 血氧饱和度: {oxygen_sat}%")

            # 显示阳性标准
            positive_criteria = []
            if metadata.get("unilateral_leg_swelling"):
                positive_criteria.append("单侧腿部肿胀")
            if metadata.get("hemoptysis"):
                positive_criteria.append("咯血")
            if metadata.get("recent_surgery_or_trauma"):
                positive_criteria.append("近期手术或外伤")
            if metadata.get("previous_pe"):
                positive_criteria.append("既往肺栓塞史")
            if metadata.get("previous_dvt"):
                positive_criteria.append("既往深静脉血栓史")
            if metadata.get("hormone_use"):
                positive_criteria.append("激素使用")
            if metadata.get("age_over_50"):
                positive_criteria.append("年龄>50岁")
            if metadata.get("heart_rate_over_100"):
                positive_criteria.append("心率>100")
            if metadata.get("oxygen_sat_under_95"):
                positive_criteria.append("血氧<95%")

            if positive_criteria:
                print(f"- 阳性标准: {', '.join(positive_criteria)}")
            else:
                print(f"- 阳性标准: 无")

            # 显示 PERC 规则结果
            perc_negative = metadata.get("perc_negative", False)
            print(f"- PERC 规则: {'阴性 (可排除PE)' if perc_negative else '阳性 (不能排除PE)'}")

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
            print("\n✅ 所有测试都通过了！PERC 计算器工作正常。")
        else:
            print(f"\n❌ {failed} 个测试失败，请检查实现。")

        print("\n测试覆盖范围:")
        features = [
            "年龄、心率、血氧参数验证",
            "多种布尔条件组合",
            "PERC 规则阴性/阳性判定",
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
            "name": "PERC阴性 - 年轻健康患者",
            "params": {
                "age": 35,
                "heart_rate": 80,
                "oxygen_saturation": 98,
                "unilateral_leg_swelling": False,
                "hemoptysis": False,
                "recent_surgery_or_trauma": False,
                "previous_pe": False,
                "previous_dvt": False,
                "hormone_use": False,
            },
            "expected_value": 0,
            "expected_valid": True,
            "description": "35岁，心率80，血氧98%，无任何阳性标准",
        },
        {
            "name": "PERC阳性 - 年龄>50",
            "params": {
                "age": 55,
                "heart_rate": 85,
                "oxygen_saturation": 97,
                "unilateral_leg_swelling": False,
                "hemoptysis": False,
                "recent_surgery_or_trauma": False,
                "previous_pe": False,
                "previous_dvt": False,
                "hormone_use": False,
            },
            "expected_value": 1,
            "expected_valid": True,
            "description": "55岁患者，仅年龄>50岁这一项阳性",
        },
        {
            "name": "PERC阳性 - 心率>100",
            "params": {
                "age": 45,
                "heart_rate": 110,
                "oxygen_saturation": 96,
                "unilateral_leg_swelling": False,
                "hemoptysis": False,
                "recent_surgery_or_trauma": False,
                "previous_pe": False,
                "previous_dvt": False,
                "hormone_use": False,
            },
            "expected_value": 1,
            "expected_valid": True,
            "description": "45岁，心率110，仅心率>100这一项阳性",
        },
        {
            "name": "PERC阳性 - 血氧<95%",
            "params": {
                "age": 40,
                "heart_rate": 90,
                "oxygen_saturation": 92,
                "unilateral_leg_swelling": False,
                "hemoptysis": False,
                "recent_surgery_or_trauma": False,
                "previous_pe": False,
                "previous_dvt": False,
                "hormone_use": False,
            },
            "expected_value": 1,
            "expected_valid": True,
            "description": "40岁，血氧92%，仅血氧<95%这一项阳性",
        },
        {
            "name": "PERC阳性 - 多项阳性",
            "params": {
                "age": 60,
                "heart_rate": 105,
                "oxygen_saturation": 93,
                "unilateral_leg_swelling": True,
                "hemoptysis": True,
                "recent_surgery_or_trauma": False,
                "previous_pe": False,
                "previous_dvt": False,
                "hormone_use": False,
            },
            "expected_value": 5,
            "expected_valid": True,
            "description": "60岁，心率105，血氧93%，单侧腿肿胀，咯血",
        },
        {
            "name": "PERC阳性 - 既往史阳性",
            "params": {
                "age": 45,
                "heart_rate": 85,
                "oxygen_saturation": 97,
                "unilateral_leg_swelling": False,
                "hemoptysis": False,
                "recent_surgery_or_trauma": False,
                "previous_pe": True,
                "previous_dvt": True,
                "hormone_use": False,
            },
            "expected_value": 1,
            "expected_valid": True,
            "description": "45岁，有既往PE和DVT史（PERC规则中PE/DVT史为同一标准）",
        },
        {
            "name": "PERC阳性 - 手术外伤史",
            "params": {
                "age": 42,
                "heart_rate": 88,
                "oxygen_saturation": 96,
                "unilateral_leg_swelling": False,
                "hemoptysis": False,
                "recent_surgery_or_trauma": True,
                "previous_pe": False,
                "previous_dvt": False,
                "hormone_use": True,
            },
            "expected_value": 2,
            "expected_valid": True,
            "description": "42岁，近期手术史，激素使用",
        },
        {
            "name": "参数验证 - 无效年龄",
            "params": {
                "age": -5,
                "heart_rate": 80,
                "oxygen_saturation": 98,
                "unilateral_leg_swelling": False,
                "hemoptysis": False,
                "recent_surgery_or_trauma": False,
                "previous_pe": False,
                "previous_dvt": False,
                "hormone_use": False,
            },
            "expected_valid": False,
            "description": "无效年龄（负数）",
        },
        {
            "name": "参数验证 - 无效心率",
            "params": {
                "age": 40,
                "heart_rate": 0,
                "oxygen_saturation": 98,
                "unilateral_leg_swelling": False,
                "hemoptysis": False,
                "recent_surgery_or_trauma": False,
                "previous_pe": False,
                "previous_dvt": False,
                "hormone_use": False,
            },
            "expected_valid": False,
            "description": "无效心率（零）",
        },
        {
            "name": "参数验证 - 无效血氧",
            "params": {
                "age": 40,
                "heart_rate": 80,
                "oxygen_saturation": 150,
                "unilateral_leg_swelling": False,
                "hemoptysis": False,
                "recent_surgery_or_trauma": False,
                "previous_pe": False,
                "previous_dvt": False,
                "hormone_use": False,
            },
            "expected_valid": False,
            "description": "无效血氧饱和度（>100%）",
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
                    "calculator_id": 48,
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
                    if actual_value != expected_value:
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
        print("PERC 计算器 MCP 测试")
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
        print("PERC 计算器测试结果")
        print("=" * 60)
        print(f"总测试数: {total_tests}")
        print(f"通过数: {total_passed}")
        print(f"失败数: {total_failed}")
        print(f"成功率: {(total_passed/total_tests*100):.1f}%")

        if total_failed == 0:
            print("\n✅ PERC 计算器所有测试都通过了！")
        else:
            print(f"\n❌ {total_failed} 个测试失败，请检查 PERC 计算器实现。")

    print_header()

    try:
        async with Client(MCP_SERVER_URL) as client:
            print_connection_status(True)
            passed, failed = await test_perc_calculator(client)
            print_overall_results(passed, failed)

    except Exception as e:
        print_connection_status(False, str(e))
        import traceback

        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("✅ PERC 计算器测试完成")


if __name__ == "__main__":
    asyncio.run(main())
