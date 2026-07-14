import asyncio
import json
import sys
import os
from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVER_URL


async def test_cha2ds2_vasc_calculator(client):
    """测试 CHA2DS2-VASc 计算器的各种风险评分计算"""

    def print_header():
        print("\n" + "=" * 70)
        print("CHA2DS2-VASc 评分计算器测试套件")
        print("=" * 70)
        print("CHA2DS2-VASc 评分用于评估房颤患者的卒中风险")
        print("评分标准：")
        print("- 充血性心力衰竭 (CHF): 1分")
        print("- 高血压: 1分")
        print("- 年龄≥75岁: 2分")
        print("- 糖尿病: 1分")
        print("- 卒中/TIA/血栓栓塞: 2分")
        print("- 血管疾病: 1分")
        print("- 年龄65-74岁: 1分")
        print("- 女性: 1分")
        print("=" * 70)

    def print_test_case(i, test_case):
        print(f"\n测试 {i:2d} | {test_case['name']}")
        print(f"- 描述: {test_case['description']}")
        print(f"- 输入参数: {test_case['params']}")
        print(f"- 期望得分: {test_case['expected_score']}")

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

    def print_calculation_result(data):
        """打印完整的计算结果"""
        score = data.get("value", "N/A")
        unit = data.get("unit", "")
        explanation = data.get("explanation", "")
        metadata = data.get("metadata", {})
        warnings = data.get("warnings", [])

        # 基本结果
        print(f"- CHA2DS2-VASc 评分: {score} {unit}")

        # 详细解释
        if explanation:
            print(f"- 计算说明: {explanation}")

        # 风险分层
        if metadata:
            risk_level = metadata.get("risk_level", "")
            risk_description = metadata.get("risk_description", "")
            if risk_level:
                print(f"- 风险分层: {risk_level}")
            if risk_description:
                print(f"- 风险描述: {risk_description}")

        # 警告信息
        if warnings:
            print(f"- ⚠️  警告: {warnings}")

    def print_test_summary(total, passed, failed):
        print("\n" + "=" * 70)
        print("测试总结")
        print("=" * 70)
        print(f"总测试数: {total}")
        print(f"通过测试: {passed}")
        print(f"失败测试: {failed}")
        success_rate = (passed / total * 100) if total > 0 else 0
        print(f"成功率: {success_rate:.1f}%")
        print("=" * 70)

    # 测试用例定义
    test_cases = [
        {
            "name": "高风险男性患者",
            "description": "78岁男性，有多种危险因素",
            "params": {
                "age": 78,
                "sex": "Male",
                "thromboembolism": True,
                "tia": True,
                "hypertension": True,
                "stroke": True
            },
            "expected_score": 5
        },
        {
            "name": "中等风险男性患者",
            "description": "74岁男性，有心血管危险因素",
            "params": {
                "age": 74,
                "sex": "Male",
                "thromboembolism": False,
                "hypertension": True,
                "vascular_disease": True,
                "chf": True,
                "stroke": False
            },
            "expected_score": 4
        },
        {
            "name": "极高风险男性患者",
            "description": "81岁男性，多重危险因素",
            "params": {
                "age": 81,
                "sex": "Male",
                "thromboembolism": False,
                "tia": True,
                "hypertension": True,
                "diabetes": True,
                "vascular_disease": True,
                "stroke": True
            },
            "expected_score": 7
        },
        {
            "name": "年轻女性患者",
            "description": "32岁女性，有血栓栓塞史",
            "params": {
                "age": 32,
                "sex": "Female",
                "hypertension": False,
                "chf": False,
                "stroke": False,
                "tia": False,
                "thromboembolism": True,
                "vascular_disease": False,
                "diabetes": False
            },
            "expected_score": 3
        },
        {
            "name": "中等风险男性患者2",
            "description": "65岁男性，多重危险因素",
            "params": {
                "age": 65,
                "sex": "Male",
                "thromboembolism": True,
                "hypertension": True,
                "diabetes": True,
                "vascular_disease": True
            },
            "expected_score": 6
        },
        {
            "name": "74岁男性多重危险因素",
            "description": "74岁男性，有CHF、高血压和血管疾病",
            "params": {
                "age": 74,
                "sex": "Male",
                "chf": True,
                "hypertension": True,
                "vascular_disease": True,
                "stroke": False,
                "tia": False,
                "thromboembolism": False,
                "diabetes": False
            },
            "expected_score": 4
        },
        {
            "name": "73岁男性多重危险因素",
            "description": "73岁男性，有CHF、高血压、血管疾病和糖尿病",
            "params": {
                "age": 73,
                "sex": "Male",
                "chf": True,
                "hypertension": True,
                "diabetes": True,
                "vascular_disease": True,
                "stroke": False,
                "tia": False,
                "thromboembolism": False
            },
            "expected_score": 5
        }
    ]

    print_header()

    total_tests = len(test_cases)
    passed_tests = 0
    failed_tests = 0

    # 执行测试
    for i, test_case in enumerate(test_cases, 1):
        print_test_case(i, test_case)

        try:
            # 调用计算器
            calc_result = await client.call_tool(
                "calculate",
                {
                    "calculator_id": 4,
                    "parameters": test_case["params"],
                },
            )

            # 使用 structured_content 或 data 属性获取实际数据
            calc_data = calc_result.structured_content or calc_result.data or {}

            if isinstance(calc_data, dict) and calc_data.get("success") and "result" in calc_data:
                # 成功计算
                data = calc_data["result"]
                actual_score = data.get("value")
                expected_score = test_case["expected_score"]

                # 打印计算结果
                print_calculation_result(data)

                # 验证结果
                if actual_score == expected_score:
                    print(f"- ✅ 测试通过! 期望得分: {expected_score}, 实际得分: {actual_score}")
                    passed_tests += 1
                else:
                    print(f"- ❌ 测试失败! 期望得分: {expected_score}, 实际得分: {actual_score}")
                    failed_tests += 1
            else:
                # 处理错误情况
                error_msg = calc_data.get("error", "无计算结果返回")
                print(f"- ❌ 测试失败! {error_msg}")
                failed_tests += 1

        except Exception as e:
            print(f"- ❌ 测试失败! 异常: {str(e)}")
            failed_tests += 1

        print("-" * 50)

    # 打印总结
    print_test_summary(total_tests, passed_tests, failed_tests)

    return passed_tests == total_tests


async def main():
    """主测试函数"""
    async with Client(MCP_SERVER_URL) as client:
        success = await test_cha2ds2_vasc_calculator(client)
        if success:
            print("\n🎉 所有 CHA2DS2-VASc 测试通过!")
        else:
            print("\n❌ 部分 CHA2DS2-VASc 测试失败!")
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
