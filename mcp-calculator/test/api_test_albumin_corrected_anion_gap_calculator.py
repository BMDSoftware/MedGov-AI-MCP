import asyncio
import json
import sys
import os
from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVER_URL


async def test_albumin_corrected_anion_gap_calculator(client):
    """测试白蛋白校正阴离子间隙计算器的各种功能和参数验证"""

    def print_header():
        print("\n" + "=" * 70)
        print("白蛋白校正阴离子间隙计算器测试套件")
        print("=" * 70)

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
            print(f"- ⚠️ 错误: {errors}")
        if warnings:
            print(f"- ⚠️ 警告: {warnings}")

    def print_calculation_result(data, expected_value=None):
        """打印完整的计算结果"""
        value = data.get("value", "N/A")
        unit = data.get("unit", "")
        explanation = data.get("explanation", "")
        metadata = data.get("metadata", {})
        warnings = data.get("warnings", [])

        # 基本结果
        print(f"- 计算结果: {value} {unit}")
        if expected_value is not None:
            print(f"- 期望值: {expected_value}")
            if isinstance(value, (int, float)) and abs(value - expected_value) <= 0.1:
                print("- ✅ 结果匹配期望值")
            else:
                print("- ❌ 结果与期望值不匹配")

        # 元数据
        if metadata:
            sodium = metadata.get("sodium")
            chloride = metadata.get("chloride") 
            bicarbonate = metadata.get("bicarbonate")
            albumin = metadata.get("albumin")
            uncorrected_ag = metadata.get("uncorrected_anion_gap")
            formula = metadata.get("formula")

            if sodium and chloride and bicarbonate and albumin:
                print(f"- 输入值: Na={sodium}, Cl={chloride}, HCO3={bicarbonate}, Alb={albumin}")
            if uncorrected_ag is not None:
                print(f"- 未校正阴离子间隙: {uncorrected_ag}")
            if formula:
                print(f"- 公式: {formula}")

        # 警告信息
        if warnings:
            for warning in warnings:
                print(f"- ⚠️ 警告: {warning}")

        # 详细解释（截取前几行显示）
        if explanation:
            lines = explanation.strip().split('\n')[:3]
            print(f"- 解释: {' '.join(lines)[:100]}...")

    def print_test_result(i, passed):
        if passed:
            status = "✅ 通过"
        else:
            status = "❌ 失败"
        print(f"- 测试结果: {status}")
        print("-" * 70)

    def print_summary(total, passed, failed):
        print(f"\n测试总结:")
        print(f"  总测试数: {total}")
        print(f"  通过数: {passed}")
        print(f"  失败数: {failed}")
        print(f"  成功率: {(passed/total*100):.1f}%")

        if failed == 0:
            print("\n✅ 所有测试都通过了！白蛋白校正阴离子间隙计算器工作正常。")
        else:
            print(f"\n❌ {failed} 个测试失败，请检查实现。")

        print("\n测试覆盖范围:")
        features = [
            "标准参数计算 (mEq/L, g/dL)",
            "参数验证 (范围检查)",
            "阴离子间隙计算公式",
            "白蛋白校正公式", 
            "错误处理",
            "边界测试",
            "元数据完整性",
        ]
        for feature in features:
            print(f"  - {feature}")

    # Test statistics
    total_tests = 0
    passed_tests = 0

    # Test cases based on training data
    test_cases = [
        {
            "name": "Standard case 1 (Training data row 9529)",
            "params": {"sodium": "139", "chloride": "104", "bicarbonate": "27", "albumin": "3.4"},
            "expected_valid": True,
            "expected_value": 9.5,
            "description": "标准计算：Na=139, Cl=104, HCO3=27, Alb=3.4",
        },
        {
            "name": "Standard case 2 (Training data row 9488)",
            "params": {"sodium": "133", "chloride": "103", "bicarbonate": "23", "albumin": "4.3"},
            "expected_valid": True,
            "expected_value": 6.25,
            "description": "标准计算：Na=133, Cl=103, HCO3=23, Alb=4.3",
        },
        {
            "name": "High albumin case (Training data row 9474)",
            "params": {"sodium": "134", "chloride": "100", "bicarbonate": "19", "albumin": "4.4"},
            "expected_valid": True,
            "expected_value": 14.0,
            "description": "高白蛋白：Na=134, Cl=100, HCO3=19, Alb=4.4",
        },
        {
            "name": "Low albumin case (Training data row 9537)",
            "params": {"sodium": "136", "chloride": "105", "bicarbonate": "21", "albumin": "2.2"},
            "expected_valid": True,
            "expected_value": 14.5,
            "description": "低白蛋白：Na=136, Cl=105, HCO3=21, Alb=2.2",
        },
        {
            "name": "Negative anion gap case (Training data row 9518)",
            "params": {"sodium": "132", "chloride": "132", "bicarbonate": "18", "albumin": "3.8"},
            "expected_valid": True,
            "expected_value": -17.5,
            "description": "负阴离子间隙：Na=132, Cl=132, HCO3=18, Alb=3.8",
        },
        {
            "name": "Invalid sodium (too low)",
            "params": {"sodium": "100", "chloride": "104", "bicarbonate": "27", "albumin": "3.4"},
            "expected_valid": False,
            "description": "无效钠离子（过低）：Na=100",
        },
        {
            "name": "Invalid sodium (too high)",
            "params": {"sodium": "190", "chloride": "104", "bicarbonate": "27", "albumin": "3.4"},
            "expected_valid": False,
            "description": "无效钠离子（过高）：Na=190",
        },
        {
            "name": "Invalid chloride (too low)",
            "params": {"sodium": "139", "chloride": "50", "bicarbonate": "27", "albumin": "3.4"},
            "expected_valid": False,
            "description": "无效氯离子（过低）：Cl=50",
        },
        {
            "name": "Invalid chloride (too high)",
            "params": {"sodium": "139", "chloride": "140", "bicarbonate": "27", "albumin": "3.4"},
            "expected_valid": False,
            "description": "无效氯离子（过高）：Cl=140",
        },
        {
            "name": "Invalid bicarbonate (too low)",
            "params": {"sodium": "139", "chloride": "104", "bicarbonate": "1", "albumin": "3.4"},
            "expected_valid": False,
            "description": "无效碳酸氢盐（过低）：HCO3=1",
        },
        {
            "name": "Invalid bicarbonate (too high)",
            "params": {"sodium": "139", "chloride": "104", "bicarbonate": "50", "albumin": "3.4"},
            "expected_valid": False,
            "description": "无效碳酸氢盐（过高）：HCO3=50",
        },
        {
            "name": "Invalid albumin (too low)",
            "params": {"sodium": "139", "chloride": "104", "bicarbonate": "27", "albumin": "0.5"},
            "expected_valid": False,
            "description": "无效白蛋白（过低）：Alb=0.5",
        },
        {
            "name": "Invalid albumin (too high)",
            "params": {"sodium": "139", "chloride": "104", "bicarbonate": "27", "albumin": "7.0"},
            "expected_valid": False,
            "description": "无效白蛋白（过高）：Alb=7.0",
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
                    "calculator_id": 65,  # Albumin Corrected Anion Gap Calculator ID
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
                    actual_value = data.get("value")
                    if actual_value is None or abs(actual_value - expected_value) > 0.1:
                        print(f"- 错误: 期望值{expected_value}，实际值{actual_value}")
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
        print("白蛋白校正阴离子间隙计算器 MCP 测试")
        print("=" * 70)

    def print_connection_status(success, error=None):
        if success:
            print("[OK] 成功连接到 MCP 服务器")
        else:
            print(f"[ERROR] 连接失败: {error}")

    def print_overall_results(total_passed, total_failed):
        total_tests = total_passed + total_failed
        if total_tests == 0:
            return

        print("\n" + "=" * 70)
        print("白蛋白校正阴离子间隙计算器测试结果")
        print("=" * 70)
        print(f"总测试数: {total_tests}")
        print(f"通过数: {total_passed}")
        print(f"失败数: {total_failed}")
        print(f"成功率: {(total_passed/total_tests*100):.1f}%")

        if total_failed == 0:
            print("\n✅ 白蛋白校正阴离子间隙计算器所有测试都通过了！")
        else:
            print(f"\n❌ {total_failed} 个测试失败，请检查白蛋白校正阴离子间隙计算器实现。")

    print_header()

    try:
        async with Client(MCP_SERVER_URL) as client:
            print_connection_status(True)
            passed, failed = await test_albumin_corrected_anion_gap_calculator(client)
            print_overall_results(passed, failed)

    except Exception as e:
        print_connection_status(False, str(e))
        import traceback

        traceback.print_exc()
        return

    print("\n" + "=" * 70)
    print("[DONE] 白蛋白校正阴离子间隙计算器测试完成")


if __name__ == "__main__":
    asyncio.run(main())