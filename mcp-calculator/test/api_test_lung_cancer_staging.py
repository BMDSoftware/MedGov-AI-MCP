import asyncio
import json
import sys
import os
from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVER_URL


async def test_lung_cancer_staging_calculator(client):
    """测试肺癌TNM分期计算器的各种功能"""

    def print_header():
        print("\n" + "=" * 60)
        print("肺癌TNM分期计算器测试套件 (AJCC第九版)")
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

    def print_calculation_result(data, expected_results):
        """打印完整的计算结果"""
        stage_value = data.get("value", "N/A")
        unit = data.get("unit", "")
        explanation = data.get("explanation", "")
        metadata = data.get("metadata", {})
        warnings = data.get("warnings", [])

        # 基本结果
        print(f"- 最终分期: {stage_value} {unit}")

        # TNM组合结果
        if metadata:
            t_stage = metadata.get("t_stage", "N/A")
            n_stage = metadata.get("n_stage", "N/A") 
            m_stage = metadata.get("m_stage", "N/A")
            tnm_combined = metadata.get("tnm_combined", "N/A")
            ajcc_version = metadata.get("ajcc_version", "N/A")

            print(f"- T分期: {t_stage}")
            print(f"- N分期: {n_stage}")
            print(f"- M分期: {m_stage}")
            print(f"- TNM组合: {tnm_combined}")
            print(f"- AJCC版本: {ajcc_version}")

            # 检查预期结果
            results_match = True
            if expected_results:
                expected_stage = expected_results.get("expected_stage")
                expected_t = expected_results.get("expected_t_stage")
                expected_n = expected_results.get("expected_n_stage") 
                expected_m = expected_results.get("expected_m_stage")
                
                if expected_stage and stage_value != expected_stage:
                    print(f"- ❌ 分期不匹配: 预期 {expected_stage}, 实际 {stage_value}")
                    results_match = False
                if expected_t and t_stage != expected_t:
                    print(f"- ❌ T分期不匹配: 预期 {expected_t}, 实际 {t_stage}")
                    results_match = False
                if expected_n and n_stage != expected_n:
                    print(f"- ❌ N分期不匹配: 预期 {expected_n}, 实际 {n_stage}")
                    results_match = False
                if expected_m and m_stage != expected_m:
                    print(f"- ❌ M分期不匹配: 预期 {expected_m}, 实际 {m_stage}")
                    results_match = False

                if results_match:
                    print("- ✅ 所有结果与预期匹配")
                
                return results_match

        # 警告信息
        if warnings:
            for warning in warnings:
                print(f"- ⚠️  警告: {warning}")

        # 详细解释（截取前几行显示）
        if explanation:
            lines = explanation.strip().split('\n')
            print(f"- 解释摘要: {lines[0] if lines else '无'}")

        return True

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
            print("\n✅ 所有测试都通过了！肺癌TNM分期计算器工作正常。")
        else:
            print(f"\n❌ {failed} 个测试失败，请检查实现。")

        print("\n测试覆盖范围:")
        features = [
            "T分期计算 (肿瘤大小和侵犯特征)",
            "N分期计算 (淋巴结转移模式)",
            "M分期计算 (远处转移类型)",
            "最终分期组合判断",
            "特殊情况处理 (原位癌等)",
            "参数验证",
            "临床特征映射",
            "AJCC第九版标准符合性"
        ]
        for feature in features:
            print(f"  - {feature}")

    # Test statistics
    total_tests = 0
    passed_tests = 0

    # Test cases - 基于具体临床特征的参数
    test_cases = [
        {
            "name": "Early small tumor (T1b N0 M0)",
            "params": {
                "staging_type": "clinical",
                "treatment_stage": "initial",
                "tumor_size": 1.5,
                "lymph_nodes_assessable": True,
            },
            "expected_valid": True,
            "expected_stage": "IA2",
            "expected_t_stage": "T1b",
            "expected_n_stage": "N0",
            "expected_m_stage": "M0",
            "description": "早期小肿瘤测试 (1.5cm, 无淋巴结转移, 无远处转移)",
        },
        {
            "name": "Medium tumor with ipsilateral nodes (T2a N1 M0)",
            "params": {
                "staging_type": "clinical",
                "treatment_stage": "initial",
                "tumor_size": 3.5,
                "lymph_nodes_assessable": True,
                "lymph_node_involvement": "ipsilateral_pulmonary_hilar",
            },
            "expected_valid": True,
            "expected_stage": "IIB",
            "expected_t_stage": "T2a",
            "expected_n_stage": "N1",
            "expected_m_stage": "M0",
            "description": "中等肿瘤伴同侧肺内淋巴结转移 (3.5cm)",
        },
        {
            "name": "Large tumor single mediastinal node (T4 N2a M0)",
            "params": {
                "staging_type": "clinical",
                "treatment_stage": "initial",
                "tumor_size": 8.0,
                "lymph_nodes_assessable": True,
                "lymph_node_involvement": "single_ipsilateral_mediastinal",
            },
            "expected_valid": True,
            "expected_stage": "IIIB",
            "expected_t_stage": "T4",
            "expected_n_stage": "N2a",
            "expected_m_stage": "M0",
            "description": "大肿瘤伴单个纵隔淋巴结转移 (8.0cm)",
        },
        {
            "name": "Contralateral lung nodule (T2a N0 M1a)",
            "params": {
                "staging_type": "clinical",
                "treatment_stage": "initial",
                "tumor_size": 4.0,
                "lymph_nodes_assessable": True,
                "distant_metastasis": "contralateral_lung_nodules",
            },
            "expected_valid": True,
            "expected_stage": "IVA",
            "expected_t_stage": "T2a",
            "expected_n_stage": "N0",
            "expected_m_stage": "M1a",
            "description": "对侧肺结节 (4.0cm, M1a转移)",
        },
        {
            "name": "Carcinoma in situ (Tis N0 M0)",
            "params": {
                "staging_type": "pathologic",
                "treatment_stage": "initial",
                "tumor_special_status": "adenocarcinoma_in_situ",
                "lymph_nodes_assessable": True,
            },
            "expected_valid": True,
            "expected_stage": "0",
            "expected_t_stage": "Tis(AIS)",
            "expected_n_stage": "N0",
            "expected_m_stage": "M0",
            "description": "腺癌原位癌测试",
        },
        {
            "name": "Chest wall invasion with N1 (T3 N1 M0)",
            "params": {
                "staging_type": "clinical",
                "treatment_stage": "initial",
                "tumor_size": 4.0,
                "tumor_invasion_features": "chest_wall_diaphragm",
                "lymph_nodes_assessable": True,
                "lymph_node_involvement": "ipsilateral_pulmonary_hilar",
            },
            "expected_valid": True,
            "expected_stage": "IIIA",
            "expected_t_stage": "T3",
            "expected_n_stage": "N1",
            "expected_m_stage": "M0",
            "description": "胸壁侵犯伴同侧肺内淋巴结转移",
        },
        {
            "name": "Pleural invasion multiple mediastinal (T2a N2b M0)",
            "params": {
                "staging_type": "clinical",
                "treatment_stage": "initial",
                "tumor_size": 2.5,
                "tumor_invasion_features": "visceral_pleura",
                "lymph_nodes_assessable": True,
                "lymph_node_involvement": "multiple_ipsilateral_mediastinal",
            },
            "expected_valid": True,
            "expected_stage": "IIIB",
            "expected_t_stage": "T2a",
            "expected_n_stage": "N2b",
            "expected_m_stage": "M0",
            "description": "脏层胸膜侵犯伴多个纵隔淋巴结转移",
        },
        {
            "name": "Multiple organ metastasis (T1a N0 M1c)",
            "params": {
                "staging_type": "clinical",
                "treatment_stage": "initial",
                "tumor_size": 0.8,
                "lymph_nodes_assessable": True,
                "distant_metastasis": "multiple_organs_metastasis",
            },
            "expected_valid": True,
            "expected_stage": "IVB",
            "expected_t_stage": "T1a",
            "expected_n_stage": "N0",
            "expected_m_stage": "M1c",
            "description": "多器官转移 (0.8cm, M1c)",
        },
        {
            "name": "Invalid parameters (missing required)",
            "params": {
                "tumor_size": 5.0,
                # Missing staging_type, treatment_stage, lymph_nodes_assessable
            },
            "expected_valid": False,
            "description": "无效参数测试 - 缺少必需参数",
        },
        {
            "name": "Edge case - very large tumor",
            "params": {
                "staging_type": "clinical",
                "treatment_stage": "initial",
                "tumor_size": 15.0,
                "lymph_nodes_assessable": True,
            },
            "expected_valid": True,
            "expected_stage": "IIIA",
            "expected_t_stage": "T4",
            "expected_n_stage": "N0",
            "expected_m_stage": "M0",
            "description": "边界测试 - 极大肿瘤 (15cm)",
        },
        # 新增测试用例 - 测试新功能
        {
            "name": "Minimally invasive adenocarcinoma T1a(mi)",
            "params": {
                "staging_type": "pathologic",
                "treatment_stage": "initial",
                "tumor_special_status": "minimally_invasive_adenocarcinoma",
                "lymph_nodes_assessable": True,
            },
            "expected_valid": True,
            "expected_stage": "IA1",
            "expected_t_stage": "T1a(mi)",
            "expected_n_stage": "N0",
            "expected_m_stage": "M0",
            "description": "微浸润性腺癌测试 (≤3cm, 浸润成分≤5mm)",
        },
        {
            "name": "Post-neoadjuvant pathologic staging ypT2aN1M0",
            "params": {
                "staging_type": "pathologic",
                "treatment_stage": "post_neoadjuvant",
                "tumor_size": 3.2,
                "lymph_nodes_assessable": True,
                "lymph_node_involvement": "ipsilateral_pulmonary_hilar",
            },
            "expected_valid": True,
            "expected_stage": "IIB",
            "expected_t_stage": "T2a",
            "expected_n_stage": "N1",
            "expected_m_stage": "M0",
            "description": "新辅助治疗后病理分期测试 (ypTNM)",
        },
        {
            "name": "Clinical recurrence staging rcT1cN0M0",
            "params": {
                "staging_type": "clinical",
                "treatment_stage": "recurrence",
                "tumor_size": 2.8,
                "lymph_nodes_assessable": True,
            },
            "expected_valid": True,
            "expected_stage": "IA3",
            "expected_t_stage": "T1c",
            "expected_n_stage": "N0",
            "expected_m_stage": "M0",
            "description": "复发时临床分期测试 (rcTNM)",
        },
        {
            "name": "Very small tumor T1a staging",
            "params": {
                "staging_type": "clinical",
                "treatment_stage": "initial",
                "tumor_size": 0.8,
                "lymph_nodes_assessable": True,
            },
            "expected_valid": True,
            "expected_stage": "IA1",
            "expected_t_stage": "T1a",
            "expected_n_stage": "N0",
            "expected_m_stage": "M0",
            "description": "极小肿瘤测试 - IA1期 (≤1cm)",
        },
        {
            "name": "T1c staging test",
            "params": {
                "staging_type": "clinical", 
                "treatment_stage": "initial",
                "tumor_size": 2.5,
                "lymph_nodes_assessable": True,
            },
            "expected_valid": True,
            "expected_stage": "IA3",
            "expected_t_stage": "T1c",
            "expected_n_stage": "N0",
            "expected_m_stage": "M0",
            "description": "T1c分期测试 - IA3期 (2-3cm)",
        },
        {
            "name": "Squamous carcinoma in situ",
            "params": {
                "staging_type": "pathologic",
                "treatment_stage": "initial",
                "tumor_special_status": "squamous_carcinoma_in_situ",
                "lymph_nodes_assessable": True,
            },
            "expected_valid": True,
            "expected_stage": "0",
            "expected_t_stage": "Tis(SC)",
            "expected_n_stage": "N0",
            "expected_m_stage": "M0",
            "description": "鳞癌原位癌测试",
        },
        {
            "name": "Pleural implants M1a",
            "params": {
                "staging_type": "clinical",
                "treatment_stage": "initial",
                "tumor_size": 3.0,
                "lymph_nodes_assessable": True,
                "distant_metastasis": "pleural_implants",
            },
            "expected_valid": True,
            "expected_stage": "IVA",
            "expected_t_stage": "T1c",
            "expected_n_stage": "N0",
            "expected_m_stage": "M1a",
            "description": "胸膜种植测试 - 应归类为M1a",
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
                    "calculator_id": 70,  # LungCancerStagingCalculator ID
                    "parameters": test_case["params"],
                },
            )

            # 使用 structured_content 或 data 属性获取实际数据
            calc_data = calc_result.structured_content or calc_result.data or {}

            if isinstance(calc_data, dict) and calc_data.get("success") and "result" in calc_data:
                # 成功计算
                data = calc_data["result"]
                expected_results = {
                    "expected_stage": test_case.get("expected_stage"),
                    "expected_t_stage": test_case.get("expected_t_stage"),
                    "expected_n_stage": test_case.get("expected_n_stage"),
                    "expected_m_stage": test_case.get("expected_m_stage"),
                }
                
                results_match = print_calculation_result(data, expected_results)

                # 检查是否符合预期
                if not test_case["expected_valid"]:
                    print("- 错误: 预期失败但计算成功")
                    test_passed = False
                elif not results_match:
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
        print("肺癌TNM分期计算器 MCP 测试")
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
        print("肺癌TNM分期计算器测试结果")
        print("=" * 60)
        print(f"总测试数: {total_tests}")
        print(f"通过数: {total_passed}")
        print(f"失败数: {total_failed}")
        print(f"成功率: {(total_passed/total_tests*100):.1f}%")

        if total_failed == 0:
            print("\n✅ 肺癌TNM分期计算器所有测试都通过了！")
        else:
            print(f"\n❌ {total_failed} 个测试失败，请检查肺癌TNM分期计算器实现。")

    print_header()

    try:
        async with Client(MCP_SERVER_URL) as client:
            print_connection_status(True)
            passed, failed = await test_lung_cancer_staging_calculator(client)
            print_overall_results(passed, failed)

    except Exception as e:
        print_connection_status(False, str(e))
        import traceback

        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("✅ 肺癌TNM分期计算器测试完成")


if __name__ == "__main__":
    asyncio.run(main())