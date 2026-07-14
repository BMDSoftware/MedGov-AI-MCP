import asyncio
import json
import sys
import os
from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVER_URL


async def test_feverpain_calculator(client):
    """测试 FeverPAIN 计算器的各种功能"""

    def print_header():
        print("\n" + "=" * 60)
        print("FeverPAIN 计算器测试套件")
        print("=" * 60)

    def print_test_case(i, test_case):
        print(f"\n测试 {i:2d} | {test_case['name']}")
        print(f"- {test_case['description']}")
        print(f"- 输入参数: {test_case['params']}")

    def print_calculation_result(data):
        """打印完整的计算结果"""
        score_value = data.get("value", "N/A")
        unit = data.get("unit", "")
        explanation = data.get("explanation", "")
        metadata = data.get("metadata", {})
        warnings = data.get("warnings", [])

        # 基本结果
        print(f"- FeverPAIN 评分: {score_value} {unit}")

        # 元数据信息
        if metadata:
            strep_probability = metadata.get("strep_probability", "N/A")
            recommendation = metadata.get("recommendation", "N/A")
            
            print(f"- 链球菌感染概率: {strep_probability}")
            print(f"- 建议: {recommendation}")
            
            # 打印各项得分
            fever_points = metadata.get("fever_points", 0)
            cough_coryza_points = metadata.get("cough_coryza_points", 0)
            onset_points = metadata.get("onset_points", 0)
            purulent_points = metadata.get("purulent_points", 0)
            inflammation_points = metadata.get("inflammation_points", 0)
            
            print(f"- 详细得分: 发热({fever_points}) + 无咳嗽/鼻炎({cough_coryza_points}) + 发病≤3天({onset_points}) + 化脓性扁桃体({purulent_points}) + 严重炎症({inflammation_points})")

        # 警告信息
        if warnings:
            for warning in warnings:
                print(f"- ⚠️  警告: {warning}")

        # 详细解释（截取前几行显示）
        if explanation:
            lines = explanation.strip().split('\n')
            if len(lines) > 3:
                print(f"- 解释: {lines[0]}...（共{len(lines)}行）")
            else:
                print(f"- 解释: {explanation.strip()}")

    def print_test_result(i, passed, expected_score=None, actual_score=None):
        if passed:
            status = "✅ 通过"
        else:
            status = "❌ 失败"
        print(f"- 测试结果: {status}")
        if expected_score is not None and actual_score is not None:
            print(f"- 期望评分: {expected_score}, 实际评分: {actual_score}")
        print("-" * 60)

    def print_summary(total, passed, failed):
        print(f"\n测试总结:")
        print(f"  总测试数: {total}")
        print(f"  通过数: {passed}")
        print(f"  失败数: {failed}")
        print(f"  成功率: {(passed/total*100):.1f}%")

        if failed == 0:
            print("\n✅ 所有测试都通过了！FeverPAIN 计算器工作正常。")
        else:
            print(f"\n❌ {failed} 个测试失败，请检查实现。")

        print("\n测试覆盖范围:")
        features = [
            "发热评估",
            "咳嗽/鼻炎症状评估",
            "症状发作时间评估",
            "化脓性扁桃体评估",
            "扁桃体炎症严重程度评估",
            "综合评分计算",
            "链球菌感染概率评估",
            "治疗建议生成",
            "边界测试"
        ]
        for feature in features:
            print(f"  - {feature}")

    # Test statistics
    total_tests = 0
    passed_tests = 0

    # Test cases based on data from medcalc_train_testcase_s20.jsonl
    test_cases = [
        {
            "name": "仅症状发作时间 ≤3天",
            "params": {
                "fever_24_hours": False,
                "cough_coryza_absent": False,
                "symptom_onset": True,
                "purulent_tonsils": False,
                "severe_tonsil_inflammation": False
            },
            "expected_score": 1,
            "description": "Row 6032: 仅症状发作≤3天为真"
        },
        {
            "name": "无任何症状",
            "params": {
                "fever_24_hours": False,
                "cough_coryza_absent": False,
                "symptom_onset": False,
                "purulent_tonsils": False,
                "severe_tonsil_inflammation": False
            },
            "expected_score": 0,
            "description": "Row 6047: 所有症状均为假"
        },
        {
            "name": "化脓性扁桃体 + 症状发作 ≤3天",
            "params": {
                "fever_24_hours": False,
                "cough_coryza_absent": False,
                "symptom_onset": True,
                "purulent_tonsils": True,
                "severe_tonsil_inflammation": False
            },
            "expected_score": 2,
            "description": "Row 6039: 化脓性扁桃体 + 症状发作≤3天"
        },
        {
            "name": "发热 + 无咳嗽鼻炎",
            "params": {
                "fever_24_hours": True,
                "cough_coryza_absent": True,
                "symptom_onset": False,
                "purulent_tonsils": False,
                "severe_tonsil_inflammation": False
            },
            "expected_score": 2,
            "description": "Row 6030: 发热在过去24小时 + 无咳嗽或鼻炎"
        },
        {
            "name": "仅化脓性扁桃体",
            "params": {
                "fever_24_hours": False,
                "cough_coryza_absent": False,
                "symptom_onset": False,
                "purulent_tonsils": True,
                "severe_tonsil_inflammation": False
            },
            "expected_score": 1,
            "description": "Row 6033: 仅化脓性扁桃体为真"
        },
        {
            "name": "发热 + 无咳嗽鼻炎 + 症状发作 ≤3天",
            "params": {
                "fever_24_hours": True,
                "cough_coryza_absent": True,
                "symptom_onset": True,
                "purulent_tonsils": False,
                "severe_tonsil_inflammation": False
            },
            "expected_score": 3,
            "description": "Row 6027: 三项指标为真"
        },
        {
            "name": "仅发热",
            "params": {
                "fever_24_hours": True,
                "cough_coryza_absent": False,
                "symptom_onset": False,
                "purulent_tonsils": False,
                "severe_tonsil_inflammation": False
            },
            "expected_score": 1,
            "description": "Row 6029: 仅发热在过去24小时为真"
        },
        {
            "name": "发热 + 症状发作 ≤3天",
            "params": {
                "fever_24_hours": True,
                "cough_coryza_absent": False,
                "symptom_onset": True,
                "purulent_tonsils": False,
                "severe_tonsil_inflammation": False
            },
            "expected_score": 2,
            "description": "Row 6026: 发热 + 症状发作≤3天"
        },
        {
            "name": "症状发作 ≤3天 + 化脓性扁桃体 + 严重扁桃体炎症",
            "params": {
                "fever_24_hours": False,
                "cough_coryza_absent": False,
                "symptom_onset": True,
                "purulent_tonsils": True,
                "severe_tonsil_inflammation": True
            },
            "expected_score": 3,
            "description": "Row 6037: 三项严重指标为真"
        },
        {
            "name": "所有症状都存在（最高分）",
            "params": {
                "fever_24_hours": True,
                "cough_coryza_absent": True,
                "symptom_onset": True,
                "purulent_tonsils": True,
                "severe_tonsil_inflammation": True
            },
            "expected_score": 5,
            "description": "边界测试: 所有症状都存在"
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
                    "calculator_id": 33,
                    "parameters": test_case["params"],
                },
            )

            # 使用 structured_content 或 data 属性获取实际数据
            calc_data = calc_result.structured_content or calc_result.data or {}

            if isinstance(calc_data, dict) and calc_data.get("success") and "result" in calc_data:
                # 成功计算
                data = calc_data["result"]
                print_calculation_result(data)

                # 检查评分是否符合预期
                actual_score = data.get("value")
                expected_score = test_case.get("expected_score")
                
                if expected_score is not None and actual_score != expected_score:
                    print(f"- 错误: 期望评分 {expected_score}，但得到 {actual_score}")
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

        print_test_result(i, test_passed, 
                         test_case.get("expected_score"), 
                         data.get("value") if 'data' in locals() else None)

    print_summary(total_tests, passed_tests, total_tests - passed_tests)
    return passed_tests, total_tests - passed_tests


async def main():
    def print_header():
        print("FeverPAIN 计算器 MCP 测试")
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
        print("FeverPAIN 计算器测试结果")
        print("=" * 60)
        print(f"总测试数: {total_tests}")
        print(f"通过数: {total_passed}")
        print(f"失败数: {total_failed}")
        print(f"成功率: {(total_passed/total_tests*100):.1f}%")

        if total_failed == 0:
            print("\n✅ FeverPAIN 计算器所有测试都通过了！")
        else:
            print(f"\n❌ {total_failed} 个测试失败，请检查 FeverPAIN 计算器实现。")

    print_header()

    try:
        async with Client(MCP_SERVER_URL) as client:
            print_connection_status(True)
            passed, failed = await test_feverpain_calculator(client)
            print_overall_results(passed, failed)

    except Exception as e:
        print_connection_status(False, str(e))
        import traceback

        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("✅ FeverPAIN 计算器测试完成")


if __name__ == "__main__":
    asyncio.run(main())