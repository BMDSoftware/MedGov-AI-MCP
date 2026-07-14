import asyncio
import json
import sys
import os
from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVER_URL


def map_parameter_names(test_params):
    """Map test parameter names to calculator parameter names"""
    mapped_params = {}
    
    for key, value in test_params.items():
        param_value, param_unit = value
        
        if key == "Temperature":
            # Pass temperature as [value, unit] tuple to calculator
            mapped_params["temperature"] = [param_value, param_unit]
        elif key == "Heart Rate or Pulse":
            mapped_params["heart_rate"] = [param_value, "bpm"]
        elif key == "respiratory rate":
            mapped_params["respiratory_rate"] = [param_value, "breaths/min"]
        elif key == "White blood cell count":
            # Pass WBC as [value, unit] tuple to calculator
            mapped_params["wbc"] = [param_value, param_unit]
        elif key == "PaCO₂":
            mapped_params["paco2"] = [param_value, param_unit]
    
    return mapped_params


async def test_sirs_criteria_calculator(client):
    """测试 SIRS Criteria 计算器的各种功能和参数"""

    def print_header():
        print("\n" + "=" * 60)
        print("SIRS Criteria 计算器测试套件")
        print("=" * 60)

    def print_test_case(i, test_case):
        print(f"\n测试 {i:2d} | {test_case['name']}")
        print(f"- {test_case['description']}")
        print(f"- 输入参数: {test_case['params']}")
        print(f"- 期望结果: {test_case['expected_result']}")

    def print_calculation_result(data):
        """打印完整的计算结果"""
        sirs_value = data.get("value", "N/A")
        unit = data.get("unit", "")
        explanation = data.get("explanation", "")
        metadata = data.get("metadata", {})
        warnings = data.get("warnings", [])

        # 基本结果
        print(f"- SIRS 评分: {sirs_value} {unit}")

        # 详细信息
        if metadata:
            criteria_details = metadata.get("criteria_details", [])
            if criteria_details:
                print("- 评估详情:")
                for detail in criteria_details:
                    print(f"  • {detail}")

        # 警告信息
        if warnings:
            for warning in warnings:
                print(f"- ⚠️  警告: {warning}")

    def print_test_result(i, passed, expected, actual):
        if passed:
            status = "✅ 通过"
        else:
            status = f"❌ 失败 (期望: {expected}, 实际: {actual})"
        print(f"- 测试结果: {status}")
        print("-" * 60)

    def print_summary(total, passed, failed):
        print(f"\n测试总结:")
        print(f"  总测试数: {total}")
        print(f"  通过数: {passed}")
        print(f"  失败数: {failed}")
        print(f"  成功率: {(passed/total*100):.1f}%")

        if failed == 0:
            print("\n✅ 所有测试都通过了！SIRS Criteria 计算器工作正常。")
        else:
            print(f"\n❌ {failed} 个测试失败，请检查实现。")

    # Test statistics
    total_tests = 0
    passed_tests = 0

    # Test cases from provided data
    test_cases = [
        {
            "name": "Test Case 1 - Row 6986",
            "params": {"Temperature": [39.0, "degrees celsius"], "Heart Rate or Pulse": [101.0, "beats per minute"], "respiratory rate": [18.0, "breaths per minute"], "White blood cell count": [6900.0, "µL"]},
            "expected_result": 2,
            "description": "温度>38°C, 心率>90, WBC正常, 呼吸频率正常 - 实际只有2个标准符合"
        },
        {
            "name": "Test Case 2 - Row 6976",
            "params": {"Temperature": [37.7, "degrees celsius"], "Heart Rate or Pulse": [120.0, "beats per minute"], "respiratory rate": [28.0, "breaths per minute"], "White blood cell count": [16200.0, "m^3"]},
            "expected_result": 3,
            "description": "温度正常, 心率>90, WBC>12000, 呼吸频率>20"
        },
        {
            "name": "Test Case 3 - Row 6853",
            "params": {"Temperature": [36.8, "degrees celsius"], "Heart Rate or Pulse": [92.0, "beats per minute"], "respiratory rate": [24.0, "breaths per minute"], "White blood cell count": [6.3, "L"]},
            "expected_result": 2,
            "description": "温度正常, 心率>90, WBC正常, 呼吸频率>20"
        },
        {
            "name": "Test Case 4 - Row 7035",
            "params": {"White blood cell count": [79500.0, "m^3"], "Temperature": [101.5, "degrees fahrenheit"], "respiratory rate": [16.0, "breaths per minute"], "Heart Rate or Pulse": [110.0, "beats per minute"]},
            "expected_result": 3,
            "description": "华氏温度>38°C, 心率>90, WBC>12000, 呼吸频率正常"
        },
        {
            "name": "Test Case 5 - Row 7032",
            "params": {"Temperature": [38.7, "degrees celsius"], "White blood cell count": [13310.0, "µL"], "respiratory rate": [33.0, "breaths per minute"], "Heart Rate or Pulse": [99.0, "beats per minute"]},
            "expected_result": 4,
            "description": "温度>38°C, 心率>90, WBC>12000, 呼吸频率>20"
        },
        {
            "name": "Test Case 6 - Row 6879",
            "params": {"Temperature": [98.0, "degrees fahrenheit"], "Heart Rate or Pulse": [98.0, "beats per minute"], "respiratory rate": [18.0, "breaths per minute"], "White blood cell count": [19.0, "L"]},
            "expected_result": 2,
            "description": "华氏温度98°F(36.7°C)正常, 心率>90, WBC>12000, 呼吸频率正常 - 实际只有2个标准符合"
        },
        {
            "name": "Test Case 7 - Row 6820",
            "params": {"Temperature": [37.8, "degrees celsius"], "Heart Rate or Pulse": [109.0, "beats per minute"], "respiratory rate": [22.0, "breaths per minute"], "White blood cell count": [14600.0, "µL"]},
            "expected_result": 3,
            "description": "温度正常, 心率>90, WBC>12000, 呼吸频率>20"
        },
        {
            "name": "Test Case 8 - Row 6850",
            "params": {"Temperature": [97.8, "degrees fahrenheit"], "Heart Rate or Pulse": [86.0, "beats per minute"], "respiratory rate": [18.0, "breaths per minute"], "White blood cell count": [11400.0, "µL"]},
            "expected_result": 0,
            "description": "华氏温度正常, 心率正常, WBC正常, 呼吸频率正常"
        },
        {
            "name": "Test Case 9 - Row 6893",
            "params": {"Temperature": [38.2, "degrees celsius"], "Heart Rate or Pulse": [95.0, "beats/min"], "respiratory rate": [16.0, "breaths/min"], "White blood cell count": [16210.0, "µL"]},
            "expected_result": 3,
            "description": "温度>38°C, 心率>90, WBC>12000, 呼吸频率正常"
        },
        {
            "name": "Test Case 10 - Row 6807",
            "params": {"Temperature": [36.4, "degrees celsius"], "Heart Rate or Pulse": [84.0, "beats per minute"], "respiratory rate": [16.0, "breaths per minute"], "White blood cell count": [10300.0, "m^3"]},
            "expected_result": 0,
            "description": "温度36.4°C正常(非<36°C), 心率正常, WBC正常, 呼吸频率正常 - 实际0个标准符合"
        },
        {
            "name": "Test Case 11 - Row 6945",
            "params": {"Temperature": [37.0, "degrees celsius"], "Heart Rate or Pulse": [90.0, "beats per minute"], "respiratory rate": [25.0, "breaths per minute"], "White blood cell count": [4000.0, "m^3"]},
            "expected_result": 1,
            "description": "温度正常, 心率90(非>90), WBC=4000(非<4000), 呼吸频率>20 - 实际只有1个标准符合"
        },
        {
            "name": "Test Case 12 - Row 6977",
            "params": {"Temperature": [37.8, "degrees celsius"], "Heart Rate or Pulse": [187.0, "beats per minute"], "respiratory rate": [25.0, "breaths per minute"], "White blood cell count": [13.7, "L"]},
            "expected_result": 3,
            "description": "温度正常, 心率>90, WBC>12000, 呼吸频率>20"
        },
        {
            "name": "Test Case 13 - Row 6979",
            "params": {"Temperature": [36.7, "degrees celsius"], "Heart Rate or Pulse": [120.0, "beats per minute"], "PaCO₂": [28.2, "mm hg"], "respiratory rate": [18.0, "breaths per minute"], "White blood cell count": [7900.0, "m^3"]},
            "expected_result": 2,
            "description": "温度正常, 心率>90, WBC正常, PaCO2<32"
        },
        {
            "name": "Test Case 14 - Row 6927",
            "params": {"Temperature": [99.0, "degrees fahrenheit"], "Heart Rate or Pulse": [75.0, "beats per minute"], "PaCO₂": [36.1, "mmhg"], "respiratory rate": [16.0, "breaths per minute"], "White blood cell count": [8400.0, "µL"]},
            "expected_result": 0,
            "description": "华氏温度正常, 心率正常, WBC正常, PaCO2正常"
        },
        {
            "name": "Test Case 15 - Row 6881",
            "params": {"Temperature": [37.4, "degrees celsius"], "Heart Rate or Pulse": [98.0, "beats per minute"], "respiratory rate": [19.0, "breaths per minute"], "White blood cell count": [10600.0, "m^3"]},
            "expected_result": 1,
            "description": "温度正常, 心率>90, WBC正常, 呼吸频率正常"
        },
        {
            "name": "Test Case 16 - Row 6895",
            "params": {"Temperature": [99.0, "degrees fahrenheit"], "Heart Rate or Pulse": [100.0, "beats per minute"], "respiratory rate": [30.0, "breaths per minute"], "White blood cell count": [12400.0, "m^3"]},
            "expected_result": 3,
            "description": "华氏温度正常, 心率>90, WBC>12000, 呼吸频率>20"
        },
        {
            "name": "Test Case 17 - Row 7011",
            "params": {"Temperature": [37.0, "degrees celsius"], "Heart Rate or Pulse": [102.0, "beats per minute"], "respiratory rate": [18.0, "breaths per minute"], "White blood cell count": [15500.0, "m^3"]},
            "expected_result": 2,
            "description": "温度正常, 心率>90, WBC>12000, 呼吸频率正常"
        },
        {
            "name": "Test Case 18 - Row 7029",
            "params": {"Temperature": [101.3, "degrees fahrenheit"], "White blood cell count": [6000.0, "µL"], "respiratory rate": [14.0, "breaths per minute"], "Heart Rate or Pulse": [112.0, "beats per minute"]},
            "expected_result": 2,
            "description": "华氏温度>38°C, 心率>90, WBC正常, 呼吸频率正常 - 实际只有2个标准符合"
        },
        {
            "name": "Test Case 19 - Row 6826",
            "params": {"Temperature": [37.2, "degrees celsius"], "Heart Rate or Pulse": [82.0, "beats per minute"], "respiratory rate": [15.0, "breaths per minute"], "White blood cell count": [10000.0, "µL"]},
            "expected_result": 0,
            "description": "温度正常, 心率正常, WBC正常, 呼吸频率正常"
        },
        {
            "name": "Test Case 20 - Row 6973",
            "params": {"Temperature": [36.6, "degrees celsius"], "Heart Rate or Pulse": [135.0, "beats per minute"], "respiratory rate": [35.0, "breaths per minute"], "White blood cell count": [1.1, "L"]},
            "expected_result": 3,
            "description": "温度<36°C, 心率>90, WBC<4000, 呼吸频率>20"
        }
    ]

    print_header()

    # Execute test cases
    for i, test_case in enumerate(test_cases, 1):
        total_tests += 1
        test_passed = True

        print_test_case(i, test_case)

        # Map and convert parameters
        try:
            mapped_params = map_parameter_names(test_case["params"])
            print(f"- 转换后参数: {mapped_params}")
        except Exception as e:
            print(f"- 参数转换错误: {e}")
            test_passed = False
            print_test_result(i, test_passed, test_case["expected_result"], "参数转换失败")
            continue

        # Calculation test
        try:
            calc_result = await client.call_tool(
                "calculate",
                {
                    "calculator_id": 51,  # SIRS Criteria Calculator ID
                    "parameters": mapped_params,
                },
            )

            # 使用 structured_content 或 data 属性获取实际数据
            calc_data = calc_result.structured_content or calc_result.data or {}

            if isinstance(calc_data, dict) and calc_data.get("success") and "result" in calc_data:
                # 成功计算
                data = calc_data["result"]
                actual_result = data.get("value")
                print_calculation_result(data)

                # 检查结果是否符合预期
                if actual_result == test_case["expected_result"]:
                    print(f"- ✅ 结果匹配 (期望: {test_case['expected_result']}, 实际: {actual_result})")
                else:
                    print(f"- ❌ 结果不匹配 (期望: {test_case['expected_result']}, 实际: {actual_result})")
                    test_passed = False
            else:
                # 计算失败
                error_msg = calc_data.get("error", "未知错误") if isinstance(calc_data, dict) else str(calc_data)
                print(f"- 计算失败: {error_msg}")
                test_passed = False

        except Exception as e:
            print(f"- 计算错误: {e}")
            test_passed = False

        # Update statistics
        if test_passed:
            passed_tests += 1

        print_test_result(i, test_passed, test_case["expected_result"], 
                         calc_data.get("result", {}).get("value", "N/A") if 'calc_data' in locals() else "N/A")

    print_summary(total_tests, passed_tests, total_tests - passed_tests)
    return passed_tests, total_tests - passed_tests


async def main():
    def print_header():
        print("SIRS Criteria 计算器 MCP 测试")
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
        print("SIRS Criteria 计算器测试结果")
        print("=" * 60)
        print(f"总测试数: {total_tests}")
        print(f"通过数: {total_passed}")
        print(f"失败数: {total_failed}")
        print(f"成功率: {(total_passed/total_tests*100):.1f}%")

        if total_failed == 0:
            print("\n✅ SIRS Criteria 计算器所有测试都通过了！")
        else:
            print(f"\n❌ {total_failed} 个测试失败，请检查 SIRS Criteria 计算器实现。")

    print_header()

    try:
        async with Client(MCP_SERVER_URL) as client:
            print_connection_status(True)
            passed, failed = await test_sirs_criteria_calculator(client)
            print_overall_results(passed, failed)

    except Exception as e:
        print_connection_status(False, str(e))
        import traceback

        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("✅ SIRS Criteria 计算器测试完成")


if __name__ == "__main__":
    asyncio.run(main())