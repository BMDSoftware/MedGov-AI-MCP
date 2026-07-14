import asyncio
import json
import sys
import os
from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVER_URL


def fahrenheit_to_celsius(temp_f):
    """Convert Fahrenheit to Celsius"""
    return (temp_f - 32) * 5 / 9


def map_test_params_to_calculator_params(test_params):
    """Map test data parameter names to calculator parameter names"""
    mapped_params = {}
    
    # Map age directly
    if "age" in test_params:
        age_value = test_params["age"]
        if isinstance(age_value, list):
            mapped_params["age"] = age_value[0]
        else:
            mapped_params["age"] = age_value
    
    # Map temperature and convert if necessary
    if "Temperature" in test_params:
        temp_value = test_params["Temperature"]
        if isinstance(temp_value, list):
            temp_num = temp_value[0]
            temp_unit = temp_value[1].lower()
            if "fahrenheit" in temp_unit or "fahreinheit" in temp_unit:
                temp_num = fahrenheit_to_celsius(temp_num)
            mapped_params["temperature"] = temp_num
        else:
            mapped_params["temperature"] = temp_value
    
    # Map boolean parameters
    if "Cough Absent" in test_params:
        mapped_params["cough_absent"] = test_params["Cough Absent"]
    
    if "Tender/swollen anterior cervical lymph nodes" in test_params:
        mapped_params["tender_lymph_nodes"] = test_params["Tender/swollen anterior cervical lymph nodes"]
    
    if "Exudate or swelling on tonsils" in test_params:
        mapped_params["exudate_swelling_tonsils"] = test_params["Exudate or swelling on tonsils"]
    
    return mapped_params


async def test_centor_score_calculator(client):
    """测试 Centor Score 计算器的各种功能"""

    def print_header():
        print("\n" + "=" * 60)
        print("Centor Score 计算器测试套件")
        print("=" * 60)

    def print_test_case(i, test_case):
        print(f"\n测试 {i:2d} | {test_case['name']}")
        print(f"- {test_case['description']}")
        print(f"- 输入参数: {test_case['params']}")
        if 'expected_score' in test_case:
            print(f"- 期望分数: {test_case['expected_score']}")

    def print_calculation_result(data):
        """打印完整的计算结果"""
        score_value = data.get("value", "N/A")
        unit = data.get("unit", "")
        explanation = data.get("explanation", "")
        metadata = data.get("metadata", {})
        warnings = data.get("warnings", [])

        # 基本结果
        print(f"- Centor Score: {score_value} {unit}")

        # 元数据信息
        if metadata:
            age = metadata.get("age")
            temperature = metadata.get("temperature")
            exudate_swelling_tonsils = metadata.get("exudate_swelling_tonsils")
            tender_lymph_nodes = metadata.get("tender_lymph_nodes")
            cough_absent = metadata.get("cough_absent")
            risk_assessment = metadata.get("risk_assessment")

            if age is not None:
                print(f"- 年龄: {age} years")
            if temperature is not None:
                print(f"- 体温: {temperature}°C")
            if exudate_swelling_tonsils is not None:
                print(f"- 扁桃体渗出或肿胀: {'是' if exudate_swelling_tonsils else '否'}")
            if tender_lymph_nodes is not None:
                print(f"- 颈前淋巴结触痛: {'是' if tender_lymph_nodes else '否'}")
            if cough_absent is not None:
                print(f"- 无咳嗽: {'是' if cough_absent else '否'}")
            if risk_assessment:
                print(f"- 风险评估: {risk_assessment}")

        # 警告信息
        if warnings:
            for warning in warnings:
                print(f"- ⚠️  警告: {warning}")

        # 详细解释（截取前几行显示）
        if explanation:
            explanation_lines = explanation.strip().split('\n')[:5]
            print(f"- 解释: {explanation_lines[0]}...")

    def print_test_result(i, passed, expected=None, actual=None):
        if passed:
            status = "✅ 通过"
        else:
            status = "❌ 失败"
            if expected is not None and actual is not None:
                status += f" (期望: {expected}, 实际: {actual})"
        print(f"- 测试结果: {status}")
        print("-" * 60)

    def print_summary(total, passed, failed):
        print(f"\n测试总结:")
        print(f"  总测试数: {total}")
        print(f"  通过数: {passed}")
        print(f"  失败数: {failed}")
        print(f"  成功率: {(passed/total*100):.1f}%")

        if failed == 0:
            print("\n✅ 所有测试都通过了！Centor Score 计算器工作正常。")
        else:
            print(f"\n❌ {failed} 个测试失败，请检查实现。")

    # Test statistics
    total_tests = 0
    passed_tests = 0

    # Test cases based on real data from medcalc_train_testcase_s20.jsonl
    test_cases = [
        {
            "name": "54岁, 发热39.5°C, 无咳嗽, 无淋巴结肿大, 无扁桃体渗出",
            "params": {
                "age": 54,
                "temperature": 39.5,
                "cough_absent": True,
                "tender_lymph_nodes": False,
                "exudate_swelling_tonsils": False
            },
            "expected_score": 1,
            "description": "≥45岁(-1) + 发热>38°C(+1) + 无咳嗽(+1) = 1分",
        },
        {
            "name": "16岁, 发热99.9°F, 无咳嗽, 淋巴结肿大, 无扁桃体渗出",
            "params": {
                "age": 16,
                "temperature": fahrenheit_to_celsius(99.9),  # ~37.7°C
                "cough_absent": True,
                "tender_lymph_nodes": True,
                "exudate_swelling_tonsils": False
            },
            "expected_score": 2,
            "description": "15-44岁(0) + 无咳嗽(+1) + 淋巴结肿大(+1) = 2分",
        },
        {
            "name": "23岁, 发热37.7°C, 无咳嗽, 淋巴结肿大, 扁桃体渗出",
            "params": {
                "age": 23,
                "temperature": 37.7,
                "cough_absent": True,
                "tender_lymph_nodes": True,
                "exudate_swelling_tonsils": True
            },
            "expected_score": 3,
            "description": "15-44岁(0) + 无咳嗽(+1) + 淋巴结肿大(+1) + 扁桃体渗出(+1) = 3分",
        },
        {
            "name": "5岁, 发热39.3°C, 淋巴结肿大, 扁桃体渗出, 有咳嗽",
            "params": {
                "age": 5,
                "temperature": 39.3,
                "cough_absent": False,
                "tender_lymph_nodes": True,
                "exudate_swelling_tonsils": True
            },
            "expected_score": 4,
            "description": "3-14岁(+1) + 发热>38°C(+1) + 淋巴结肿大(+1) + 扁桃体渗出(+1) = 4分",
        },
        {
            "name": "62岁, 体温37.0°C, 无咳嗽, 无淋巴结肿大, 无扁桃体渗出",
            "params": {
                "age": 62,
                "temperature": 37.0,
                "cough_absent": True,
                "tender_lymph_nodes": False,
                "exudate_swelling_tonsils": False
            },
            "expected_score": 0,
            "description": "≥45岁(-1) + 无发热(0) + 无咳嗽(+1) + 无淋巴结肿大(0) + 无扁桃体渗出(0) = 0分",
        },
        {
            "name": "4岁, 发热38.5°C, 无咳嗽, 淋巴结肿大, 无扁桃体渗出",
            "params": {
                "age": 4,
                "temperature": 38.5,
                "cough_absent": True,
                "tender_lymph_nodes": True,
                "exudate_swelling_tonsils": False
            },
            "expected_score": 4,
            "description": "3-14岁(+1) + 发热>38°C(+1) + 无咳嗽(+1) + 淋巴结肿大(+1) = 4分",
        },
        {
            "name": "无效年龄测试 (负数)",
            "params": {
                "age": -5,
                "temperature": 38.0,
                "cough_absent": True,
                "tender_lymph_nodes": False,
                "exudate_swelling_tonsils": False
            },
            "expected_valid": False,
            "description": "测试无效年龄参数",
        },
        {
            "name": "无效体温测试 (过高)",
            "params": {
                "age": 25,
                "temperature": 50.0,
                "cough_absent": True,
                "tender_lymph_nodes": False,
                "exudate_swelling_tonsils": False
            },
            "expected_valid": False,
            "description": "测试无效体温参数",
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
                    "calculator_id": 20,
                    "parameters": test_case["params"],
                },
            )

            # 使用 structured_content 或 data 属性获取实际数据
            calc_data = calc_result.structured_content or calc_result.data or {}

            if isinstance(calc_data, dict) and calc_data.get("success") and "result" in calc_data:
                # 成功计算
                data = calc_data["result"]
                print_calculation_result(data)

                # 检查期望分数
                if "expected_score" in test_case:
                    actual_score = data.get("value")
                    expected_score = test_case["expected_score"]
                    if actual_score != expected_score:
                        print(f"- 错误: 分数不匹配 (期望: {expected_score}, 实际: {actual_score})")
                        test_passed = False

                # 检查是否符合有效性预期
                if "expected_valid" in test_case and not test_case["expected_valid"]:
                    print("- 错误: 预期失败但计算成功")
                    test_passed = False
            else:
                # 计算失败
                error_msg = calc_data.get("error", "未知错误") if isinstance(calc_data, dict) else str(calc_data)
                print(f"- 计算失败: {error_msg}")

                # 检查是否符合有效性预期
                if "expected_valid" not in test_case or test_case.get("expected_valid", True):
                    print("- 错误: 预期成功但计算失败")
                    test_passed = False

        except Exception as e:
            print(f"- 计算错误: {e}")
            # 检查是否符合有效性预期
            if "expected_valid" not in test_case or test_case.get("expected_valid", True):
                test_passed = False

        # Update statistics
        if test_passed:
            passed_tests += 1

        # Print result with expected vs actual if applicable
        expected_score = test_case.get("expected_score")
        actual_score = None
        try:
            if calc_data and calc_data.get("success") and "result" in calc_data:
                actual_score = calc_data["result"].get("value")
        except:
            pass
        
        print_test_result(i, test_passed, expected_score, actual_score)

    print_summary(total_tests, passed_tests, total_tests - passed_tests)
    return passed_tests, total_tests - passed_tests


async def main():
    def print_header():
        print("Centor Score 计算器 MCP 测试")
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
        print("Centor Score 计算器测试结果")
        print("=" * 60)
        print(f"总测试数: {total_tests}")
        print(f"通过数: {total_passed}")
        print(f"失败数: {total_failed}")
        print(f"成功率: {(total_passed/total_tests*100):.1f}%")

        if total_failed == 0:
            print("\n✅ Centor Score 计算器所有测试都通过了！")
        else:
            print(f"\n❌ {total_failed} 个测试失败，请检查 Centor Score 计算器实现。")

    print_header()

    try:
        async with Client(MCP_SERVER_URL) as client:
            print_connection_status(True)
            passed, failed = await test_centor_score_calculator(client)
            print_overall_results(passed, failed)

    except Exception as e:
        print_connection_status(False, str(e))
        import traceback
        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("✅ Centor Score 计算器测试完成")


if __name__ == "__main__":
    asyncio.run(main())