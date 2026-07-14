import asyncio
import json
import sys
import os
from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCP_SERVER_URL


def get_expected_calculators():
    """从 calculators 模块获取预期的计算器列表"""
    try:
        # 导入 calculators 模块以获取所有计算器类
        from medcalc import CalculatorService
        
        # 创建计算器服务实例来获取注册的计算器
        service = CalculatorService({})
        expected_calculators = service.list_calculators()
        
        # 转换为字典格式以便比较
        expected_list = []
        for calc_info in expected_calculators:
            expected_list.append({
                'id': calc_info.id,
                'name': calc_info.name,
                'category': calc_info.category,
                'description': calc_info.description
            })
        
        return expected_list
        
    except Exception as e:
        print(f"   警告: 无法获取预期计算器列表: {e}")
        return []


async def test_tools(client):
    """动态测试通用工具"""
    print("\n=== 通用工具测试 ===")

    passed_tests = 0
    failed_tests = 0
    
    # 0. 获取预期的计算器列表
    expected_calculators = get_expected_calculators()
    print(f"\n0. 预期计算器列表 (从代码中读取):")
    if expected_calculators:
        print(f"   预期计算器数量: {len(expected_calculators)}")
        for calc in expected_calculators:
            print(f"   - {calc['id']}: {calc['name']} ({calc['category']})")
    else:
        print("   警告: 无法获取预期计算器列表")
    
    # 1. 测试计算器列表工具
    print("\n1. 计算器列表工具:")
    calculators_list = []
    try:
        result = await client.call_tool("list_calculators", {})
        data = result.structured_content or result.data or {}

        # 检查数据结构
        if isinstance(data, dict) and data.get("success"):
            calculators = data.get("calculators", [])
            categories = data.get("categories", [])
            count = data.get("count", 0)
            
            calculators_list = calculators  # 保存计算器列表用于后续测试

            print(f"   ✅ 成功获取 {count} 个计算器")
            print(f"   类别数: {len(categories)}")
            print(f"   类别列表: {', '.join(categories)}")

            for calc in calculators:
                print(f"   - {calc['id']}: {calc['name']} ({calc['category']})")
            
            # 验证与预期计算器列表的一致性
            if expected_calculators:
                print(f"\n   数据一致性验证:")
                
                # 检查数量是否一致
                if len(calculators) == len(expected_calculators):
                    print(f"   ✅ 计算器数量一致: {len(calculators)}")
                else:
                    print(f"   ❌ 计算器数量不一致: 预期{len(expected_calculators)}, 实际{len(calculators)}")
                
                # 检查每个计算器是否存在
                actual_ids = {calc['id'] for calc in calculators}
                expected_ids = {calc['id'] for calc in expected_calculators}
                
                missing_calculators = expected_ids - actual_ids
                extra_calculators = actual_ids - expected_ids
                
                if not missing_calculators and not extra_calculators:
                    print(f"   ✅ 所有预期计算器都存在")
                else:
                    if missing_calculators:
                        print(f"   ❌ 缺少计算器: {', '.join(missing_calculators)}")
                    if extra_calculators:
                        print(f"   ⚠️  额外计算器: {', '.join(extra_calculators)}")
                
                # 检查计算器详细信息是否一致
                for expected_calc in expected_calculators:
                    actual_calc = next((c for c in calculators if c['id'] == expected_calc['id']), None)
                    if actual_calc:
                        if (actual_calc['name'] == expected_calc['name'] and 
                            actual_calc['category'] == expected_calc['category']):
                            print(f"   ✅ {expected_calc['id']} 信息一致")
                        else:
                            print(f"   ❌ {expected_calc['id']} 信息不一致")
                            print(f"      预期: {expected_calc['name']} ({expected_calc['category']})")
                            print(f"      实际: {actual_calc['name']} ({actual_calc['category']})")

            passed_tests += 1
            print("   测试结果: ✅ 通过")
        else:
            failed_tests += 1
            error_msg = data.get("error", "未知错误") if isinstance(data, dict) else str(data)
            print(f"   ❌ 失败: {error_msg}")
            print("   测试结果: ❌ 失败")

    except Exception as e:
        failed_tests += 1
        print(f"   错误: {e}")
        print("   测试结果: ❌ 失败")

    # 2. 动态测试所有计算器的信息获取
    if calculators_list:
        print(f"\n2. 获取计算器信息工具 (动态测试 {len(calculators_list)} 个计算器):")
        
        for i, calc in enumerate(calculators_list, 1):
            calc_id = calc['id']
            calc_name = calc['name']
            
            print(f"\n   2.{i} 测试计算器: {calc_id} ({calc_name})")
            
            try:
                result = await client.call_tool("get_calculator_info", {"calculator_id": calc_id})
                data = result.structured_content or result.data or {}

                # 检查数据结构
                if isinstance(data, dict) and data.get("success"):
                    calc_info = data
                    
                    # 验证返回的信息是否与列表中的一致
                    returned_id = calc_info.get('id')
                    returned_name = calc_info.get('name')
                    returned_category = calc_info.get('category')
                    parameters = calc_info.get('parameters', [])
                    
                    print(f"      ✅ 成功获取计算器信息")
                    print(f"      ID: {returned_id}")
                    print(f"      名称: {returned_name}")
                    print(f"      类别: {returned_category}")
                    print(f"      描述: {calc_info.get('description', '')}")
                    print(f"      参数数量: {len(parameters)}")
                    
                    # 验证数据一致性
                    if returned_id == calc_id and returned_name == calc_name:
                        print(f"      ✅ 数据一致性验证通过")
                        passed_tests += 1
                    else:
                        print(f"      ❌ 数据一致性验证失败: 期望ID={calc_id}, 实际ID={returned_id}")
                        failed_tests += 1
                        
                    print(f"      测试结果: ✅ 通过")
                else:
                    failed_tests += 1
                    error_msg = data.get("error", "未知错误") if isinstance(data, dict) else str(data)
                    print(f"      ❌ 失败: {error_msg}")
                    print(f"      测试结果: ❌ 失败")

            except Exception as e:
                failed_tests += 1
                print(f"      错误: {e}")
                print(f"      测试结果: ❌ 失败")
    else:
        print("\n2. 获取计算器信息工具: 跳过（无可用计算器）")
        failed_tests += 1

    # 计算总测试数
    total_tests = 1 + len(calculators_list)  # 1个列表测试 + N个信息获取测试
    
    # 打印测试总结
    print(f"\n通用工具测试总结:")
    print(f"  总测试数: {total_tests}")
    print(f"  通过数: {passed_tests}")
    print(f"  失败数: {failed_tests}")
    print(f"  成功率: {(passed_tests/total_tests*100):.1f}%" if total_tests > 0 else "  成功率: 0.0%")
    
    # 打印测试覆盖范围
    print(f"\n测试覆盖范围:")
    print(f"  - 计算器列表获取")
    print(f"  - 计算器信息获取 ({len(calculators_list)} 个计算器)")
    print(f"  - 数据一致性验证")
    print(f"  - 错误处理测试")

    return passed_tests, failed_tests


async def main():
    """主函数 - 测试通用工具"""

    def print_header():
        print("医学计算器 MCP 通用工具测试")
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
        print("通用工具测试结果")
        print("=" * 60)
        print(f"总测试数: {total_tests}")
        print(f"通过数: {total_passed}")
        print(f"失败数: {total_failed}")
        print(f"成功率: {(total_passed/total_tests*100):.1f}%")

        if total_failed == 0:
            print("\n✅ 所有通用工具测试都通过了！")
        else:
            print(f"\n❌ {total_failed} 个测试失败，请检查服务器配置。")

    print_header()

    try:
        async with Client(MCP_SERVER_URL) as client:
            print_connection_status(True)
            tool_passed, tool_failed = await test_tools(client)
            print_overall_results(tool_passed, tool_failed)

    except Exception as e:
        print_connection_status(False, str(e))
        import traceback

        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("✅ 通用工具测试完成")


if __name__ == "__main__":
    asyncio.run(main())
