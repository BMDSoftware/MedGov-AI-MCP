"""
医学计算器 MCP 服务测试运行器
简化版本 - 运行 test 文件夹下的所有测试脚本
"""

import os
import sys
import subprocess
import time
from pathlib import Path


def analyze_test_output(stdout, returncode):
    """分析测试输出，判断是否真正通过"""
    if not stdout:
        return returncode == 0

    # 检查具体的失败模式
    lines = stdout.split('\n')
    
    for line in lines:
        # 检查失败数量大于0的情况
        if "失败数:" in line and not "失败数: 0" in line:
            return False
        # 检查明确的失败消息
        if line.strip().startswith("❌") and "测试失败" in line:
            return False
        # 检查成功率不是100%
        if "成功率:" in line and not "100.0%" in line:
            return False

    # 没有发现失败标志且返回码为0，认为测试通过
    return returncode == 0


def run_test_file(test_file):
    """运行单个测试文件"""
    print(f"\n{'='*50}")
    print(f"运行测试: {test_file.name}")
    print(f"{'='*50}")

    try:
        # 设置环境变量解决Unicode输出问题
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'

        # 运行测试脚本，捕获输出
        result = subprocess.run(
            [sys.executable, str(test_file)],
            cwd=test_file.parent.parent,
            text=True,
            timeout=60,
            capture_output=True,
            encoding='utf-8',
            env=env,
        )

        # 打印测试输出
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)

        # 分析输出判断是否真正通过
        test_passed = analyze_test_output(result.stdout, result.returncode)

        if test_passed:
            print(f"✅ {test_file.name} - 测试通过")
            return True
        else:
            print(f"❌ {test_file.name} - 测试失败")
            return False

    except subprocess.TimeoutExpired:
        print(f"⏰ {test_file.name} - 测试超时")
        return False
    except Exception as e:
        print(f"💥 {test_file.name} - 运行异常: {e}")
        return False


def main():
    """主函数"""
    print("医学计算器 MCP 服务测试运行器")
    print("=" * 50)

    # 检查test目录
    test_dir = Path("test")
    if not test_dir.exists():
        print("❌ 错误: 未找到 test 目录")
        return

    # 查找所有测试文件
    test_files = list(test_dir.glob("api_test_*.py"))
    test_files.sort()

    if not test_files:
        print("❌ 未找到任何测试文件")
        return

    print(f"找到 {len(test_files)} 个测试文件:")
    for test_file in test_files:
        print(f"  - {test_file.name}")

    # 运行所有测试
    start_time = time.time()
    results = []

    for test_file in test_files:
        success = run_test_file(test_file)
        results.append((test_file.name, success))

    end_time = time.time()

    # 汇总结果
    print(f"\n{'='*50}")
    print("测试汇总")
    print(f"{'='*50}")

    total_tests = len(results)
    passed_tests = sum(1 for _, success in results if success)
    failed_tests = total_tests - passed_tests

    print(f"总测试文件数: {total_tests}")
    print(f"通过文件数: {passed_tests}")
    print(f"失败文件数: {failed_tests}")
    print(f"成功率: {(passed_tests/total_tests*100):.1f}%")
    print(f"总耗时: {(end_time-start_time):.1f}秒")

    print(f"\n详细结果:")
    for filename, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"  {filename:<45} {status}")

    if failed_tests == 0:
        print(f"\n🎉 所有测试都通过了！")
    else:
        print(f"\n⚠️  有 {failed_tests} 个测试失败")


if __name__ == "__main__":
    main()
