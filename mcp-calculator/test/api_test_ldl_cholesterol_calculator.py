import asyncio
import json
import sys
import os
from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVER_URL


async def test_ldl_cholesterol_calculator(client):
    """测试 LDL 胆固醇计算器的各种功能和单位转换"""

    def print_header():
        print("\n" + "=" * 60)
        print("LDL 胆固醇计算器测试套件")
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

    def print_calculation_result(data, expected_value=None, lower_limit=None, upper_limit=None):
        """打印完整的计算结果"""
        ldl_value = data.get("value", "N/A")
        unit = data.get("unit", "")
        explanation = data.get("explanation", "")
        metadata = data.get("metadata", {})
        warnings = data.get("warnings", [])

        # 基本结果
        print(f"- LDL 值: {ldl_value} {unit}")

        # 期望值和范围检查
        if expected_value is not None:
            print(f"- 期望值: {expected_value} {unit}")
            if lower_limit is not None and upper_limit is not None:
                print(f"- 期望范围: {lower_limit} - {upper_limit} {unit}")
                if isinstance(ldl_value, (int, float)) and lower_limit <= ldl_value <= upper_limit:
                    print("- ✅ 结果在期望范围内")
                else:
                    print("- ❌ 结果超出期望范围")

        # 元数据
        if metadata:
            total_cholesterol = metadata.get("total_cholesterol")
            hdl_cholesterol = metadata.get("hdl_cholesterol")
            triglycerides = metadata.get("triglycerides")
            clinical_note = metadata.get("clinical_note", "N/A")

            if total_cholesterol:
                print(f"- 总胆固醇: {total_cholesterol} mg/dL")
            if hdl_cholesterol:
                print(f"- HDL胆固醇: {hdl_cholesterol} mg/dL")
            if triglycerides:
                print(f"- 甘油三酯: {triglycerides} mg/dL")
            if clinical_note:
                print(f"- 临床意义: {clinical_note}")

        # 警告信息
        if warnings:
            for warning in warnings:
                print(f"- ⚠️  警告: {warning}")

        # 详细解释（截取前几行显示）
        if explanation:
            lines = explanation.split('\n')[:3]
            print(f"- 解释: {' '.join(lines)}")

    def print_test_result(i, passed, error_msg=None):
        if passed:
            status = "✅ 通过"
        else:
            status = "❌ 失败"
        print(f"- 测试结果: {status}")
        if error_msg:
            print(f"- 错误信息: {error_msg}")
        print("-" * 60)

    def print_summary(total, passed, failed):
        print(f"\n测试总结:")
        print(f"  总测试数: {total}")
        print(f"  通过数: {passed}")
        print(f"  失败数: {failed}")
        print(f"  成功率: {(passed/total*100):.1f}%")

        if failed == 0:
            print("\n✅ 所有测试都通过了！LDL 胆固醇计算器工作正常。")
        else:
            print(f"\n❌ {failed} 个测试失败，请检查实现。")

        print("\n测试覆盖范围:")
        features = [
            "Friedewald 公式计算",
            "多种单位支持 (mg/dL, mmol/L)",
            "参数验证",
            "临床分类",
            "错误处理",
            "边界测试",
            "甘油三酯高值警告",
        ]
        for feature in features:
            print(f"  - {feature}")

    def convert_mmol_to_mgdl(value, cholesterol_type):
        """将 mmol/L 转换为 mg/dL - 使用更精确的转换系数"""
        if cholesterol_type == "cholesterol":
            # 胆固醇: 1 mmol/L = 38.66 mg/dL (更接近标准值)
            return value * 38.66
        elif cholesterol_type == "triglycerides":
            # 甘油三酯: 1 mmol/L = 88.50 mg/dL (调整后的系数)  
            return value * 88.50
        return value

    def map_parameters(params):
        """映射数据文件中的参数名到计算器期望的参数名，保持原始单位"""
        mapped_params = {}
        
        for key, value in params.items():
            if key == "Total cholesterol":
                mapped_params["total_cholesterol"] = value
            elif key == "high-density lipoprotein cholesterol":
                mapped_params["hdl_cholesterol"] = value
            elif key == "Triglycerides":
                mapped_params["triglycerides"] = value
        
        return mapped_params

    # Test statistics
    total_tests = 0
    passed_tests = 0

    # Test cases from data file - 真实测试数据
    test_cases_from_data = [
        {
            "name": "Standard case 1",
            "params": {"Total cholesterol": [170.0, "mg/dL"], "high-density lipoprotein cholesterol": [51.0, "mg/dL"], "Triglycerides": [98.0, "mg/dL"]},
            "expected_valid": True,
            "expected_value": 99.4,
            "lower_limit": 94.43,
            "upper_limit": 104.37,
            "description": "标准案例 1 - 来自数据文件",
        },
        {
            "name": "Standard case 2",
            "params": {"high-density lipoprotein cholesterol": [32.0, "mg/dL"], "Triglycerides": [88.0, "mg/dL"], "Total cholesterol": [145.0, "mg/dL"]},
            "expected_valid": True,
            "expected_value": 95.4,
            "lower_limit": 90.63,
            "upper_limit": 100.17,
            "description": "标准案例 2 - 来自数据文件",
        },
        {
            "name": "mmol/L units case",
            "params": {"Total cholesterol": [4.6, "mmol/L"], "high-density lipoprotein cholesterol": [0.8, "mmol/L"], "Triglycerides": [3.9, "mmol/L"]},
            "expected_valid": True,
            "expected_value": 93.5,
            "lower_limit": 88.825,
            "upper_limit": 98.175,
            "description": "mmol/L 单位测试 - 来自数据文件",
        },
        {
            "name": "Normal LDL case",
            "params": {"Total cholesterol": [167.0, "mg/dL"], "high-density lipoprotein cholesterol": [42.0, "mg/dL"], "Triglycerides": [77.0, "mg/dL"]},
            "expected_valid": True,
            "expected_value": 109.6,
            "lower_limit": 104.12,
            "upper_limit": 115.08,
            "description": "正常 LDL 案例 - 来自数据文件",
        },
        {
            "name": "Low LDL case",
            "params": {"high-density lipoprotein cholesterol": [0.57, "mmol/L"], "Triglycerides": [2.28, "mmol/L"], "Total cholesterol": [2.86, "mmol/L"]},
            "expected_valid": True,
            "expected_value": 59.54,
            "lower_limit": 56.563,
            "upper_limit": 62.517,
            "description": "低 LDL 案例 (mmol/L) - 来自数据文件",
        },
        {
            "name": "Very low LDL case",
            "params": {"high-density lipoprotein cholesterol": [37.44, "mg/dL"], "Triglycerides": [20.7, "mg/dL"], "Total cholesterol": [92.16, "mg/dL"]},
            "expected_valid": True,
            "expected_value": 50.58,
            "lower_limit": 48.051,
            "upper_limit": 53.109,
            "description": "极低 LDL 案例 - 来自数据文件",
        },
        {
            "name": "High LDL case",
            "params": {"high-density lipoprotein cholesterol": [55.0, "mg/dL"], "Triglycerides": [100.0, "mg/dL"], "Total cholesterol": [315.0, "mg/dL"]},
            "expected_valid": True,
            "expected_value": 240.0,
            "lower_limit": 228.0,
            "upper_limit": 252.0,
            "description": "高 LDL 案例 - 来自数据文件",
        },
        {
            "name": "High triglycerides case",
            "params": {"Total cholesterol": [208.0, "mg/dL"], "Triglycerides": [207.0, "mg/dL"], "high-density lipoprotein cholesterol": [46.0, "mg/dL"]},
            "expected_valid": True,
            "expected_value": 120.6,
            "lower_limit": 114.57,
            "upper_limit": 126.63,
            "description": "高甘油三酯案例 - 来自数据文件",
        },
        {
            "name": "Moderate triglycerides case",
            "params": {"high-density lipoprotein cholesterol": [36.0, "mg/dL"], "Triglycerides": [197.0, "mg/dL"], "Total cholesterol": [121.0, "mg/dL"]},
            "expected_valid": True,
            "expected_value": 45.6,
            "lower_limit": 43.32,
            "upper_limit": 47.88,
            "description": "中等甘油三酯案例 - 来自数据文件",
        },
        {
            "name": "Very high LDL case",
            "params": {"Total cholesterol": [335.0, "mg/dL"], "high-density lipoprotein cholesterol": [45.0, "mg/dL"], "Triglycerides": [211.0, "mg/dL"]},
            "expected_valid": True,
            "expected_value": 247.8,
            "lower_limit": 235.41,
            "upper_limit": 260.19,
            "description": "极高 LDL 案例 - 来自数据文件",
        }
    ]

    # Additional validation test cases
    additional_test_cases = [
        {
            "name": "Very low total cholesterol (edge case)",
            "params": {"total_cholesterol": 30, "hdl_cholesterol": 40, "triglycerides": 100},
            "expected_valid": False,
            "description": "总胆固醇过低（边界外）",
        },
        {
            "name": "Very low HDL cholesterol (edge case)", 
            "params": {"total_cholesterol": 200, "hdl_cholesterol": 5, "triglycerides": 100},
            "expected_valid": False,
            "description": "HDL胆固醇过低（边界外）",
        },
        {
            "name": "Invalid triglycerides (too high)",
            "params": {"total_cholesterol": 200, "hdl_cholesterol": 40, "triglycerides": 1200},
            "expected_valid": False,
            "description": "无效甘油三酯（过高）",
        },
        {
            "name": "High triglycerides with warning",
            "params": {"total_cholesterol": 250, "hdl_cholesterol": 45, "triglycerides": 450},
            "expected_valid": True,
            "description": "高甘油三酯警告案例（>400，应该计算但带警告）",
        }
    ]

    print_header()

    # Execute test cases from data
    all_test_cases = test_cases_from_data + additional_test_cases
    
    for i, test_case in enumerate(all_test_cases, 1):
        total_tests += 1
        test_passed = True
        error_msg = None

        print_test_case(i, test_case)

        # 映射参数（如果需要）
        if "params" in test_case and any(isinstance(v, list) for v in test_case["params"].values()):
            # 来自数据文件的测试案例，需要映射参数名
            mapped_params = map_parameters(test_case["params"])
        else:
            # 额外的验证测试案例，直接使用
            mapped_params = test_case["params"]

        # Calculation test
        try:
            calc_result = await client.call_tool(
                "calculate",
                {
                    "calculator_id": 44,
                    "parameters": mapped_params,
                },
            )

            # 使用 structured_content 或 data 属性获取实际数据
            calc_data = calc_result.structured_content or calc_result.data or {}

            if isinstance(calc_data, dict) and calc_data.get("success") and "result" in calc_data:
                # 成功计算
                data = calc_data["result"]
                expected_value = test_case.get("expected_value")
                lower_limit = test_case.get("lower_limit")
                upper_limit = test_case.get("upper_limit")
                
                print_calculation_result(data, expected_value, lower_limit, upper_limit)

                # 检查是否符合预期
                if not test_case["expected_valid"]:
                    error_msg = "预期失败但计算成功"
                    test_passed = False
                elif expected_value is not None and lower_limit is not None and upper_limit is not None:
                    # 检查结果是否在期望范围内
                    ldl_value = data.get("value")
                    if not isinstance(ldl_value, (int, float)) or not (lower_limit <= ldl_value <= upper_limit):
                        error_msg = f"结果 {ldl_value} 不在期望范围 [{lower_limit}, {upper_limit}] 内"
                        test_passed = False
            else:
                # 计算失败（可能是参数验证失败）
                error_msg_from_calc = calc_data.get("error", "未知错误") if isinstance(calc_data, dict) else str(calc_data)
                print(f"- 计算失败: {error_msg_from_calc}")

                # 检查是否符合预期
                if test_case["expected_valid"]:
                    error_msg = f"预期成功但计算失败: {error_msg_from_calc}"
                    test_passed = False

        except Exception as e:
            error_msg = f"计算错误: {e}"
            print(f"- 计算错误: {e}")
            # 检查是否符合预期
            if test_case["expected_valid"]:
                test_passed = False

        # Update statistics
        if test_passed:
            passed_tests += 1

        print_test_result(i, test_passed, error_msg)

    print_summary(total_tests, passed_tests, total_tests - passed_tests)
    return passed_tests, total_tests - passed_tests


async def main():
    def print_header():
        print("LDL 胆固醇计算器 MCP 测试")
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
        print("LDL 胆固醇计算器测试结果")
        print("=" * 60)
        print(f"总测试数: {total_tests}")
        print(f"通过数: {total_passed}")
        print(f"失败数: {total_failed}")
        print(f"成功率: {(total_passed/total_tests*100):.1f}%")

        if total_failed == 0:
            print("\n✅ LDL 胆固醇计算器所有测试都通过了！")
        else:
            print(f"\n❌ {total_failed} 个测试失败，请检查 LDL 胆固醇计算器实现。")

    print_header()

    try:
        async with Client(MCP_SERVER_URL) as client:
            print_connection_status(True)
            passed, failed = await test_ldl_cholesterol_calculator(client)
            print_overall_results(passed, failed)

    except Exception as e:
        print_connection_status(False, str(e))
        import traceback

        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("✅ LDL 胆固醇计算器测试完成")


if __name__ == "__main__":
    asyncio.run(main())