import asyncio
import json
import sys
import os
from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVER_URL


async def test_free_water_deficit_calculator(client):
    """测试自由水缺失计算器的各种功能和单位转换"""

    def print_header():
        print("\n" + "=" * 60)
        print("自由水缺失计算器测试套件")
        print("=" * 60)

    def print_test_case(i, test_case):
        print(f"\n测试 {i:2d} | {test_case['name']}")
        print(f"- {test_case['description']}")
        print(f"- 输入参数: {test_case['params']}")
        print(f"- 期望结果: {test_case['expected_result']}")

    def print_calculation_result(data):
        """打印完整的计算结果"""
        value = data.get("value", "N/A")
        unit = data.get("unit", "")
        explanation = data.get("explanation", "")
        metadata = data.get("metadata", {})
        
        # 基本结果
        print(f"- 计算结果: {value} {unit}")
        
        # 元数据信息
        if metadata:
            age = metadata.get("age")
            sex = metadata.get("sex") 
            weight = metadata.get("weight")
            sodium = metadata.get("sodium")
            tbw_percentage = metadata.get("tbw_percentage")
            age_category = metadata.get("age_category")
            clinical_note = metadata.get("clinical_note")
            
            if age is not None:
                print(f"- 年龄: {age} years")
            if sex:
                print(f"- 性别: {sex}")
            if weight is not None:
                print(f"- 体重: {weight} kg") 
            if sodium is not None:
                print(f"- 钠离子: {sodium} mmol/L")
            if tbw_percentage is not None:
                print(f"- 总体水分百分比: {tbw_percentage}")
            if age_category:
                print(f"- 年龄分类: {age_category}")
            if clinical_note:
                print(f"- 临床说明: {clinical_note}")

    def print_test_result(i, passed, expected_result, actual_result):
        if passed:
            status = "✅ 通过"
        else:
            status = "❌ 失败"
        print(f"- 测试结果: {status}")
        if not passed:
            print(f"- 期望: {expected_result}, 实际: {actual_result}")
        print("-" * 60)

    def print_summary(total, passed, failed):
        print(f"\n测试总结:")
        print(f"  总测试数: {total}")
        print(f"  通过数: {passed}")
        print(f"  失败数: {failed}")
        print(f"  成功率: {(passed/total*100):.1f}%")

        if failed == 0:
            print("\n✅ 所有测试都通过了！自由水缺失计算器工作正常。")
        else:
            print(f"\n❌ {failed} 个测试失败，请检查实现。")

    # Test statistics
    total_tests = 0
    passed_tests = 0

    # Test cases from data file
    test_cases = [
        {
            "name": "新生儿高钠血症 (3 days, Female)",
            "params": {"sex": "Female", "age": "3 days", "weight": "3040g", "sodium": "153.8 mmol/L"},
            "expected_result": 0.18,
            "tolerance": 0.01,
            "description": "新生儿女婴高钠血症测试",
        },
        {
            "name": "成年男性低钠血症 (63 years, Male)",
            "params": {"age": "63 years", "weight": "99kg", "sex": "Male", "sodium": "137 mmol/L"},
            "expected_result": -1.27,
            "tolerance": 0.07,
            "description": "成年男性轻度低钠血症测试",
        },
        {
            "name": "成年女性低钠血症 (55 years, Female)", 
            "params": {"age": "55 years", "weight": "106.6kg", "sex": "Female", "sodium": "133 mEq/L"},
            "expected_result": -2.67,
            "tolerance": 0.13,
            "description": "成年女性中度低钠血症测试",
        },
        {
            "name": "青少年男性低钠血症 (16 years, Male)",
            "params": {"sex": "Male", "age": "16 years", "weight": "61kg", "sodium": "129 mEq/L"},
            "expected_result": -2.88,
            "tolerance": 0.14,
            "description": "青少年男性中度低钠血症测试",
        },
        {
            "name": "青少年女性轻度低钠血症 (15 years, Female)",
            "params": {"sex": "Female", "age": "15 years", "weight": "41.5kg", "sodium": "135 mmol/L"},
            "expected_result": -0.889,
            "tolerance": 0.044,
            "description": "青少年女性轻度低钠血症测试",
        },
        {
            "name": "成年女性正常钠离子 (53 years, Female)",
            "params": {"age": "53 years", "weight": "100kg", "sex": "Female", "sodium": "140 mEq/L"},
            "expected_result": 0,
            "tolerance": 0.01,
            "description": "成年女性正常钠离子测试",
        },
        {
            "name": "成年男性轻度高钠血症 (22 years, Male)",
            "params": {"sex": "Male", "age": "22 years", "weight": "68kg", "sodium": "141 mmol/L"},
            "expected_result": 0.291,
            "tolerance": 0.015,
            "description": "成年男性轻度高钠血症测试",
        },
        {
            "name": "老年男性低钠血症 (78 years, Male)",
            "params": {"age": "78 years", "weight": "70kg", "sex": "Male", "sodium": "129 mEq/L"},
            "expected_result": -2.75,
            "tolerance": 0.14,
            "description": "老年男性中度低钠血症测试",
        },
        {
            "name": "儿童轻度低钠血症 (4 years, Female)",
            "params": {"age": "4 years", "weight": "8kg", "sex": "Female", "sodium": "135 mEq/L"},
            "expected_result": -0.171,
            "tolerance": 0.009,
            "description": "儿童轻度低钠血症测试",
        },
        {
            "name": "成年男性轻度高钠血症 (51 years, Male)",
            "params": {"age": "51 years", "weight": "68.1kg", "sex": "Male", "sodium": "142 mEq/L"},
            "expected_result": 0.584,
            "tolerance": 0.029,
            "description": "成年男性轻度高钠血症测试",
        },
        {
            "name": "成年男性正常钠离子 (58 years, Male)",
            "params": {"age": "58 years", "weight": "84kg", "sex": "Male", "sodium": "140 mmol/L"},
            "expected_result": 0,
            "tolerance": 0.01,
            "description": "成年男性正常钠离子测试",
        },
        {
            "name": "老年男性轻体重低钠血症 (67 years, Male)",
            "params": {"age": "67 years", "weight": "10kg", "sex": "Male", "sodium": "130 mEq/L"},
            "expected_result": -0.357,
            "tolerance": 0.018,
            "description": "老年男性低体重低钠血症测试",
        },
        {
            "name": "成年男性高体重低钠血症 (41 years, Male)",
            "params": {"age": "41 years", "weight": "140kg", "sex": "Male", "sodium": "137 mEq/L"},
            "expected_result": -1.8,
            "tolerance": 0.09,
            "description": "成年男性高体重低钠血症测试",
        },
        {
            "name": "青少年男性轻度低钠血症 (16 years, Male)",
            "params": {"age": "16 years", "weight": "70kg", "sex": "Male", "sodium": "138 mmol/L"},
            "expected_result": -0.6,
            "tolerance": 0.03,
            "description": "青少年男性轻度低钠血症测试",
        },
        {
            "name": "新生儿男婴严重高钠血症 (9 days, Male)",
            "params": {"age": "9 days", "weight": "2340g", "sex": "Male", "sodium": "195 mEq/L"},
            "expected_result": 0.552,
            "tolerance": 0.028,
            "description": "新生儿男婴严重高钠血症测试",
        },
        {
            "name": "成年男性中度高钠血症 (32 years, Male)",
            "params": {"sex": "Male", "age": "32 years", "weight": "79kg", "sodium": "143 mEq/L"},
            "expected_result": 1.016,
            "tolerance": 0.051,
            "description": "成年男性中度高钠血症测试",
        },
        {
            "name": "青年女性中度低钠血症 (18 years, Female)",
            "params": {"sex": "Female", "age": "18 years", "weight": "35kg", "sodium": "128 mEq/L"},
            "expected_result": -1.5,
            "tolerance": 0.08,
            "description": "青年女性中度低钠血症测试",
        },
        {
            "name": "青年女性严重高钠血症 (19 years, Female)",
            "params": {"sex": "Female", "age": "19 years", "weight": "60.6kg", "sodium": "164 mmol/L"},
            "expected_result": 5.194,
            "tolerance": 0.26,
            "description": "青年女性严重高钠血症测试",
        },
        {
            "name": "青少年男性轻度低钠血症 (14 years, Male)",
            "params": {"age": "14 years", "weight": "38kg", "sex": "Male", "sodium": "136 mEq/L"},
            "expected_result": -0.651,
            "tolerance": 0.033,
            "description": "青少年男性轻度低钠血症测试",
        },
        {
            "name": "青年女性严重低钠血症 (22 years, Female)",
            "params": {"sex": "Female", "age": "22 years", "weight": "40kg", "sodium": "117 mmol/L"},
            "expected_result": -3.29,
            "tolerance": 0.16,
            "description": "青年女性严重低钠血症测试",
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
                    "calculator_id": 38,
                    "parameters": test_case["params"],
                },
            )

            # 使用 structured_content 或 data 属性获取实际数据
            calc_data = calc_result.structured_content or calc_result.data or {}

            if isinstance(calc_data, dict) and calc_data.get("success") and "result" in calc_data:
                # 成功计算
                data = calc_data["result"]
                print_calculation_result(data)

                # 检查结果是否在期望范围内
                actual_result = data.get("value")
                expected_result = test_case["expected_result"]
                tolerance = test_case["tolerance"]
                
                if actual_result is not None:
                    if abs(actual_result - expected_result) <= tolerance:
                        print(f"- 结果验证: ✅ 通过 (期望: {expected_result}, 实际: {actual_result}, 容差: ±{tolerance})")
                    else:
                        print(f"- 结果验证: ❌ 失败 (期望: {expected_result}, 实际: {actual_result}, 容差: ±{tolerance})")
                        test_passed = False
                else:
                    print("- 错误: 无法获取计算结果")
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
                         data.get("value") if 'data' in locals() else "N/A")

    print_summary(total_tests, passed_tests, total_tests - passed_tests)
    return passed_tests, total_tests - passed_tests


async def main():
    def print_header():
        print("自由水缺失计算器 MCP 测试")
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
        print("自由水缺失计算器测试结果")
        print("=" * 60)
        print(f"总测试数: {total_tests}")
        print(f"通过数: {total_passed}")
        print(f"失败数: {total_failed}")
        print(f"成功率: {(total_passed/total_tests*100):.1f}%")

        if total_failed == 0:
            print("\n✅ 自由水缺失计算器所有测试都通过了！")
        else:
            print(f"\n❌ {total_failed} 个测试失败，请检查自由水缺失计算器实现。")

    print_header()

    try:
        async with Client(MCP_SERVER_URL) as client:
            print_connection_status(True)
            passed, failed = await test_free_water_deficit_calculator(client)
            print_overall_results(passed, failed)

    except Exception as e:
        print_connection_status(False, str(e))
        import traceback
        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("✅ 自由水缺失计算器测试完成")


if __name__ == "__main__":
    asyncio.run(main())