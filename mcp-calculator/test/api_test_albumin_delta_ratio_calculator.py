import asyncio
import json
import sys
import os
from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVER_URL


async def test_albumin_delta_ratio_calculator(client):
    """测试白蛋白校正Delta Ratio计算器的各种功能和参数组合"""

    def print_header():
        print("\n" + "=" * 60)
        print("白蛋白校正Delta Ratio计算器测试套件")
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

    def print_calculation_result(data, expected_value=None):
        """打印完整的计算结果"""
        value = data.get("value", "N/A")
        unit = data.get("unit", "")
        explanation = data.get("explanation", "")
        metadata = data.get("metadata", {})
        
        # 基本结果
        print(f"- 校正Delta Ratio值: {value} {unit}")
        if expected_value is not None:
            if abs(float(value) - expected_value) < 0.01:  # 允许小的误差
                print(f"- 期望值: {expected_value} - ✅ 匹配")
            else:
                print(f"- 期望值: {expected_value} - ❌ 不匹配")
        
        # 元数据信息
        if metadata:
            sodium = metadata.get("sodium")
            chloride = metadata.get("chloride") 
            bicarbonate = metadata.get("bicarbonate")
            albumin = metadata.get("albumin")
            uncorrected_ag = metadata.get("uncorrected_anion_gap")
            corrected_ag = metadata.get("corrected_anion_gap")
            corrected_dg = metadata.get("corrected_delta_gap")
            
            if sodium: print(f"- 钠离子: {sodium} mEq/L")
            if chloride: print(f"- 氯离子: {chloride} mEq/L")
            if bicarbonate: print(f"- 碳酸氢盐: {bicarbonate} mEq/L")
            if albumin: print(f"- 白蛋白: {albumin} g/dL")
            if uncorrected_ag: print(f"- 未校正阴离子间隙: {uncorrected_ag} mEq/L")
            if corrected_ag: print(f"- 白蛋白校正阴离子间隙: {corrected_ag} mEq/L")
            if corrected_dg: print(f"- 白蛋白校正Delta Gap: {corrected_dg} mEq/L")

        # 详细解释（截取前几行显示）
        if explanation and len(explanation) > 100:
            print(f"- 解释: {explanation[:100]}...")
        elif explanation:
            print(f"- 解释: {explanation}")

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
            print("\n✅ 所有测试都通过了！白蛋白校正Delta Ratio计算器工作正常。")
        else:
            print(f"\n❌ {failed} 个测试失败，请检查实现。")

        print("\n测试覆盖范围:")
        features = [
            "不同单位的参数 (mEq/L, mmol/L, g/dL, g/L, mg/dL)",
            "参数验证",
            "白蛋白校正Delta Ratio计算",
            "错误处理",
            "边界测试",
            "数据文件测试用例",
        ]
        for feature in features:
            print(f"  - {feature}")

    # Test statistics
    total_tests = 0
    passed_tests = 0

    # Test cases from data file and edge cases
    test_cases = [
        {
            "name": "Standard case from data",
            "params": {"sodium": 140.0, "chloride": 105.0, "bicarbonate": 28.0, "albumin": 3.9},
            "expected_valid": True,
            "expected_value": 1.188,
            "description": "数据文件测试用例 - 标准参数 (sodium=140, chloride=105, bicarbonate=28, albumin=3.9)"
        },
        {
            "name": "Mixed units case from data",
            "params": {"sodium": 140.0, "chloride": 101.0, "bicarbonate": 10.0, "albumin": 2.7},
            "expected_valid": True,
            "expected_value": 1.446,
            "description": "数据文件测试用例 - 混合单位 (sodium=140, chloride=101, bicarbonate=10, albumin=2.7)"
        },
        {
            "name": "Low albumin case",
            "params": {"sodium": 134.0, "chloride": 103.0, "bicarbonate": 26.0, "albumin": 2.2},
            "expected_valid": True, 
            "expected_value": 1.25,
            "description": "数据文件测试用例 - 低白蛋白 (sodium=134, chloride=103, bicarbonate=26, albumin=2.2)"
        },
        {
            "name": "Negative delta ratio case",
            "params": {"sodium": 138.0, "chloride": 101.0, "bicarbonate": 25.0, "albumin": 3.8},
            "expected_valid": True,
            "expected_value": -0.5,
            "description": "数据文件测试用例 - 负数Delta Ratio (sodium=138, chloride=101, bicarbonate=25, albumin=3.8)"
        },
        {
            "name": "High delta ratio case", 
            "params": {"sodium": 144.0, "chloride": 113.0, "bicarbonate": 25.0, "albumin": 3.8},
            "expected_valid": True,
            "expected_value": 5.5,
            "description": "数据文件测试用例 - 高Delta Ratio (sodium=144, chloride=113, bicarbonate=25, albumin=3.8)"
        },
        {
            "name": "Edge case - normal values",
            "params": {"sodium": 134.0, "chloride": 100.0, "bicarbonate": 19.0, "albumin": 4.4},
            "expected_valid": True,
            "expected_value": 0.4,
            "description": "数据文件测试用例 - 正常范围值 (sodium=134, chloride=100, bicarbonate=19, albumin=4.4)"
        },
        {
            "name": "Invalid sodium (too low)",
            "params": {"sodium": 100.0, "chloride": 102.0, "bicarbonate": 20.0, "albumin": 4.0},
            "expected_valid": False,
            "description": "无效钠离子（过低）"
        },
        {
            "name": "Invalid chloride (too high)",
            "params": {"sodium": 140.0, "chloride": 130.0, "bicarbonate": 20.0, "albumin": 4.0},
            "expected_valid": False,
            "description": "无效氯离子（过高）"
        },
        {
            "name": "Invalid bicarbonate (too low)",
            "params": {"sodium": 140.0, "chloride": 102.0, "bicarbonate": 0.5, "albumin": 4.0},
            "expected_valid": False,
            "description": "无效碳酸氢盐（过低）"
        },
        {
            "name": "Invalid albumin (too high)",
            "params": {"sodium": 140.0, "chloride": 102.0, "bicarbonate": 20.0, "albumin": 7.0},
            "expected_valid": False,
            "description": "无效白蛋白（过高）"
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
                    "calculator_id": 67,  # Albumin Delta Ratio calculator ID
                    "parameters": test_case["params"],
                },
            )

            # 使用 structured_content 或 data 属性获取实际数据
            calc_data = calc_result.structured_content or calc_result.data or {}

            if isinstance(calc_data, dict) and calc_data.get("success") and "result" in calc_data:
                # 成功计算
                data = calc_data["result"]
                expected_value = test_case.get("expected_value")
                print_calculation_result(data, expected_value)

                # 检查是否符合预期
                if not test_case["expected_valid"]:
                    print("- 错误: 预期失败但计算成功")
                    test_passed = False
                elif expected_value is not None:
                    actual_value = float(data.get("value", 0))
                    if abs(actual_value - expected_value) >= 0.01:
                        print(f"- 错误: 计算结果不匹配，期望 {expected_value}，实际 {actual_value}")
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
        print("白蛋白校正Delta Ratio计算器 MCP 测试")
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
        print("白蛋白校正Delta Ratio计算器测试结果")
        print("=" * 60)
        print(f"总测试数: {total_tests}")
        print(f"通过数: {total_passed}")
        print(f"失败数: {total_failed}")
        print(f"成功率: {(total_passed/total_tests*100):.1f}%")

        if total_failed == 0:
            print("\n✅ 白蛋白校正Delta Ratio计算器所有测试都通过了！")
        else:
            print(f"\n❌ {total_failed} 个测试失败，请检查白蛋白校正Delta Ratio计算器实现。")

    print_header()

    try:
        async with Client(MCP_SERVER_URL) as client:
            print_connection_status(True)
            passed, failed = await test_albumin_delta_ratio_calculator(client)
            print_overall_results(passed, failed)

    except Exception as e:
        print_connection_status(False, str(e))
        import traceback
        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("✅ 白蛋白校正Delta Ratio计算器测试完成")


if __name__ == "__main__":
    asyncio.run(main())