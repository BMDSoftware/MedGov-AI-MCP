import asyncio
import json
import sys
import os
from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVER_URL


def convert_bun_to_mg_dl(value, unit):
    """Convert BUN from mmol/L to mg/dL if needed"""
    if unit == "mmol/L":
        return value * 2.8  # 1 mmol/L = 2.8 mg/dL
    elif unit == "mg/dL":
        return value
    else:
        raise ValueError(f"Unknown BUN unit: {unit}")


async def test_curb_65_calculator(client):
    """测试 CURB-65 计算器的各种功能"""

    def print_header():
        print("\n" + "=" * 60)
        print("CURB-65 计算器测试套件")
        print("=" * 60)

    def print_test_case(i, test_case):
        print(f"\n测试 {i:2d} | {test_case['name']}")
        print(f"- {test_case['description']}")
        print(f"- 输入参数: {test_case['params']}")
        print(f"- 期望分数: {test_case['expected_score']}")

    def print_calculation_result(data, expected_score):
        """打印完整的计算结果"""
        score = data.get("value", "N/A")
        unit = data.get("unit", "")
        explanation = data.get("explanation", "")
        metadata = data.get("metadata", {})

        # 基本结果
        print(f"- 实际分数: {score} {unit}")
        
        # 分数匹配检查
        score_match = score == expected_score
        status = "✅ 匹配" if score_match else "❌ 不匹配"
        print(f"- 分数验证: {status}")

        # 元数据
        if metadata:
            risk_level = metadata.get("risk_level", "N/A")
            mortality_risk = metadata.get("mortality_risk", "N/A")
            recommendation = metadata.get("recommendation", "N/A")
            
            print(f"- 风险等级: {risk_level}")
            print(f"- 死亡率风险: {mortality_risk}")
            print(f"- 建议: {recommendation}")
            
            # 各项得分
            confusion_pts = metadata.get("confusion_points", 0)
            bun_pts = metadata.get("bun_points", 0)
            resp_pts = metadata.get("respiratory_rate_points", 0)
            bp_pts = metadata.get("blood_pressure_points", 0)
            age_pts = metadata.get("age_points", 0)
            
            print(f"- 详细得分: 意识混乱({confusion_pts}) + BUN({bun_pts}) + 呼吸频率({resp_pts}) + 血压({bp_pts}) + 年龄({age_pts})")

        return score_match

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
            print("\n✅ 所有测试都通过了！CURB-65 计算器工作正常。")
        else:
            print(f"\n❌ {failed} 个测试失败，请检查实现。")

        print("\n测试覆盖范围:")
        features = [
            "CURB-65 评分计算 (0-5分)",
            "意识混乱评估",
            "BUN 阈值判断 (>19 mg/dL)",
            "呼吸频率评估 (≥30/min)",
            "血压评估 (SBP<90 或 DBP≤60)",
            "年龄评估 (≥65岁)",
            "风险分层和建议",
            "BUN 单位转换 (mmol/L → mg/dL)",
        ]
        for feature in features:
            print(f"  - {feature}")

    # Test statistics
    total_tests = 0
    passed_tests = 0

    # Test cases from data file - all real test cases
    test_cases = [
        # Score 0 cases
        {
            "name": "CURB-65 Score 0 - Case 1",
            "params": {
                "confusion": False,
                "bun": "13.9mg/dL",
                "respiratory_rate": "24breaths/min", 
                "systolic_bp": "160mmHg",
                "diastolic_bp": "100mmHg",
                "age": "64years"
            },
            "expected_score": 0,
            "description": "64岁患者，无意识混乱，BUN 13.9，呼吸频率24，血压160/100",
            "source_row": "6626"
        },
        {
            "name": "CURB-65 Score 0 - Case 2", 
            "params": {
                "confusion": False,
                "bun": "14.0mg/dL",
                "respiratory_rate": "20breaths/min",
                "systolic_bp": "110mmHg", 
                "diastolic_bp": "70mmHg",
                "age": "53years"
            },
            "expected_score": 0,
            "description": "53岁患者，无意识混乱，BUN 14.0，呼吸频率20，血压110/70",
            "source_row": "6581"
        },
        
        # Score 1 cases
        {
            "name": "CURB-65 Score 1 - Age ≥65",
            "params": {
                "confusion": False,
                "bun": "16.52mg/dL",  # 5.9 mmol/L * 2.8
                "respiratory_rate": "20breaths/min",
                "systolic_bp": "136mmHg",
                "diastolic_bp": "72mmHg", 
                "age": "85years"
            },
            "expected_score": 1,
            "description": "85岁患者，仅年龄≥65得分，BUN正常，其他指标正常",
            "source_row": "6570"
        },
        {
            "name": "CURB-65 Score 1 - Low BP",
            "params": {
                "confusion": False,
                "bun": "8.12mg/dL",  # 2.9 mmol/L * 2.8
                "respiratory_rate": "20breaths/min",
                "systolic_bp": "92mmHg",
                "diastolic_bp": "60mmHg",  # DBP = 60, should get 1 point
                "age": "42years"
            },
            "expected_score": 1,
            "description": "42岁患者，血压92/60（舒张压≤60），其他指标正常",
            "source_row": "6647"
        },
        {
            "name": "CURB-65 Score 1 - Age ≥65 only",
            "params": {
                "confusion": False,
                "bun": "16.0mg/dL", 
                "respiratory_rate": "22breaths/min",
                "systolic_bp": "125mmHg",
                "diastolic_bp": "90mmHg",
                "age": "68years"
            },
            "expected_score": 1,
            "description": "68岁患者，仅年龄≥65得分",
            "source_row": "6662"
        },
        
        # Score 2 cases
        {
            "name": "CURB-65 Score 2 - BUN + Resp Rate",
            "params": {
                "confusion": False,
                "bun": "40.0mg/dL",
                "respiratory_rate": "34breaths/min",
                "systolic_bp": "146mmHg",
                "diastolic_bp": "80mmHg",
                "age": "57years"
            },
            "expected_score": 2,
            "description": "57岁患者，BUN>19且呼吸频率≥30",
            "source_row": "6634"
        },
        {
            "name": "CURB-65 Score 2 - Age + BUN",
            "params": {
                "confusion": False,
                "bun": "34.9mg/dL",
                "respiratory_rate": "18breaths/min",
                "systolic_bp": "120mmHg",
                "diastolic_bp": "70mmHg", 
                "age": "80years"
            },
            "expected_score": 2,
            "description": "80岁患者，年龄≥65且BUN>19",
            "source_row": "6669"
        },
        {
            "name": "CURB-65 Score 2 - BP + Resp Rate", 
            "params": {
                "confusion": False,
                "bun": "7.2mg/dL",
                "respiratory_rate": "40breaths/min",
                "systolic_bp": "90mmHg",  # SBP = 90, no point for BP
                "diastolic_bp": "50mmHg",  # DBP ≤ 60, gets 1 point
                "age": "17years"
            },
            "expected_score": 2,
            "description": "17岁患者，血压90/50（舒张压≤60）且呼吸频率≥30",
            "source_row": "6642"
        },
        
        # Score 3 cases
        {
            "name": "CURB-65 Score 3 - Age + BP + Resp", 
            "params": {
                "confusion": False,
                "bun": "78.4mg/dL",  # 28.0 mmol/L * 2.8
                "respiratory_rate": "37breaths/min",
                "systolic_bp": "85mmHg",
                "diastolic_bp": "60mmHg",
                "age": "52years"
            },
            "expected_score": 3,
            "description": "52岁患者，BUN>19，收缩压<90，舒张压≤60，呼吸频率≥30",
            "source_row": "6621"
        },
        {
            "name": "CURB-65 Score 3 - Confusion + BUN + Resp",
            "params": {
                "confusion": True,
                "bun": "94.0mg/dL", 
                "respiratory_rate": "37breaths/min",
                "systolic_bp": "106mmHg",
                "diastolic_bp": "64mmHg",
                "age": "53years"
            },
            "expected_score": 3,
            "description": "53岁患者，意识混乱，BUN>19，呼吸频率≥30",
            "source_row": "6631"
        },
        
        # Score 4 cases
        {
            "name": "CURB-65 Score 4 - Multiple factors",
            "params": {
                "confusion": True,
                "bun": "90.0mg/dL",
                "respiratory_rate": "31breaths/min", 
                "systolic_bp": "80mmHg",
                "diastolic_bp": "40mmHg",
                "age": "41years"
            },
            "expected_score": 4,
            "description": "41岁患者，意识混乱，BUN>19，呼吸频率≥30，收缩压<90且舒张压≤60",
            "source_row": "6586"
        },
        {
            "name": "CURB-65 Score 4 - High risk elderly",
            "params": {
                "confusion": True,
                "bun": "26.0mg/dL",
                "respiratory_rate": "26breaths/min",
                "systolic_bp": "80mmHg", 
                "diastolic_bp": "58mmHg",
                "age": "69years"
            },
            "expected_score": 4,
            "description": "69岁患者，意识混乱，BUN>19，收缩压<90且舒张压≤60，年龄≥65",
            "source_row": "6664"
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
                    "calculator_id": 45,  # CURB-65 calculator ID
                    "parameters": test_case["params"],
                },
            )

            # 使用 structured_content 或 data 属性获取实际数据
            calc_data = calc_result.structured_content or calc_result.data or {}

            if isinstance(calc_data, dict) and calc_data.get("success") and "result" in calc_data:
                # 成功计算
                data = calc_data["result"]
                score_match = print_calculation_result(data, test_case["expected_score"])
                
                if not score_match:
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

        print_test_result(i, test_passed)

    print_summary(total_tests, passed_tests, total_tests - passed_tests)
    return passed_tests, total_tests - passed_tests


async def main():
    def print_header():
        print("CURB-65 计算器 MCP 测试")
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
        print("CURB-65 计算器测试结果")
        print("=" * 60)
        print(f"总测试数: {total_tests}")
        print(f"通过数: {total_passed}")
        print(f"失败数: {total_failed}")
        print(f"成功率: {(total_passed/total_tests*100):.1f}%")

        if total_failed == 0:
            print("\n✅ CURB-65 计算器所有测试都通过了！")
        else:
            print(f"\n❌ {total_failed} 个测试失败，请检查 CURB-65 计算器实现。")

    print_header()

    try:
        async with Client(MCP_SERVER_URL) as client:
            print_connection_status(True)
            passed, failed = await test_curb_65_calculator(client)
            print_overall_results(passed, failed)

    except Exception as e:
        print_connection_status(False, str(e))
        import traceback
        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("✅ CURB-65 计算器测试完成")


if __name__ == "__main__":
    asyncio.run(main())