import asyncio
import json
import sys
import os
from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVER_URL


async def test_conception_calculator(client):
    """测试预计受孕日期计算器的各种功能"""

    def print_header():
        print("\n" + "=" * 60)
        print("预计受孕日期计算器测试套件")
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
            print(f"- 错误: {errors}")
        if warnings:
            print(f"- 警告: {warnings}")

    def print_calculation_result(data):
        """打印受孕日期计算结果"""
        conception_date = data.get("value", "N/A")
        unit = data.get("unit", "")
        explanation = data.get("explanation", "")
        metadata = data.get("metadata", {})
        warnings = data.get("warnings", [])

        # 基本结果
        print(f"- 预计受孕日期: {conception_date}")

        # 详细信息
        if metadata:
            menstrual_date = metadata.get("menstrual_date")
            cycle_length = metadata.get("cycle_length")
            method = metadata.get("calculation_method")

            if menstrual_date:
                print(f"- 末次月经: {menstrual_date}")
            if cycle_length:
                print(f"- 月经周期: {cycle_length} 天")
            if method:
                print(f"- 计算方法: {method}")

        # 警告信息
        if warnings:
            for warning in warnings:
                print(f"- 警告: {warning}")

        # 解释（截取前100字符）
        if explanation:
            print(f"- 解释: {explanation[:100]}...")

    def print_test_result(i, passed):
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"- 测试 {i} 结果: {status}")

    def print_summary(total, passed, failed):
        print("\n" + "=" * 60)
        print("预计受孕日期计算器测试总结")
        print("=" * 60)
        print(f"  总测试数: {total}")
        print(f"  通过数: {passed}")
        print(f"  失败数: {failed}")
        print(f"  成功率: {(passed/total*100):.1f}%")

        if failed == 0:
            print("\n✅ 所有测试都通过了！预计受孕日期计算器工作正常。")
        else:
            print(f"\n❌ {failed} 个测试失败，请检查实现。")

        print("\n测试覆盖范围:")
        features = [
            "标准月经周期计算",
            "自定义月经周期",
            "日期格式验证",
            "参数验证",
            "错误处理",
        ]
        for feature in features:
            print(f"  - {feature}")

    # Test statistics
    total_tests = 0
    passed_tests = 0

    # Test cases
    test_cases = [
        {
            "name": "Standard case",
            "params": {"menstrual_date": "01/01/2024"},
            "expected_valid": True,
            "description": "标准案例：月经日期 2024年1月1日",
        },
        {
            "name": "With custom cycle",
            "params": {"menstrual_date": "02/15/2024", "cycle_length": 30},
            "expected_valid": True,
            "description": "自定义周期：30天周期",
        },
        {
            "name": "Short cycle",
            "params": {"menstrual_date": "03/10/2024", "cycle_length": 21},
            "expected_valid": True,
            "description": "短周期：21天周期",
        },
        {
            "name": "Long cycle",
            "params": {"menstrual_date": "04/01/2024", "cycle_length": 35},
            "expected_valid": True,
            "description": "长周期：35天周期",
        },
        {
            "name": "Invalid date format",
            "params": {"menstrual_date": "2024-01-01"},
            "expected_valid": False,
            "description": "无效日期格式",
        },
        {
            "name": "Invalid cycle length",
            "params": {"menstrual_date": "01/01/2024", "cycle_length": 50},
            "expected_valid": False,
            "description": "无效周期长度",
        },
    ]

    print_header()

    for i, test_case in enumerate(test_cases, 1):
        total_tests += 1
        test_passed = True

        print_test_case(i, test_case)

        try:
            # Calculate (validation is included in calculate)
            calc_result = await client.call_tool(
                "calculate", {"calculator_id": 68, "parameters": test_case["params"]}
            )

            # 使用 structured_content 或 data 属性获取实际数据
            calc_data = calc_result.structured_content or calc_result.data or {}

            if isinstance(calc_data, dict) and calc_data.get("success") and "result" in calc_data:
                # 成功计算
                data = calc_data["result"]
                print_calculation_result(data)

                # 检查是否符合预期（有效参数应该成功计算）
                if not test_case["expected_valid"]:
                    print("- ❌ 预期参数无效但计算成功")
                    test_passed = False
                else:
                    print("- ✅ 计算成功")
            else:
                # 计算失败
                error_msg = calc_data.get("error", "Unknown error")
                print(f"- 计算失败: {error_msg}")

                # 检查是否符合预期（无效参数应该失败）
                if test_case["expected_valid"]:
                    print("- ❌ 预期参数有效但计算失败")
                    test_passed = False
                else:
                    print("- ✅ 正确拒绝无效参数")

        except Exception as e:
            print(f"- ❌ 测试错误: {e}")
            test_passed = False

        if test_passed:
            passed_tests += 1

        print_test_result(i, test_passed)

    print_summary(total_tests, passed_tests, total_tests - passed_tests)
    return passed_tests, total_tests - passed_tests


async def test_gestational_age_calculator(client):
    """测试预计妊娠期计算器的各种功能"""

    def print_header():
        print("\n" + "=" * 60)
        print("预计妊娠期计算器测试套件")
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
            print(f"- 错误: {errors}")
        if warnings:
            print(f"- 警告: {warnings}")

    def print_calculation_result(data):
        """打印妊娠期计算结果"""
        gestational_age = data.get("value", "N/A")
        unit = data.get("unit", "")
        explanation = data.get("explanation", "")
        metadata = data.get("metadata", {})
        warnings = data.get("warnings", [])

        # 基本结果 - 处理元组/列表格式
        if isinstance(gestational_age, (tuple, list)) and len(gestational_age) == 2:
            weeks_str, days_str = gestational_age
            print(f"- 妊娠期: {weeks_str}, {days_str}")
        else:
            print(f"- 妊娠期: {gestational_age}")

        # 详细信息
        if metadata:
            menstrual_date = metadata.get("menstrual_date")
            current_date = metadata.get("current_date")
            total_days = metadata.get("total_days")
            weeks = metadata.get("weeks")
            days = metadata.get("days")
            trimester = metadata.get("trimester")
            method = metadata.get("calculation_method")

            if menstrual_date:
                print(f"- 末次月经: {menstrual_date}")
            if current_date:
                print(f"- 当前日期: {current_date}")
            if total_days is not None:
                print(f"- 总天数: {total_days} 天")
            if weeks is not None and days is not None:
                print(f"- 详细: {weeks} 周 {days} 天")
            if trimester:
                print(f"- 妊娠期: {trimester} trimester")
            if method:
                print(f"- 计算方法: {method}")

        # 警告信息
        if warnings:
            for warning in warnings:
                print(f"- 警告: {warning}")

        # 解释（截取前100字符）
        if explanation:
            print(f"- 解释: {explanation[:100]}...")

    def print_test_result(i, passed):
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"- 测试 {i} 结果: {status}")

    def print_summary(total, passed, failed):
        print("\n" + "=" * 60)
        print("预计妊娠期计算器测试总结")
        print("=" * 60)
        print(f"  总测试数: {total}")
        print(f"  通过数: {passed}")
        print(f"  失败数: {failed}")
        print(f"  成功率: {(passed/total*100):.1f}%")

        if failed == 0:
            print("\n✅ 所有测试都通过了！预计妊娠期计算器工作正常。")
        else:
            print(f"\n❌ {failed} 个测试失败，请检查实现。")

        print("\n测试覆盖范围:")
        features = [
            "早期妊娠计算",
            "中期妊娠计算",
            "晚期妊娠计算",
            "妊娠期阶段判断",
            "日期格式验证",
            "参数验证",
            "错误处理",
        ]
        for feature in features:
            print(f"  - {feature}")

    # Test statistics
    total_tests = 0
    passed_tests = 0

    # Test cases
    test_cases = [
        {
            "name": "Early pregnancy",
            "params": {"menstrual_date": "01/01/2024", "current_date": "02/15/2024"},
            "expected_valid": True,
            "description": "早期妊娠：6周多",
        },
        {
            "name": "Mid pregnancy",
            "params": {"menstrual_date": "01/01/2024", "current_date": "04/15/2024"},
            "expected_valid": True,
            "description": "中期妊娠：约15周",
        },
        {
            "name": "Late pregnancy",
            "params": {"menstrual_date": "01/01/2024", "current_date": "09/15/2024"},
            "expected_valid": True,
            "description": "晚期妊娠：约37周",
        },
        {
            "name": "Just days",
            "params": {"menstrual_date": "01/01/2024", "current_date": "01/05/2024"},
            "expected_valid": True,
            "description": "仅几天：4天",
        },
        {
            "name": "Invalid date format",
            "params": {"menstrual_date": "2024-01-01", "current_date": "02/15/2024"},
            "expected_valid": False,
            "description": "无效日期格式",
        },
        {
            "name": "Current date before menstrual",
            "params": {"menstrual_date": "01/01/2024", "current_date": "12/31/2023"},
            "expected_valid": False,
            "description": "当前日期早于月经日期",
        },
        {
            "name": "Missing current date",
            "params": {"menstrual_date": "01/01/2024"},
            "expected_valid": False,
            "description": "缺少当前日期",
        },
    ]

    print_header()

    for i, test_case in enumerate(test_cases, 1):
        total_tests += 1
        test_passed = True

        print_test_case(i, test_case)

        try:
            # Calculate (validation is included in calculate)
            calc_result = await client.call_tool(
                "calculate", {"calculator_id": 69, "parameters": test_case["params"]}
            )

            # 使用 structured_content 或 data 属性获取实际数据
            calc_data = calc_result.structured_content or calc_result.data or {}

            if isinstance(calc_data, dict) and calc_data.get("success") and "result" in calc_data:
                # 成功计算
                data = calc_data["result"]
                print_calculation_result(data)

                # 检查是否符合预期（有效参数应该成功计算）
                if not test_case["expected_valid"]:
                    print("- ❌ 预期参数无效但计算成功")
                    test_passed = False
                else:
                    print("- ✅ 计算成功")
            else:
                # 计算失败
                error_msg = calc_data.get("error", "Unknown error")
                print(f"- 计算失败: {error_msg}")

                # 检查是否符合预期（无效参数应该失败）
                if test_case["expected_valid"]:
                    print("- ❌ 预期参数有效但计算失败")
                    test_passed = False
                else:
                    print("- ✅ 正确拒绝无效参数")

        except Exception as e:
            print(f"- ❌ 测试错误: {e}")
            test_passed = False

        if test_passed:
            passed_tests += 1

        print_test_result(i, test_passed)

    print_summary(total_tests, passed_tests, total_tests - passed_tests)
    return passed_tests, total_tests - passed_tests


async def test_due_date_calculator(client):
    """测试预计分娩日期计算器的各种功能"""

    def print_header():
        print("\n" + "=" * 60)
        print("预计分娩日期计算器测试套件")
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
            print(f"- 错误: {errors}")
        if warnings:
            print(f"- 警告: {warnings}")

    def print_calculation_result(data):
        """打印分娩日期计算结果"""
        due_date = data.get("value", "N/A")
        unit = data.get("unit", "")
        explanation = data.get("explanation", "")
        metadata = data.get("metadata", {})
        warnings = data.get("warnings", [])

        # 基本结果
        print(f"- 预计分娩日期: {due_date}")

        # 详细信息
        if metadata:
            menstrual_date = metadata.get("menstrual_date")
            cycle_length = metadata.get("cycle_length")
            method = metadata.get("method")
            gestational_weeks = metadata.get("gestational_weeks")

            if menstrual_date:
                print(f"- 末次月经: {menstrual_date}")
            if cycle_length:
                print(f"- 月经周期: {cycle_length}天")
            if method:
                print(f"- 计算方法: {method}")
            if gestational_weeks:
                print(f"- 妊娠周数: {gestational_weeks}周")

        # 警告信息
        if warnings:
            for warning in warnings:
                print(f"- {warning}")

        # 计算解释
        if explanation:
            print(f"- 计算说明: {explanation[:100]}..." if len(explanation) > 100 else f"- 计算说明: {explanation}")

    def print_test_result(test_num, passed):
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"\n测试 {test_num:2d} 结果: {status}")

    def print_summary(total, passed, failed):
        print("\n" + "=" * 60)
        print("预计分娩日期计算器测试总结")
        print("=" * 60)
        print(f"总测试数: {total}")
        print(f"通过数: {passed}")
        print(f"失败数: {failed}")
        if total > 0:
            print(f"成功率: {(passed/total*100):.1f}%")

        if failed == 0:
            print("\n✅ 预计分娩日期计算器所有测试都通过了！")
        else:
            print(f"\n❌ {failed} 个测试失败，请检查预计分娩日期计算器实现。")

    # 测试用例定义
    test_cases = [
        {
            "name": "标准28天周期",
            "description": "使用标准28天月经周期计算预计分娩日期",
            "params": {"menstrual_date": "01/01/2024", "cycle_length": 28},
            "expected_valid": True,
            "expected_due_date": "10/07/2024",
        },
        {
            "name": "短周期21天",
            "description": "使用21天月经周期计算预计分娩日期",
            "params": {"menstrual_date": "01/01/2024", "cycle_length": 21},
            "expected_valid": True,
            "expected_due_date": "09/30/2024",  # 参考文件逻辑：21-28=-7天
        },
        {
            "name": "短周期27天",
            "description": "使用27天月经周期计算预计分娩日期（验证参考文件逻辑）",
            "params": {"menstrual_date": "12/01/2003", "cycle_length": 27},
            "expected_valid": True,
            "expected_due_date": "09/05/2004",  # 参考文件逻辑：27-28=-1天
        },
        {
            "name": "长周期35天",
            "description": "使用35天月经周期计算预计分娩日期",
            "params": {"menstrual_date": "01/01/2024", "cycle_length": 35},
            "expected_valid": True,
            "expected_due_date": "10/14/2024",  # 参考文件逻辑：35-28=+7天
        },
        {
            "name": "默认周期长度",
            "description": "不指定周期长度，使用默认28天",
            "params": {"menstrual_date": "03/15/2024"},
            "expected_valid": True,
            "expected_due_date": "12/20/2024",
        },
        {
            "name": "跨年计算",
            "description": "末次月经在年末，分娩日期在次年",
            "params": {"menstrual_date": "12/25/2023", "cycle_length": 28},
            "expected_valid": True,
            "expected_due_date": "09/30/2024",
        },
        {
            "name": "闰年计算",
            "description": "在闰年进行计算",
            "params": {"menstrual_date": "02/29/2024", "cycle_length": 28},
            "expected_valid": True,
            "expected_due_date": "12/05/2024",
        },
        {
            "name": "无效日期格式",
            "description": "使用错误的日期格式",
            "params": {"menstrual_date": "2024-01-01", "cycle_length": 28},
            "expected_valid": False,
        },
        {
            "name": "缺少末次月经日期",
            "description": "不提供末次月经日期",
            "params": {"cycle_length": 28},
            "expected_valid": False,
        },
        {
            "name": "边界短周期20天",
            "description": "使用20天周期（正常范围外但医学可接受）",
            "params": {"menstrual_date": "01/01/2024", "cycle_length": 20},
            "expected_valid": True,
            "expected_due_date": "09/29/2024",  # 参考文件逻辑：20-28=-8天
        },
        {
            "name": "边界长周期36天",
            "description": "使用36天周期（正常范围外但医学可接受）",
            "params": {"menstrual_date": "01/01/2024", "cycle_length": 36},
            "expected_valid": True,
            "expected_due_date": "10/15/2024",  # 参考文件逻辑：36-28=+8天
        },
        {
            "name": "极短周期13天",
            "description": "周期长度小于医学下限14天",
            "params": {"menstrual_date": "01/01/2024", "cycle_length": 13},
            "expected_valid": False,
        },
        {
            "name": "极长周期46天",
            "description": "周期长度大于医学上限45天",
            "params": {"menstrual_date": "01/01/2024", "cycle_length": 46},
            "expected_valid": False,
        },
        {
            "name": "非数字周期长度",
            "description": "周期长度为非数字值",
            "params": {"menstrual_date": "01/01/2024", "cycle_length": "invalid"},
            "expected_valid": False,
        },
        {
            "name": "无效日期",
            "description": "使用不存在的日期",
            "params": {"menstrual_date": "02/30/2024", "cycle_length": 28},
            "expected_valid": False,
        },
    ]

    print_header()

    total_tests = len(test_cases)
    passed_tests = 0

    for i, test_case in enumerate(test_cases, 1):
        print_test_case(i, test_case)
        test_passed = True

        try:
            # 调用计算器
            calc_result = await client.call_tool(
                "calculate", {"calculator_id": 13, "parameters": test_case["params"]}
            )

            # 使用 structured_content 或 data 属性获取实际数据
            calc_data = calc_result.structured_content or calc_result.data or {}

            if isinstance(calc_data, dict) and calc_data.get("success") and "result" in calc_data:
                # 成功计算
                data = calc_data["result"]
                print_validation_result(test_case["expected_valid"], True)

                if not test_case["expected_valid"]:
                    # 期望无效但实际有效
                    print("- ❌ 预期参数无效但计算成功")
                    test_passed = False
                else:
                    # 打印计算结果
                    print_calculation_result(data)
                    print("- ✅ 计算成功")

                    # 检查预期结果
                    if "expected_due_date" in test_case:
                        actual_due_date = data.get("value")
                        expected_due_date = test_case["expected_due_date"]
                        if actual_due_date != expected_due_date:
                            print(f"- ❌ 日期不匹配: 期望 {expected_due_date}, 实际 {actual_due_date}")
                            test_passed = False
                        else:
                            print(f"- ✅ 日期匹配: {actual_due_date}")
            else:
                # 计算失败
                error_msg = calc_data.get("error", "Unknown error")
                print(f"- 计算失败: {error_msg}")
                print_validation_result(test_case["expected_valid"], False, errors=error_msg)

                # 检查是否符合预期（无效参数应该失败）
                if test_case["expected_valid"]:
                    print("- ❌ 预期参数有效但计算失败")
                    test_passed = False
                else:
                    print("- ✅ 正确拒绝无效参数")

        except Exception as e:
            print(f"- ❌ 测试错误: {e}")
            test_passed = False

        if test_passed:
            passed_tests += 1

        print_test_result(i, test_passed)

    print_summary(total_tests, passed_tests, total_tests - passed_tests)
    return passed_tests, total_tests - passed_tests


async def main():
    def print_header():
        print("妊娠计算器 MCP 测试")
        print("=" * 60)

    def print_connection_status(success, error=None):
        if success:
            print("✅ 成功连接到 MCP 服务器")
        else:
            print(f"❌ 连接失败: {error}")

    def print_overall_results(
        conception_passed, conception_failed, gestational_passed, gestational_failed, due_date_passed, due_date_failed
    ):
        total_passed = conception_passed + gestational_passed + due_date_passed
        total_failed = conception_failed + gestational_failed + due_date_failed
        total_tests = total_passed + total_failed

        if total_tests == 0:
            return

        print("\n" + "=" * 60)
        print("妊娠计算器整体测试结果")
        print("=" * 60)
        print(f"总测试数: {total_tests}")
        print(f"通过数: {total_passed}")
        print(f"失败数: {total_failed}")
        print(f"成功率: {(total_passed/total_tests*100):.1f}%")

        print(f"\n预计受孕日期计算器: {conception_passed}/{conception_passed + conception_failed}")
        print(f"预计妊娠期计算器: {gestational_passed}/{gestational_passed + gestational_failed}")
        print(f"预计分娩日期计算器: {due_date_passed}/{due_date_passed + due_date_failed}")

        if total_failed == 0:
            print("\n✅ 妊娠计算器所有测试都通过了！")
        else:
            print(f"\n❌ {total_failed} 个测试失败，请检查妊娠计算器实现。")

    print_header()

    try:
        async with Client(MCP_SERVER_URL) as client:
            print_connection_status(True)

            # Test conception calculator
            conception_passed, conception_failed = await test_conception_calculator(client)

            # Test gestational age calculator
            gestational_passed, gestational_failed = await test_gestational_age_calculator(client)

            # Test due date calculator
            due_date_passed, due_date_failed = await test_due_date_calculator(client)

            print_overall_results(
                conception_passed,
                conception_failed,
                gestational_passed,
                gestational_failed,
                due_date_passed,
                due_date_failed,
            )

    except Exception as e:
        print_connection_status(False, str(e))
        import traceback

        traceback.print_exc()
        return


if __name__ == "__main__":
    asyncio.run(main())
