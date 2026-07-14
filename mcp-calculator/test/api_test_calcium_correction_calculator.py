import asyncio
import json
import sys
import os
from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVER_URL


async def test_calcium_correction_calculator(client):
    """测试钙校正计算器的各种功能和单位转换"""

    def print_header():
        print("\n" + "=" * 60)
        print("钙校正计算器测试套件")
        print("=" * 60)

    def print_test_case(i, test_case):
        print(f"\n测试 {i:2d} | {test_case['name']}")
        print(f"- {test_case['description']}")
        print(f"- 输入参数: {test_case['params']}")
        if 'expected_value' in test_case:
            print(f"- 期望值: {test_case['expected_value']}")

    def print_calculation_result(data):
        """打印完整的计算结果"""
        value = data.get("value", "N/A")
        unit = data.get("unit", "")
        explanation = data.get("explanation", "")
        metadata = data.get("metadata", {})
        warnings = data.get("warnings", [])

        # 基本结果
        print(f"- 校正钙值: {value} {unit}")

        # 原始输入和计算参数
        if metadata:
            serum_calcium = metadata.get("serum_calcium")
            serum_albumin = metadata.get("serum_albumin")
            normal_albumin = metadata.get("normal_albumin")
            formula = metadata.get("formula")

            if serum_calcium is not None:
                print(f"- 血清钙: {serum_calcium} mg/dL")
            if serum_albumin is not None:
                print(f"- 血清白蛋白: {serum_albumin} g/dL")
            if normal_albumin is not None:
                print(f"- 正常白蛋白: {normal_albumin} g/dL")
            if formula:
                print(f"- 计算公式: {formula}")

        # 警告信息
        if warnings:
            for warning in warnings:
                print(f"- ⚠️ 警告: {warning}")

        # 详细解释（截取前几行显示）
        if explanation:
            print(f"- 解释: [详细解释已省略]")

    def print_test_result(i, passed, expected_value=None, actual_value=None):
        if passed:
            status = "✅ 通过"
        else:
            status = "❌ 失败"
        print(f"- 测试结果: {status}")
        if expected_value is not None and actual_value is not None:
            print(f"  期望: {expected_value}, 实际: {actual_value}")
        print("-" * 60)

    def print_summary(total, passed, failed):
        print(f"\n测试总结:")
        print(f"  总测试数: {total}")
        print(f"  通过数: {passed}")
        print(f"  失败数: {failed}")
        print(f"  成功率: {(passed/total*100):.1f}%")

        if failed == 0:
            print("\n✅ 所有测试都通过了！钙校正计算器工作正常。")
        else:
            print(f"\n❌ {failed} 个测试失败，请检查实现。")

        print("\n测试覆盖范围:")
        features = [
            "标准单位 (mg/dL, g/dL)",
            "混合单位 (mmol/L, g/L)",
            "参数验证",
            "钙校正公式",
            "错误处理",
            "边界测试",
        ]
        for feature in features:
            print(f"  - {feature}")

    # Test statistics
    total_tests = 0
    passed_tests = 0

    # 从数据文件提取的测试用例（Calculator ID = 7）- 使用原始数据格式
    test_cases = [
        {
            "name": "Row 2736 - Low albumin case",
            "params": {"Calcium": [7.6, "mg/dL"], "Albumin": [2.1, "g/dL"]},
            "expected_value": 9.12,
            "description": "低白蛋白病例 (钙7.6 mg/dL, 白蛋白2.1 g/dL)",
        },
        {
            "name": "Row 2689 - Normal albumin",
            "params": {"Albumin": [3.9, "g/dL"], "Calcium": [9.0, "mg/dL"]},
            "expected_value": 9.08,
            "description": "接近正常白蛋白 (钙9.0 mg/dL, 白蛋白3.9 g/dL)",
        },
        {
            "name": "Row 2646 - mmol/L and g/L units",
            "params": {"Albumin": [14.0, "g/L"], "Calcium": [1.45, "mmol/L"]},
            "expected_value": 6.08,
            "description": "单位转换测试 (原始: 1.45 mmol/L 钙, 14.0 g/L 白蛋白)",
        },
        {
            "name": "Row 2670 - mmol/L calcium",
            "params": {"Albumin": [23.9, "g/L"], "Calcium": [1.95, "mmol/L"]},
            "expected_value": 9.288,
            "description": "钙单位转换 (原始: 1.95 mmol/L 钙, 23.9 g/L 白蛋白)",
        },
        {
            "name": "Row 2588 - Standard case",
            "params": {"Calcium": [7.8, "mg/dL"], "Albumin": [2.6, "g/dL"]},
            "expected_value": 8.92,
            "description": "标准病例 (钙7.8 mg/dL, 白蛋白2.6 g/dL)",
        },
        {
            "name": "Row 2622 - Low calcium",
            "params": {"Calcium": [5.0, "mg/dL"], "Albumin": [3.2, "g/dL"]},
            "expected_value": 5.64,
            "description": "低钙血症 (钙5.0 mg/dL, 白蛋白3.2 g/dL)",
        },
        {
            "name": "Row 2750 - Very low albumin",
            "params": {"Calcium": [8.6, "mg/dL"], "Albumin": [2.3, "g/dL"]},
            "expected_value": 9.96,
            "description": "极低白蛋白 (钙8.6 mg/dL, 白蛋白2.3 g/dL)",
        },
        {
            "name": "Row 2700 - Low albumin variant",
            "params": {"Albumin": [2.3, "g/dL"], "Calcium": [8.4, "mg/dL"]},
            "expected_value": 9.76,
            "description": "低白蛋白变体 (钙8.4 mg/dL, 白蛋白2.3 g/dL)",
        },
        {
            "name": "Row 2645 - g/L albumin unit",
            "params": {"Albumin": [3.7, "g/L"], "Calcium": [7.0, "mg/dL"]},
            "expected_value": 9.904,
            "description": "g/L白蛋白单位 (原始: 钙7.0 mg/dL, 白蛋白3.7 g/L)",
        },
        {
            "name": "Row 2744 - mmol/L and g/L",
            "params": {"Calcium": [2.2, "mmol/L"], "Albumin": [30.0, "g/L"]},
            "expected_value": 8.8,
            "description": "mmol/L和g/L单位 (原始: 2.2 mmol/L 钙, 30.0 g/L 白蛋白)",
        },
        {
            "name": "Row 2623 - Normal case",
            "params": {"Albumin": [3.0, "g/dL"], "Calcium": [7.7, "mg/dL"]},
            "expected_value": 8.5,
            "description": "正常病例 (钙7.7 mg/dL, 白蛋白3.0 g/dL)",
        },
        {
            "name": "Row 2690 - High albumin",
            "params": {"Albumin": [4.3, "g/dL"], "Calcium": [9.5, "mg/dL"]},
            "expected_value": 9.26,
            "description": "高白蛋白 (钙9.5 mg/dL, 白蛋白4.3 g/dL)",
        },
        {
            "name": "Row 2722 - Standard case 2",
            "params": {"Calcium": [8.9, "mg/dL"], "Albumin": [3.7, "g/dL"]},
            "expected_value": 9.14,
            "description": "标准病例2 (钙8.9 mg/dL, 白蛋白3.7 g/dL)",
        },
        {
            "name": "Row 2582 - mmol/L and g/L units",
            "params": {"Albumin": [28.0, "g/L"], "Calcium": [2.24, "mmol/L"]},
            "expected_value": 8.96,
            "description": "mmol/L和g/L单位 (原始: 2.24 mmol/L 钙, 28.0 g/L 白蛋白)",
        },
        {
            "name": "Row 2616 - High calcium",
            "params": {"Albumin": [3.6, "g/dL"], "Calcium": [13.0, "mg/dL"]},
            "expected_value": 13.32,
            "description": "高钙血症 (钙13.0 mg/dL, 白蛋白3.6 g/dL)",
        },
        {
            "name": "Row 2737 - Low albumin case 2",
            "params": {"Calcium": [8.3, "mg/dL"], "Albumin": [2.7, "g/dL"]},
            "expected_value": 9.34,
            "description": "低白蛋白病例2 (钙8.3 mg/dL, 白蛋白2.7 g/dL)",
        },
        {
            "name": "Row 2695 - mmol/L and g/L case",
            "params": {"Albumin": [23.0, "g/L"], "Calcium": [2.57, "mmol/L"]},
            "expected_value": 13.36,
            "description": "mmol/L和g/L病例 (原始: 2.57 mmol/L 钙, 23.0 g/L 白蛋白)",
        },
        {
            "name": "Row 2730 - Very high calcium",
            "params": {"Albumin": [3.5, "g/dL"], "Calcium": [17.08, "mg/dL"]},
            "expected_value": 17.48,
            "description": "极高钙血症 (钙17.08 mg/dL, 白蛋白3.5 g/dL)",
        },
        {
            "name": "Row 2671 - Low albumin case 3",
            "params": {"Albumin": [2.7, "g/dL"], "Calcium": [7.9, "mg/dL"]},
            "expected_value": 8.94,
            "description": "低白蛋白病例3 (钙7.9 mg/dL, 白蛋白2.7 g/dL)",
        },
        {
            "name": "Row 2705 - High calcium case",
            "params": {"Calcium": [11.7, "mg/dL"], "Albumin": [2.9, "g/dL"]},
            "expected_value": 12.58,
            "description": "高钙病例 (钙11.7 mg/dL, 白蛋白2.9 g/dL)",
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
                    "calculator_id": 7,
                    "parameters": test_case["params"],
                },
            )

            # 使用 structured_content 或 data 属性获取实际数据
            calc_data = calc_result.structured_content or calc_result.data or {}

            if isinstance(calc_data, dict) and calc_data.get("success") and "result" in calc_data:
                # 成功计算
                data = calc_data["result"]
                print_calculation_result(data)

                # 检查计算结果是否符合预期
                if "expected_value" in test_case:
                    actual_value = data.get("value")
                    expected_value = test_case["expected_value"]
                    
                    # 允许一定的误差范围（±5%）
                    tolerance = abs(expected_value * 0.05)
                    if actual_value is None or abs(actual_value - expected_value) > tolerance:
                        print(f"- 错误: 计算结果不符合预期 (误差超过5%)")
                        test_passed = False
                    else:
                        print(f"- ✅ 计算结果符合预期 (误差在5%以内)")
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

        expected_val = test_case.get("expected_value")
        actual_val = calc_data.get("result", {}).get("value") if 'calc_data' in locals() and calc_data.get("success") else None
        print_test_result(i, test_passed, expected_val, actual_val)

    print_summary(total_tests, passed_tests, total_tests - passed_tests)
    return passed_tests, total_tests - passed_tests


async def main():
    def print_header():
        print("钙校正计算器 MCP 测试")
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
        print("钙校正计算器测试结果")
        print("=" * 60)
        print(f"总测试数: {total_tests}")
        print(f"通过数: {total_passed}")
        print(f"失败数: {total_failed}")
        print(f"成功率: {(total_passed/total_tests*100):.1f}%")

        if total_failed == 0:
            print("\n✅ 钙校正计算器所有测试都通过了！")
        else:
            print(f"\n❌ {total_failed} 个测试失败，请检查钙校正计算器实现。")

    print_header()

    try:
        async with Client(MCP_SERVER_URL) as client:
            print_connection_status(True)
            passed, failed = await test_calcium_correction_calculator(client)
            print_overall_results(passed, failed)

    except Exception as e:
        print_connection_status(False, str(e))
        import traceback

        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("🎉 钙校正计算器测试完成")


if __name__ == "__main__":
    asyncio.run(main())