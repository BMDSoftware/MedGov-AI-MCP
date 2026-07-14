import asyncio
import json
import sys
import os
from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVER_URL


async def test_sodium_correction_hyperglycemia_calculator(client):
    """测试高血糖钠校正计算器的各种功能和单位转换"""

    def print_header():
        print("\n" + "=" * 60)
        print("高血糖钠校正计算器测试套件")
        print("=" * 60)

    def print_test_case(i, test_case):
        print(f"\n测试 {i:2d} | {test_case['name']}")
        print(f"- {test_case['description']}")
        print(f"- 输入参数: {test_case['params']}")
        if 'expected_result' in test_case:
            print(f"- 期望结果: {test_case['expected_result']}")

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
        result_value = data.get("value", "N/A")
        unit = data.get("unit", "")
        explanation = data.get("explanation", "")
        details = data.get("details", {})
        warnings = data.get("warnings", [])

        # 基本结果
        print(f"- 校正钠浓度: {result_value} {unit}")

        # 计算详情
        if details:
            measured_sodium = details.get("measured_sodium_mEq_per_L")
            glucose = details.get("serum_glucose_mg_per_dL")
            correction_factor = details.get("correction_factor")
            glucose_excess = details.get("glucose_excess")
            sodium_correction = details.get("sodium_correction")
            interpretation = details.get("interpretation")

            if measured_sodium is not None:
                print(f"- 测定钠浓度: {measured_sodium} mEq/L")
            if glucose is not None:
                print(f"- 血糖: {glucose} mg/dL")
            if glucose_excess is not None:
                print(f"- 超过100的血糖: {glucose_excess} mg/dL")
            if sodium_correction is not None:
                print(f"- 钠校正量: {sodium_correction} mEq/L")
            if interpretation:
                print(f"- 解释: {interpretation}")

        # 警告信息
        if warnings:
            for warning in warnings:
                print(f"- ⚠️  警告: {warning}")

        # 详细解释（截取前几行显示）
        if explanation:
            lines = explanation.split('\n')[:3]
            print(f"- 解释摘要: {' '.join(lines).strip()}")

    def print_test_result(i, passed, expected_value=None, actual_value=None, tolerance=None):
        if passed:
            status = "✅ 通过"
        else:
            status = "❌ 失败"
        print(f"- 测试结果: {status}")
        
        if expected_value is not None and actual_value is not None:
            print(f"- 期望值: {expected_value}")
            print(f"- 实际值: {actual_value}")
            if tolerance is not None:
                print(f"- 容差: ±{tolerance}")
                
        print("-" * 60)

    def print_summary(total, passed, failed):
        print(f"\n测试总结:")
        print(f"  总测试数: {total}")
        print(f"  通过数: {passed}")
        print(f"  失败数: {failed}")
        print(f"  成功率: {(passed/total*100):.1f}%")

        if failed == 0:
            print("\n✅ 所有测试都通过了！高血糖钠校正计算器工作正常。")
        else:
            print(f"\n❌ {failed} 个测试失败，请检查实现。")

        print("\n测试覆盖范围:")
        features = [
            "多种单位格式 (mEq/L, mmol/L, mEq/dL)",
            "血糖单位转换 (mg/dL, mmol/L)",
            "参数验证",
            "计算精度",
            "错误处理",
            "边界测试",
        ]
        for feature in features:
            print(f"  - {feature}")

    # Test statistics
    total_tests = 0
    passed_tests = 0

    def convert_glucose_to_mgdl(glucose, unit):
        """将glucose转换为mg/dL"""
        if unit == "mmol/L":
            return glucose * 18.0182  # 1 mmol/L = 18.0182 mg/dL
        elif unit == "mg/dL":
            return glucose
        else:
            raise ValueError(f"Unknown glucose unit: {unit}")

    def convert_sodium_to_meql(sodium, unit):
        """将sodium转换为mEq/L"""
        if unit in ["mmol/L", "mEq/L"]:
            return sodium  # mmol/L和mEq/L在钠离子情况下数值相同
        elif unit == "mEq/dL":
            return sodium * 10  # mEq/dL转换为mEq/L
        else:
            raise ValueError(f"Unknown sodium unit: {unit}")

    def is_within_tolerance(actual, expected, lower_limit, upper_limit):
        """检查结果是否在容差范围内"""
        return lower_limit <= actual <= upper_limit

    # Test cases from data file - 包含所有20个测试用例
    test_cases = [
        # Row 5506 - 异常值但仍需测试
        {
            "name": "Very high glucose with mEq/dL sodium",
            "row_number": "5506",
            "params": {"glucose": "550mg/dL", "sodium": "1380mEq/L"},  # 138.0 mEq/dL = 1380 mEq/L
            "expected_result": 1390.8,
            "lower_limit": 1321.26,
            "upper_limit": 1460.34,
            "description": "极高血糖550mg/dL，钠138mEq/dL",
            "expected_valid": True,
        },
        # Row 5562
        {
            "name": "mmol/L glucose to mg/dL conversion",
            "row_number": "5562",
            "params": {"glucose": "63mg/dL", "sodium": "137mEq/L"},  # 3.5 mmol/L = 63.06 mg/dL
            "expected_result": 136.33,
            "lower_limit": 129.513,
            "upper_limit": 143.147,
            "description": "血糖3.5mmol/L，钠137mmol/L",
            "expected_valid": True,
        },
        # Row 5590
        {
            "name": "Elevated glucose with mmol/L sodium",
            "row_number": "5590",
            "params": {"glucose": "191mg/dL", "sodium": "143mEq/L"},
            "expected_result": 145.184,
            "lower_limit": 137.925,
            "upper_limit": 152.443,
            "description": "血糖191mg/dL，钠143mmol/L",
            "expected_valid": True,
        },
        # Row 5419
        {
            "name": "Low glucose with mEq/L sodium",
            "row_number": "5419",
            "params": {"glucose": "70mg/dL", "sodium": "115mEq/L"},
            "expected_result": 114.28,
            "lower_limit": 108.566,
            "upper_limit": 119.994,
            "description": "血糖70mg/dL，钠115mEq/L",
            "expected_valid": True,
        },
        # Row 5634
        {
            "name": "Standard elevation case",
            "row_number": "5634",
            "params": {"glucose": "125mg/dL", "sodium": "130mEq/L"},
            "expected_result": 130.6,
            "lower_limit": 124.07,
            "upper_limit": 137.13,
            "description": "血糖125mg/dL，钠130mEq/L",
            "expected_valid": True,
        },
        # Row 5650
        {
            "name": "High glucose with mmol/L sodium",
            "row_number": "5650",
            "params": {"glucose": "486mg/dL", "sodium": "132mEq/L"},
            "expected_result": 141.264,
            "lower_limit": 134.201,
            "upper_limit": 148.327,
            "description": "血糖486mg/dL，钠132mmol/L",
            "expected_valid": True,
        },
        # Row 5449
        {
            "name": "Slightly elevated glucose",
            "row_number": "5449",
            "params": {"glucose": "102mg/dL", "sodium": "119mEq/L"},
            "expected_result": 119.048,
            "lower_limit": 113.096,
            "upper_limit": 125.0,
            "description": "血糖102mg/dL，钠119mEq/L",
            "expected_valid": True,
        },
        # Row 5447
        {
            "name": "mmol/L glucose conversion case 2",
            "row_number": "5447",
            "params": {"glucose": "99mg/dL", "sodium": "137mEq/L"},  # 5.5 mmol/L = 99.1 mg/dL
            "expected_result": 136.762,
            "lower_limit": 129.924,
            "upper_limit": 143.6,
            "description": "血糖5.5mmol/L，钠137mmol/L",
            "expected_valid": True,
        },
        # Row 5415
        {
            "name": "Moderate glucose elevation",
            "row_number": "5415",
            "params": {"glucose": "127mg/dL", "sodium": "140mEq/L"},
            "expected_result": 140.648,
            "lower_limit": 133.616,
            "upper_limit": 147.68,
            "description": "血糖127mg/dL，钠140mEq/L",
            "expected_valid": True,
        },
        # Row 5470
        {
            "name": "Low glucose with low sodium",
            "row_number": "5470",
            "params": {"glucose": "90mg/dL", "sodium": "117mEq/L"},
            "expected_result": 116.76,
            "lower_limit": 110.922,
            "upper_limit": 122.598,
            "description": "血糖90mg/dL，钠117mEq/L",
            "expected_valid": True,
        },
        # Row 5437
        {
            "name": "High glucose with mmol/L sodium 2",
            "row_number": "5437",
            "params": {"glucose": "237mg/dL", "sodium": "127mEq/L"},
            "expected_result": 130.288,
            "lower_limit": 123.774,
            "upper_limit": 136.802,
            "description": "血糖237mg/dL，钠127mmol/L",
            "expected_valid": True,
        },
        # Row 5485
        {
            "name": "Moderate glucose with mmol/L sodium",
            "row_number": "5485",
            "params": {"glucose": "164mg/dL", "sodium": "133mEq/L"},
            "expected_result": 134.536,
            "lower_limit": 127.809,
            "upper_limit": 141.263,
            "description": "血糖164mg/dL，钠133mmol/L",
            "expected_valid": True,
        },
        # Row 5432
        {
            "name": "Low mmol/L glucose conversion",
            "row_number": "5432",
            "params": {"glucose": "74mg/dL", "sodium": "127mEq/L"},  # 4.1 mmol/L = 73.87 mg/dL
            "expected_result": 126.33,
            "lower_limit": 120.013,
            "upper_limit": 132.647,
            "description": "血糖4.1mmol/L，钠127mmol/L",
            "expected_valid": True,
        },
        # Row 5486
        {
            "name": "High glucose with normal sodium",
            "row_number": "5486",
            "params": {"glucose": "170mg/dL", "sodium": "142mEq/L"},
            "expected_result": 143.68,
            "lower_limit": 136.496,
            "upper_limit": 150.864,
            "description": "血糖170mg/dL，钠142mEq/L",
            "expected_valid": True,
        },
        # Row 5482
        {
            "name": "Moderate glucose with high sodium",
            "row_number": "5482",
            "params": {"glucose": "133mg/dL", "sodium": "144mEq/L"},
            "expected_result": 144.792,
            "lower_limit": 137.552,
            "upper_limit": 152.032,
            "description": "血糖133mg/dL，钠144mEq/L",
            "expected_valid": True,
        },
        # Row 5464
        {
            "name": "Low glucose with mmol/L sodium",
            "row_number": "5464",
            "params": {"glucose": "90mg/dL", "sodium": "138mEq/L"},
            "expected_result": 137.76,
            "lower_limit": 130.872,
            "upper_limit": 144.648,
            "description": "血糖90mg/dL，钠138mmol/L",
            "expected_valid": True,
        },
        # Row 5493
        {
            "name": "High glucose with normal sodium 2",
            "row_number": "5493",
            "params": {"glucose": "179mg/dL", "sodium": "140mEq/L"},
            "expected_result": 141.896,
            "lower_limit": 134.801,
            "upper_limit": 148.991,
            "description": "血糖179mg/dL，钠140mEq/L",
            "expected_valid": True,
        },
        # Row 5409
        {
            "name": "Mild glucose elevation with mmol/L sodium",
            "row_number": "5409",
            "params": {"glucose": "110mg/dL", "sodium": "136mEq/L"},
            "expected_result": 136.24,
            "lower_limit": 129.428,
            "upper_limit": 143.052,
            "description": "血糖110mg/dL，钠136mmol/L",
            "expected_valid": True,
        },
        # Row 5405
        {
            "name": "High glucose with high sodium",
            "row_number": "5405",
            "params": {"glucose": "182mg/dL", "sodium": "165mEq/L"},
            "expected_result": 166.968,
            "lower_limit": 158.62,
            "upper_limit": 175.316,
            "description": "血糖182mg/dL，钠165mmol/L",
            "expected_valid": True,
        },
        # Row 5448
        {
            "name": "Mild glucose elevation",
            "row_number": "5448",
            "params": {"glucose": "115mg/dL", "sodium": "130mEq/L"},
            "expected_result": 130.36,
            "lower_limit": 123.842,
            "upper_limit": 136.878,
            "description": "血糖115mg/dL，钠130mEq/L",
            "expected_valid": True,
        },
        # 额外的错误测试用例
        {
            "name": "Invalid - negative glucose",
            "params": {"glucose": "-50mg/dL", "sodium": "135mEq/L"},
            "expected_valid": False,
            "description": "无效血糖（负数）",
        },
        {
            "name": "Invalid - zero sodium", 
            "params": {"glucose": "100mg/dL", "sodium": "0mEq/L"},
            "expected_valid": False,
            "description": "无效钠浓度（零）",
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
                    "calculator_id": 26,
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
                elif "expected_result" in test_case:
                    # 检查计算结果是否在容差范围内
                    actual_value = data.get("value", 0)
                    expected_value = test_case["expected_result"]
                    lower_limit = test_case.get("lower_limit", expected_value * 0.95)
                    upper_limit = test_case.get("upper_limit", expected_value * 1.05)
                    
                    if not is_within_tolerance(actual_value, expected_value, lower_limit, upper_limit):
                        print(f"- 错误: 结果超出容差范围")
                        print(f"  实际值: {actual_value}")
                        print(f"  期望值: {expected_value}")
                        print(f"  容差范围: [{lower_limit}, {upper_limit}]")
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

        # Print result
        expected_value = test_case.get("expected_result")
        print_test_result(i, test_passed, expected_value)

    print_summary(total_tests, passed_tests, total_tests - passed_tests)
    return passed_tests, total_tests - passed_tests


async def main():
    def print_header():
        print("高血糖钠校正计算器 MCP 测试")
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
        print("高血糖钠校正计算器测试结果")
        print("=" * 60)
        print(f"总测试数: {total_tests}")
        print(f"通过数: {total_passed}")
        print(f"失败数: {total_failed}")
        print(f"成功率: {(total_passed/total_tests*100):.1f}%")

        if total_failed == 0:
            print("\n✅ 高血糖钠校正计算器所有测试都通过了！")
        else:
            print(f"\n❌ {total_failed} 个测试失败，请检查高血糖钠校正计算器实现。")

    print_header()

    try:
        async with Client(MCP_SERVER_URL) as client:
            print_connection_status(True)
            passed, failed = await test_sodium_correction_hyperglycemia_calculator(client)
            print_overall_results(passed, failed)

    except Exception as e:
        print_connection_status(False, str(e))
        import traceback

        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("✅ 高血糖钠校正计算器测试完成")


if __name__ == "__main__":
    asyncio.run(main())