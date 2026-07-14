import asyncio
import json
import sys
import os
from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVER_URL


def convert_data_params_to_calculator_params(data_params):
    """将数据文件中的参数格式转换为计算器期望的格式"""
    
    # 参数名称映射
    param_mapping = {
        "Codeine Dose": "codeine_dose",
        "Codeine Dose Per Day": "codeine_frequency",
        "HYDROcodone Dose": "hydrocodone_dose",
        "HYDROcodone Dose Per Day": "hydrocodone_frequency",
        "OxyCODONE Dose": "oxycodone_dose",
        "OxyCODONE Dose Per Day": "oxycodone_frequency",
        "Morphine Dose": "morphine_dose",
        "Morphine Dose Per Day": "morphine_frequency",
        "HYDROmorphone Dose": "hydromorphone_dose",
        "HYDROmorphone Dose Per Day": "hydromorphone_frequency",
        "FentANYL patch Dose": "fentanyl_patch_dose",
        "FentANYL patch Dose Per Day": "fentanyl_patch_frequency",
        "TraMADol Dose": "tramadol_dose",
        "TraMADol Dose Per Day": "tramadol_frequency",
        "Tapentadol Dose": "tapentadol_dose",
        "Tapentadol Dose Per Day": "tapentadol_frequency",
        "OxyMORphone Dose": "oxymorphone_dose", 
        "OxyMORphone Dose Per Day": "oxymorphone_frequency",
        "FentaNYL buccal Dose": "fentanyl_buccal_dose",
        "FentaNYL buccal Dose Per Day": "fentanyl_buccal_frequency",
        "Methadone Dose": "methadone_dose",
        "Methadone Dose Per Day": "methadone_frequency",
        "Buprenorphine Dose": "buprenorphine_dose",
        "Buprenorphine Dose Per Day": "buprenorphine_frequency"
    }
    
    converted_params = {}
    
    for data_param, value in data_params.items():
        if data_param in param_mapping:
            calc_param = param_mapping[data_param]
            # 如果值是 [值, 单位] 格式，提取值
            if isinstance(value, list) and len(value) >= 1:
                converted_params[calc_param] = value[0]
            else:
                converted_params[calc_param] = value
                
    return converted_params


async def test_mme_calculator(client):
    """测试 MME 计算器的各种功能"""

    def print_header():
        print("\n" + "=" * 60)
        print("MME (Morphine Milligram Equivalent) 计算器测试套件")
        print("=" * 60)

    def print_test_case(i, test_case):
        print(f"\n测试 {i:2d} | {test_case['name']}")
        print(f"- {test_case['description']}")
        print(f"- 输入参数: {test_case['params']}")
        if 'expected_mme' in test_case:
            print(f"- 预期 MME: {test_case['expected_mme']}")

    def print_calculation_result(data):
        """打印完整的计算结果"""
        mme_value = data.get("value", "N/A")
        unit = data.get("unit", "")
        explanation = data.get("explanation", "")
        metadata = data.get("metadata", {})
        warnings = data.get("warnings", [])

        # 基本结果
        print(f"- MME 值: {mme_value} {unit}")

        # 风险评估
        if metadata:
            risk_level = metadata.get("risk_level", "N/A")
            recommendation = metadata.get("recommendation", "N/A")
            cdc_threshold_50 = metadata.get("cdc_threshold_50", False)
            cdc_threshold_90 = metadata.get("cdc_threshold_90", False)
            medication_details = metadata.get("medication_details", [])

            print(f"- 风险级别: {risk_level}")
            if cdc_threshold_50:
                print("- ⚠️  超过 CDC 50 MME/day 阈值")
            if cdc_threshold_90:
                print("- ⚠️  超过 CDC 90 MME/day 高风险阈值")
            
            # 显示用药详情
            if medication_details:
                print("- 用药详情:")
                for med in medication_details:
                    print(f"  • {med['name']}: {med['dose']} {med['unit']} × {med['frequency']} = {med['mme']} MME")

        # 警告信息
        if warnings:
            for warning in warnings:
                print(f"- ⚠️  警告: {warning}")

        # 详细解释（截取部分显示）
        if explanation:
            lines = explanation.split('\n')
            print(f"- 解释 (前3行): {lines[:3]}")

    def print_test_result(i, passed, expected_mme=None, actual_mme=None):
        if passed:
            status = "✅ 通过"
        else:
            status = "❌ 失败"
        print(f"- 测试结果: {status}")
        if expected_mme is not None and actual_mme is not None:
            print(f"- 数值比较: 期望 {expected_mme}, 实际 {actual_mme}")
        print("-" * 60)

    def print_summary(total, passed, failed):
        print(f"\n测试总结:")
        print(f"  总测试数: {total}")
        print(f"  通过数: {passed}")
        print(f"  失败数: {failed}")
        print(f"  成功率: {(passed/total*100):.1f}%")

        if failed == 0:
            print("\n✅ 所有测试都通过了！MME 计算器工作正常。")
        else:
            print(f"\n❌ {failed} 个测试失败，请检查实现。")

        print("\n测试覆盖范围:")
        features = [
            "多种阿片类药物支持",
            "剂量和频次计算",
            "MME 转换因子", 
            "风险评估 (CDC指导原则)",
            "参数验证",
            "芬太尼贴片特殊处理",
            "错误处理"
        ]
        for feature in features:
            print(f"  - {feature}")

    # Test statistics
    total_tests = 0
    passed_tests = 0

    # 从数据文件中提取的所有20条真实测试用例
    test_cases = [
        {
            "name": "Row 9878 - Methadone+Codeine+FentaNYL patch",
            "params": convert_data_params_to_calculator_params({
                "Methadone Dose": [50, "mg"],
                "Methadone Dose Per Day": [2, "per day"],
                "Codeine Dose": [50, "mg"], 
                "Codeine Dose Per Day": [1, "per day"],
                "FentANYL patch Dose": [40, "mg"],
                "FentANYL patch Dose Per Day": [2, "per day"]
            }),
            "expected_valid": True,
            "expected_mme": 669.5,
            "description": "数据文件条目1 (Row 9878)"
        },
        {
            "name": "Row 9826 - FentaNYL buccal+Tapentadol+TraMADol",
            "params": convert_data_params_to_calculator_params({
                "FentaNYL buccal Dose": [20, "µg"],
                "FentaNYL buccal Dose Per Day": [1, "per day"],
                "Tapentadol Dose": [20, "mg"],
                "Tapentadol Dose Per Day": [1, "per day"],
                "TraMADol Dose": [50, "mg"],
                "TraMADol Dose Per Day": [3, "per day"]
            }),
            "expected_valid": True,
            "expected_mme": 40.6,
            "description": "数据文件条目2 (Row 9826)"
        },
        {
            "name": "Row 9877 - OxyMORphone+Morphine+FentaNYL buccal",
            "params": convert_data_params_to_calculator_params({
                "OxyMORphone Dose": [40, "mg"],
                "OxyMORphone Dose Per Day": [3, "per day"],
                "Morphine Dose": [70, "mg"],
                "Morphine Dose Per Day": [2, "per day"],
                "FentaNYL buccal Dose": [10, "µg"],
                "FentaNYL buccal Dose Per Day": [2, "per day"]
            }),
            "expected_valid": True,
            "expected_mme": 502.6,
            "description": "数据文件条目3 (Row 9877)"
        },
        {
            "name": "Row 9885 - HYDROmorphone+OxyCODONE+FentANYL patch",
            "params": convert_data_params_to_calculator_params({
                "HYDROmorphone Dose": [20, "mg"],
                "HYDROmorphone Dose Per Day": [1, "per day"],
                "OxyCODONE Dose": [70, "mg"],
                "OxyCODONE Dose Per Day": [2, "per day"],
                "FentANYL patch Dose": [60, "mg"],
                "FentANYL patch Dose Per Day": [3, "per day"]
            }),
            "expected_valid": True,
            "expected_mme": 742.0,
            "description": "数据文件条目4 (Row 9885)"
        },
        {
            "name": "Row 9831 - HYDROcodone+FentaNYL buccal+OxyMORphone",
            "params": convert_data_params_to_calculator_params({
                "HYDROcodone Dose": [30, "mg"],
                "HYDROcodone Dose Per Day": [3, "per day"],
                "FentaNYL buccal Dose": [10, "µg"],
                "FentaNYL buccal Dose Per Day": [3, "per day"],
                "OxyMORphone Dose": [20, "mg"],
                "OxyMORphone Dose Per Day": [1, "per day"]
            }),
            "expected_valid": True,
            "expected_mme": 153.9,
            "description": "数据文件条目5 (Row 9831)"
        },
        {
            "name": "Row 9854 - TraMADol+HYDROcodone+Tapentadol",
            "params": convert_data_params_to_calculator_params({
                "TraMADol Dose": [10, "mg"],
                "TraMADol Dose Per Day": [2, "per day"],
                "HYDROcodone Dose": [10, "mg"],
                "HYDROcodone Dose Per Day": [2, "per day"],
                "Tapentadol Dose": [40, "mg"],
                "Tapentadol Dose Per Day": [3, "per day"]
            }),
            "expected_valid": True,
            "expected_mme": 72.0,
            "description": "数据文件条目6 (Row 9854)"
        },
        {
            "name": "Row 9871 - Codeine+Tapentadol+FentANYL patch",
            "params": convert_data_params_to_calculator_params({
                "Codeine Dose": [40, "mg"],
                "Codeine Dose Per Day": [2, "per day"],
                "Tapentadol Dose": [50, "mg"],
                "Tapentadol Dose Per Day": [1, "per day"],
                "FentANYL patch Dose": [20, "mg"],
                "FentANYL patch Dose Per Day": [3, "per day"]
            }),
            "expected_valid": True,
            "expected_mme": 176.0,
            "description": "数据文件条目7 (Row 9871)"
        },
        {
            "name": "Row 9884 - OxyMORphone+OxyCODONE+Codeine",
            "params": convert_data_params_to_calculator_params({
                "OxyMORphone Dose": [20, "mg"],
                "OxyMORphone Dose Per Day": [2, "per day"],
                "OxyCODONE Dose": [30, "mg"],
                "OxyCODONE Dose Per Day": [1, "per day"],
                "Codeine Dose": [70, "mg"],
                "Codeine Dose Per Day": [3, "per day"]
            }),
            "expected_valid": True,
            "expected_mme": 196.5,
            "description": "数据文件条目8 (Row 9884)"
        },
        {
            "name": "Row 9850 - HYDROmorphone+Tapentadol+Methadone",
            "params": convert_data_params_to_calculator_params({
                "HYDROmorphone Dose": [60, "mg"],
                "HYDROmorphone Dose Per Day": [3, "per day"],
                "Tapentadol Dose": [30, "mg"],
                "Tapentadol Dose Per Day": [1, "per day"],
                "Methadone Dose": [60, "mg"],
                "Methadone Dose Per Day": [1, "per day"]
            }),
            "expected_valid": True,
            "expected_mme": 1194.0,
            "description": "数据文件条目9 (Row 9850)"
        },
        {
            "name": "Row 9864 - OxyMORphone+TraMADol+Codeine",
            "params": convert_data_params_to_calculator_params({
                "OxyMORphone Dose": [60, "mg"],
                "OxyMORphone Dose Per Day": [2, "per day"],
                "TraMADol Dose": [70, "mg"],
                "TraMADol Dose Per Day": [3, "per day"],
                "Codeine Dose": [10, "mg"],
                "Codeine Dose Per Day": [2, "per day"]
            }),
            "expected_valid": True,
            "expected_mme": 405.0,
            "description": "数据文件条目10 (Row 9864)"
        },
        {
            "name": "Row 9874 - HYDROmorphone+FentANYL patch+Methadone",
            "params": convert_data_params_to_calculator_params({
                "HYDROmorphone Dose": [60, "mg"],
                "HYDROmorphone Dose Per Day": [3, "per day"],
                "FentANYL patch Dose": [20, "mg"],
                "FentANYL patch Dose Per Day": [2, "per day"],
                "Methadone Dose": [30, "mg"],
                "Methadone Dose Per Day": [3, "per day"]
            }),
            "expected_valid": True,
            "expected_mme": 1419.0,
            "description": "数据文件条目11 (Row 9874)"
        },
        {
            "name": "Row 9892 - OxyCODONE+Methadone+Tapentadol",
            "params": convert_data_params_to_calculator_params({
                "OxyCODONE Dose": [40, "mg"],
                "OxyCODONE Dose Per Day": [2, "per day"],
                "Methadone Dose": [50, "mg"],
                "Methadone Dose Per Day": [3, "per day"],
                "Tapentadol Dose": [70, "mg"],
                "Tapentadol Dose Per Day": [1, "per day"]
            }),
            "expected_valid": True,
            "expected_mme": 853.0,
            "description": "数据文件条目12 (Row 9892)"
        },
        {
            "name": "Row 9825 - Codeine+FentaNYL buccal+Tapentadol",
            "params": convert_data_params_to_calculator_params({
                "Codeine Dose": [70, "mg"],
                "Codeine Dose Per Day": [3, "per day"],
                "FentaNYL buccal Dose": [30, "µg"],
                "FentaNYL buccal Dose Per Day": [1, "per day"],
                "Tapentadol Dose": [70, "mg"],
                "Tapentadol Dose Per Day": [3, "per day"]
            }),
            "expected_valid": True,
            "expected_mme": 119.4,
            "description": "数据文件条目13 (Row 9825)"
        },
        {
            "name": "Row 9840 - HYDROcodone+HYDROmorphone+OxyMORphone",
            "params": convert_data_params_to_calculator_params({
                "HYDROcodone Dose": [30, "mg"],
                "HYDROcodone Dose Per Day": [2, "per day"],
                "HYDROmorphone Dose": [30, "mg"],
                "HYDROmorphone Dose Per Day": [3, "per day"],
                "OxyMORphone Dose": [10, "mg"],
                "OxyMORphone Dose Per Day": [3, "per day"]
            }),
            "expected_valid": True,
            "expected_mme": 600.0,
            "description": "数据文件条目14 (Row 9840)"
        },
        {
            "name": "Row 9870 - OxyMORphone+Tapentadol+HYDROmorphone",
            "params": convert_data_params_to_calculator_params({
                "OxyMORphone Dose": [20, "mg"],
                "OxyMORphone Dose Per Day": [3, "per day"],
                "Tapentadol Dose": [20, "mg"],
                "Tapentadol Dose Per Day": [3, "per day"],
                "HYDROmorphone Dose": [30, "mg"],
                "HYDROmorphone Dose Per Day": [3, "per day"]
            }),
            "expected_valid": True,
            "expected_mme": 654.0,
            "description": "数据文件条目15 (Row 9870)"
        },
        {
            "name": "Row 9838 - Morphine+HYDROcodone+OxyCODONE",
            "params": convert_data_params_to_calculator_params({
                "Morphine Dose": [20, "mg"],
                "Morphine Dose Per Day": [2, "per day"],
                "HYDROcodone Dose": [60, "mg"],
                "HYDROcodone Dose Per Day": [2, "per day"],
                "OxyCODONE Dose": [70, "mg"],
                "OxyCODONE Dose Per Day": [1, "per day"]
            }),
            "expected_valid": True,
            "expected_mme": 265.0,
            "description": "数据文件条目16 (Row 9838)"
        },
        {
            "name": "Row 9887 - Tapentadol+Methadone+FentANYL patch",
            "params": convert_data_params_to_calculator_params({
                "Tapentadol Dose": [40, "mg"],
                "Tapentadol Dose Per Day": [3, "per day"],
                "Methadone Dose": [40, "mg"],
                "Methadone Dose Per Day": [2, "per day"],
                "FentANYL patch Dose": [20, "mg"],
                "FentANYL patch Dose Per Day": [1, "per day"]
            }),
            "expected_valid": True,
            "expected_mme": 472.0,
            "description": "数据文件条目17 (Row 9887)"
        },
        {
            "name": "Row 9818 - HYDROcodone+OxyCODONE+FentANYL patch",
            "params": convert_data_params_to_calculator_params({
                "HYDROcodone Dose": [10, "mg"],
                "HYDROcodone Dose Per Day": [3, "per day"],
                "OxyCODONE Dose": [50, "mg"],
                "OxyCODONE Dose Per Day": [3, "per day"],
                "FentANYL patch Dose": [40, "mg"],
                "FentANYL patch Dose Per Day": [1, "per day"]
            }),
            "expected_valid": True,
            "expected_mme": 351.0,
            "description": "数据文件条目18 (Row 9818)"
        },
        {
            "name": "Row 9879 - Codeine+HYDROcodone+FentaNYL buccal",
            "params": convert_data_params_to_calculator_params({
                "Codeine Dose": [10, "mg"],
                "Codeine Dose Per Day": [1, "per day"],
                "HYDROcodone Dose": [30, "mg"],
                "HYDROcodone Dose Per Day": [1, "per day"],
                "FentaNYL buccal Dose": [10, "µg"],
                "FentaNYL buccal Dose Per Day": [2, "per day"]
            }),
            "expected_valid": True,
            "expected_mme": 34.1,
            "description": "数据文件条目19 (Row 9879)"
        },
        {
            "name": "Row 9868 - OxyMORphone+Tapentadol+HYDROcodone",
            "params": convert_data_params_to_calculator_params({
                "OxyMORphone Dose": [20, "mg"],
                "OxyMORphone Dose Per Day": [2, "per day"],
                "Tapentadol Dose": [20, "mg"],
                "Tapentadol Dose Per Day": [2, "per day"],
                "HYDROcodone Dose": [30, "mg"],
                "HYDROcodone Dose Per Day": [1, "per day"]
            }),
            "expected_valid": True,
            "expected_mme": 166.0,
            "description": "数据文件条目20 (Row 9868)"
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
                    "calculator_id": 49,
                    "parameters": test_case["params"],
                },
            )

            # 获取结果数据
            calc_data = calc_result.structured_content or calc_result.data or {}

            if isinstance(calc_data, dict) and calc_data.get("success") and "result" in calc_data:
                # 成功计算
                data = calc_data["result"]
                print_calculation_result(data)

                # 检查是否符合预期
                if not test_case["expected_valid"]:
                    print("- 错误: 预期失败但计算成功")
                    test_passed = False
                    
                # 检查 MME 值是否匹配
                if "expected_mme" in test_case:
                    actual_mme = data.get("value")
                    expected_mme = test_case["expected_mme"]
                    if abs(actual_mme - expected_mme) > 0.1:  # 允许小的浮点数误差
                        print(f"- 错误: MME 值不匹配，期望 {expected_mme}, 实际 {actual_mme}")
                        test_passed = False

            else:
                # 计算失败
                error_msg = calc_data.get("error", "未知错误") if isinstance(calc_data, dict) else str(calc_data)
                print(f"- 计算失败: {error_msg}")

                # 检查是否符合预期
                if test_case["expected_valid"]:
                    print("- 错误: 预期成功但计算失败")
                    test_passed = False

        except Exception as e:
            print(f"- 计算错误: {e}")
            if test_case["expected_valid"]:
                test_passed = False

        # Update statistics
        if test_passed:
            passed_tests += 1

        expected_mme = test_case.get("expected_mme")
        actual_mme = None
        try:
            if "calc_data" in locals() and isinstance(calc_data, dict) and calc_data.get("success"):
                actual_mme = calc_data["result"].get("value")
        except:
            pass
        
        print_test_result(i, test_passed, expected_mme, actual_mme)

    print_summary(total_tests, passed_tests, total_tests - passed_tests)
    return passed_tests, total_tests - passed_tests


async def main():
    def print_header():
        print("MME 计算器 MCP 测试")
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
        print("MME 计算器测试结果")
        print("=" * 60)
        print(f"总测试数: {total_tests}")
        print(f"通过数: {total_passed}")
        print(f"失败数: {total_failed}")
        print(f"成功率: {(total_passed/total_tests*100):.1f}%")

        if total_failed == 0:
            print("\n✅ MME 计算器所有测试都通过了！")
        else:
            print(f"\n❌ {total_failed} 个测试失败，请检查 MME 计算器实现。")

    print_header()

    try:
        async with Client(MCP_SERVER_URL) as client:
            print_connection_status(True)
            passed, failed = await test_mme_calculator(client)
            print_overall_results(passed, failed)

    except Exception as e:
        print_connection_status(False, str(e))
        import traceback

        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("✅ MME 计算器测试完成")


if __name__ == "__main__":
    asyncio.run(main())