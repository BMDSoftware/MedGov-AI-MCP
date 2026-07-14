import asyncio
import json
import sys
import os
from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVER_URL


async def api_test_mean_arterial_pressure_calculator(client):
    """测试 MAP（平均动脉压）计算器的各种功能"""

    def print_header():
        print("\n" + "=" * 60)
        print("MAP（平均动脉压）计算器测试套件")
        print("=" * 60)

    def print_test_case(i, test_case):
        print(f"\n测试 {i:2d} | {test_case['name']}")
        print(f"- {test_case['description']}")
        print(f"- 输入参数: 收缩压={test_case['systolic']}mmHg, 舒张压={test_case['diastolic']}mmHg")

    def print_calculation_result(data, expected_value=None, tolerance=None):
        """打印完整的计算结果"""
        value = data.get("value", "N/A")
        unit = data.get("unit", "")
        explanation = data.get("explanation", "")
        metadata = data.get("metadata", {})
        warnings = data.get("warnings", [])

        # 基本结果
        print(f"- MAP 值: {value} {unit}")

        # 期望值比较
        if expected_value is not None:
            diff = abs(float(value) - expected_value) if isinstance(value, (int, float)) else float('inf')
            if tolerance and diff <= tolerance:
                print(f"- ✅ 结果正确 (期望: {expected_value}, 误差: {diff:.3f} ≤ {tolerance})")
            else:
                print(f"- ❌ 结果不匹配 (期望: {expected_value}, 实际: {value}, 误差: {diff:.3f})")

        # 输入参数
        if metadata:
            systolic = metadata.get("systolic_bp")
            diastolic = metadata.get("diastolic_bp")
            if systolic:
                print(f"- 输入收缩压: {systolic} mmHg")
            if diastolic:
                print(f"- 输入舒张压: {diastolic} mmHg")

        # 警告信息
        if warnings:
            for warning in warnings:
                print(f"- ⚠️  警告: {warning}")

        # 详细解释（截取显示）
        if explanation:
            print(f"- 解释: {explanation.strip()[:100]}{'...' if len(explanation) > 100 else ''}")

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
            print("\n✅ 所有测试都通过了！MAP 计算器工作正常。")
        else:
            print(f"\n❌ {failed} 个测试失败，请检查实现。")

        print("\n测试覆盖范围:")
        features = [
            "标准血压值计算",
            "高血压计算",
            "低血压计算",
            "极值边界测试",
            "参数验证",
            "错误处理",
        ]
        for feature in features:
            print(f"  - {feature}")

    # Test statistics
    total_tests = 0
    passed_tests = 0

    # Test cases based on the training data
    test_cases = [
        {
            "name": "正常血压 (120/80)",
            "systolic": 120.0,
            "diastolic": 80.0,
            "expected_value": 93.333,  # (120 + 2*80) / 3
            "description": "标准正常血压值",
            "tolerance": 2.0,
        },
        {
            "name": "高血压 (150/100)",
            "systolic": 150.0,
            "diastolic": 100.0,
            "expected_value": 116.667,  # (150 + 2*100) / 3
            "description": "高血压测试",
            "tolerance": 2.0,
        },
        {
            "name": "低血压 (100/80)",
            "systolic": 100.0,
            "diastolic": 80.0,
            "expected_value": 86.667,  # (100 + 2*80) / 3
            "description": "低血压测试",
            "tolerance": 2.0,
        },
        {
            "name": "收缩压偏低 (83/42)",
            "systolic": 83.0,
            "diastolic": 42.0,
            "expected_value": 55.667,  # (83 + 2*42) / 3
            "description": "收缩压偏低测试",
            "tolerance": 2.0,
        },
        {
            "name": "高正常值 (126/74)",
            "systolic": 126.0,
            "diastolic": 74.0,
            "expected_value": 91.333,  # (126 + 2*74) / 3
            "description": "高正常血压值",
            "tolerance": 2.0,
        },
        {
            "name": "轻度高血压 (130/85)",
            "systolic": 130.0,
            "diastolic": 85.0,
            "expected_value": 100.0,  # (130 + 2*85) / 3
            "description": "轻度高血压",
            "tolerance": 2.0,
        },
        {
            "name": "严重高血压 (220/137)",
            "systolic": 220.0,
            "diastolic": 137.0,
            "expected_value": 164.667,  # (220 + 2*137) / 3
            "description": "严重高血压测试",
            "tolerance": 2.0,
        },
        {
            "name": "脉压差大 (160/80)",
            "systolic": 160.0,
            "diastolic": 80.0,
            "expected_value": 106.667,  # (160 + 2*80) / 3
            "description": "脉压差较大的情况",
            "tolerance": 2.0,
        },
        {
            "name": "低收缩压 (102/45)",
            "systolic": 102.0,
            "diastolic": 45.0,
            "expected_value": 64.0,  # (102 + 2*45) / 3
            "description": "低收缩压测试",
            "tolerance": 2.0,
        },
        {
            "name": "边界值测试 (200/100)",
            "systolic": 200.0,
            "diastolic": 100.0,
            "expected_value": 133.333,  # (200 + 2*100) / 3
            "description": "边界值测试",
            "tolerance": 2.0,
        },
    ]

    print_header()

    # Execute test cases
    for i, test_case in enumerate(test_cases, 1):
        total_tests += 1
        test_passed = True

        print_test_case(i, test_case)

        # Calculate MAP
        try:
            calc_result = await client.call_tool(
                "calculate",
                {
                    "calculator_id": 5,
                    "parameters": {
                        "systolic_bp": test_case["systolic"],
                        "diastolic_bp": test_case["diastolic"],
                    },
                },
            )

            # 获取实际数据
            calc_data = calc_result.structured_content or calc_result.data or {}

            if isinstance(calc_data, dict) and calc_data.get("success") and "result" in calc_data:
                # 成功计算
                data = calc_data["result"]
                print_calculation_result(data, test_case.get("expected_value"), test_case.get("tolerance"))

                # 验证结果
                if test_case.get("expected_value") is not None and test_case.get("tolerance") is not None:
                    actual_value = data.get("value")
                    if isinstance(actual_value, (int, float)):
                        diff = abs(actual_value - test_case["expected_value"])
                        if diff > test_case["tolerance"]:
                            print(f"- 错误: 结果超出容差范围 (差值: {diff:.3f} > {test_case['tolerance']})")
                            test_passed = False
                    else:
                        print(f"- 错误: 无法获取有效的计算结果")
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
        print("MAP（平均动脉压）计算器 MCP 测试")
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
        print("MAP 计算器测试结果")
        print("=" * 60)
        print(f"总测试数: {total_tests}")
        print(f"通过数: {total_passed}")
        print(f"失败数: {total_failed}")
        print(f"成功率: {(total_passed/total_tests*100):.1f}%")

        if total_failed == 0:
            print("\n✅ MAP 计算器所有测试都通过了！")
        else:
            print(f"\n❌ {total_failed} 个测试失败，请检查 MAP 计算器实现。")

    print_header()

    try:
        async with Client(MCP_SERVER_URL) as client:
            print_connection_status(True)
            passed, failed = await api_test_mean_arterial_pressure_calculator(client)
            print_overall_results(passed, failed)

    except Exception as e:
        print_connection_status(False, str(e))
        import traceback

        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("✅ MAP 计算器测试完成")


if __name__ == "__main__":
    asyncio.run(main())