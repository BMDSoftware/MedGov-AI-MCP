import asyncio
import json
import sys
import os
from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVER_URL


async def test_sofa_calculator(client):
    """测试 SOFA 计算器的各种功能和参数组合"""

    def print_header():
        print("\n" + "=" * 60)
        print("SOFA 计算器测试套件")
        print("=" * 60)

    def print_test_case(i, test_case):
        print(f"\n测试 {i:2d} | {test_case['name']}")
        print(f"- {test_case['description']}")
        print(f"- 输入参数: {test_case['params']}")

    def print_calculation_result(data):
        """打印完整的计算结果"""
        sofa_value = data.get("value", "N/A")
        unit = data.get("unit", "")
        explanation = data.get("explanation", "")
        metadata = data.get("metadata", {})
        warnings = data.get("warnings", [])

        # 基本结果
        print(f"- SOFA 评分: {sofa_value} {unit}")

        # 死亡率风险和器官评分
        if metadata:
            mortality_risk = metadata.get("mortality_risk", "N/A")
            organ_scores = metadata.get("organ_scores", {})
            pao2_fio2_ratio = metadata.get("pao2_fio2_ratio", "N/A")
            respiratory_support = metadata.get("respiratory_support", False)
            map_value = metadata.get("map_value", "N/A")

            print(f"- 死亡率风险: {mortality_risk}")
            print(f"- PaO2/FiO2 比值: {pao2_fio2_ratio}")
            print(f"- 呼吸支持: {'是' if respiratory_support else '否'}")
            if map_value != "N/A":
                print(f"- 平均动脉压: {map_value} mmHg")
            
            if organ_scores:
                print("- 器官系统评分:")
                for organ, score in organ_scores.items():
                    organ_names = {
                        "respiratory": "呼吸系统",
                        "coagulation": "凝血系统", 
                        "liver": "肝脏系统",
                        "cardiovascular": "心血管系统",
                        "cns": "中枢神经系统",
                        "renal": "肾脏系统"
                    }
                    print(f"  {organ_names.get(organ, organ)}: {score} 分")

        # 警告信息
        if warnings:
            for warning in warnings:
                print(f"- ⚠️  警告: {warning}")

        # 详细解释（显示前几行）
        if explanation:
            explanation_lines = explanation.split('\n')[:5]
            print(f"- 解释: {explanation_lines[0] if explanation_lines else ''}")

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
            print("\n✅ 所有测试都通过了！SOFA 计算器工作正常。")
        else:
            print(f"\n❌ {failed} 个测试失败，请检查实现。")

        print("\n测试覆盖范围:")
        features = [
            "器官衰竭评估 (6个器官系统)",
            "呼吸系统评估 (PaO2/FiO2比值)",
            "凝血系统评估 (血小板计数)",
            "肝脏系统评估 (胆红素)",
            "心血管系统评估 (血压/血管活性药物)",
            "中枢神经系统评估 (GCS评分)",
            "肾脏系统评估 (肌酐/尿量)",
            "死亡率风险预测",
            "参数验证",
            "边界测试",
        ]
        for feature in features:
            print(f"  - {feature}")

    # Test statistics
    total_tests = 0
    passed_tests = 0

    # Test cases
    test_cases = [
        {
            "name": "正常患者 (低风险)",
            "params": {
                "pao2": 400,
                "fio2": 21,
                "platelets": 200,
                "bilirubin": 1.0,
                "gcs": 15,
                "creatinine": 1.0,
                "systolic_bp": 120,
                "diastolic_bp": 80
            },
            "expected_valid": True,
            "description": "健康患者所有参数正常",
        },
        {
            "name": "中度器官衰竭",
            "params": {
                "pao2": 250,
                "fio2": 50,
                "mechanical_ventilation": False,
                "platelets": 80,
                "bilirubin": 3.0,
                "gcs": 12,
                "creatinine": 2.5,
                "systolic_bp": 90,
                "diastolic_bp": 60
            },
            "expected_valid": True,
            "description": "中度多器官功能障碍",
        },
        {
            "name": "重度器官衰竭 (使用血管活性药物)",
            "params": {
                "pao2": 80,
                "fio2": 80,
                "mechanical_ventilation": True,
                "platelets": 30,
                "bilirubin": 8.0,
                "gcs": 6,
                "dopamine": 20,
                "epinephrine": 0.15,
                "creatinine": 4.5
            },
            "expected_valid": True,
            "description": "重度多器官衰竭，使用机械通气和血管活性药物",
        },
        {
            "name": "使用CPAP的呼吸衰竭",
            "params": {
                "pao2": 150,
                "fio2": 60,
                "cpap": True,
                "platelets": 120,
                "bilirubin": 2.5,
                "gcs": 14,
                "dobutamine": 3.0,
                "creatinine": 1.8
            },
            "expected_valid": True,
            "description": "使用CPAP的患者",
        },
        {
            "name": "使用尿量评估肾功能",
            "params": {
                "pao2": 300,
                "fio2": 40,
                "platelets": 150,
                "bilirubin": 1.5,
                "gcs": 13,
                "urine_output": 300,
                "norepinephrine": 0.08
            },
            "expected_valid": True,
            "description": "使用尿量而非肌酐评估肾功能",
        },
        {
            "name": "极低尿量",
            "params": {
                "pao2": 200,
                "fio2": 60,
                "platelets": 60,
                "bilirubin": 15.0,
                "gcs": 3,
                "urine_output": 100,
                "dopamine": 25
            },
            "expected_valid": True,
            "description": "极低尿量的重症患者",
        },
        {
            "name": "缺少肾功能参数 (应该失败)",
            "params": {
                "pao2": 300,
                "fio2": 40,
                "platelets": 150,
                "bilirubin": 1.5,
                "gcs": 15,
                "systolic_bp": 120,
                "diastolic_bp": 80
            },
            "expected_valid": False,
            "description": "缺少肌酐和尿量参数",
        },
        {
            "name": "缺少心血管参数 (应该失败)",
            "params": {
                "pao2": 300,
                "fio2": 40,
                "platelets": 150,
                "bilirubin": 1.5,
                "gcs": 15,
                "creatinine": 1.2
            },
            "expected_valid": False,
            "description": "缺少血压和血管活性药物信息",
        },
        {
            "name": "边界值测试 - 最小值",
            "params": {
                "pao2": 20,
                "fio2": 21,
                "platelets": 1,
                "bilirubin": 0.1,
                "gcs": 3,
                "creatinine": 0.1,
                "systolic_bp": 30,
                "diastolic_bp": 20
            },
            "expected_valid": True,
            "description": "所有参数最小值测试",
        },
        {
            "name": "边界值测试 - 最大值",
            "params": {
                "pao2": 500,
                "fio2": 100,
                "platelets": 1000,
                "bilirubin": 50,
                "gcs": 15,
                "creatinine": 15,
                "dopamine": 50,
                "dobutamine": 50,
                "epinephrine": 5,
                "norepinephrine": 5,
                "urine_output": 5000
            },
            "expected_valid": True,
            "description": "所有参数最大值测试",
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
                    "calculator_id": 43,  # SOFA calculator ID
                    "parameters": test_case["params"],
                },
            )

            # 使用 structured_content 或 data 属性获取实际数据
            calc_data = calc_result.structured_content or calc_result.data or {}

            if isinstance(calc_data, dict) and calc_data.get("success") and "result" in calc_data:
                # 成功计算
                data = calc_data["result"]
                print_calculation_result(data)

                # 检查是否符合预期
                if not test_case["expected_valid"]:
                    print("- 错误: 预期失败但计算成功")
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
        print("SOFA 计算器 MCP 测试")
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
        print("SOFA 计算器测试结果")
        print("=" * 60)
        print(f"总测试数: {total_tests}")
        print(f"通过数: {total_passed}")
        print(f"失败数: {total_failed}")
        print(f"成功率: {(total_passed/total_tests*100):.1f}%")

        if total_failed == 0:
            print("\n✅ SOFA 计算器所有测试都通过了！")
        else:
            print(f"\n❌ {total_failed} 个测试失败，请检查 SOFA 计算器实现。")

    print_header()

    try:
        async with Client(MCP_SERVER_URL) as client:
            print_connection_status(True)
            passed, failed = await test_sofa_calculator(client)
            print_overall_results(passed, failed)

    except Exception as e:
        print_connection_status(False, str(e))
        import traceback

        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("✅ SOFA 计算器测试完成")


if __name__ == "__main__":
    asyncio.run(main())