import datetime
import httpx
import json
import sys
import os
import asyncio
import re
from json_repair import repair_json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import BASE_URL, API_KEY, MCP_SERVER_URL
from fastmcp import Client

# from jinja2 import Template


system_prompt_1 = """In this environment you have access to a set of functions you can call to answer the user's question. You can use one or more function calls per message, and will receive the result of that function call in the user's response. You use function calls step-by-step to accomplish a given task, with each function call informed by the result of the previous function call.

# Task Analysis and Planning

Before taking any action or responding to the user, carefully analyze the request:
- Identify the specific requirements and constraints that apply
- Check if all required information is available or needs to be collected
- Verify that your planned approach complies with all applicable rules and policies
- Review function call results for accuracy and completeness before proceeding
- Plan your sequence of function calls to efficiently accomplish the task

Here are examples of how to properly use the medical calculator tools:

## Example: User asks "Calculate my BMI with height 175cm and weight 70kg"

1. First call:
<tool_call>
{"name": "list_calculators", "arguments": {}}
</tool_call>

2. First Result: [{"id": "bmi", "name": "BMI Calculator", "category": "anthropometry", "description": "Calculate Body Mass Index"}, {"id": "bsa", "name": "BSA Calculator", "category": "anthropometry", "description": "Calculate Body Surface Area"}, ...]

3. Second call:
<tool_call>
{"name": "calculate", "arguments": {"calculator_id": "bmi", "parameters": {"height": "175cm", "weight": "70kg"}}}
</tool_call>

4. Second Result: {"success": true, "result": {"bmi": 22.86, "category": "Normal weight", "interpretation": "Your BMI is in the normal range. This indicates a healthy weight for your height."}, "details": {"height_m": 1.75, "weight_kg": 70.0, "formula": "BMI = weight(kg) / height(m)²"}}

5. Response: Based on your height of 175cm and weight of 70kg, your BMI is 22.86, which falls in the "Normal weight" category. This indicates a healthy weight for your height.

# Function Call Rules
Here are the rules you should always follow to solve your task:
1. Always use the right arguments for the functions. Never use variable names as the action arguments, use the value instead.
2. Call a function only when needed: do not call the function if you do not need information, try to solve the task yourself.
3. If no function call is needed, just answer the question directly.
4. Never re-do a function call that you previously did with the exact same parameters.
5. Response in user query language."""


system_prompt_2 = "## Using the think tool\n\nBefore taking any action or responding to the user after receiving tool results, use the think tool as a scratchpad to:\n- List the specific rules that apply to the current request\n- Check if all required information is collected\n- Verify that the planned action complies with all policies\n- Iterate over tool results for correctness \n- Response in user query language\n\nHere are some examples of what to iterate over inside the think tool:\n<think_tool_example_1>\nUser wants to cancel flight ABC123\n- Need to verify: user ID, reservation ID, reason\n- Check cancellation rules:\n  * Is it within 24h of booking?\n  * If not, check ticket class and insurance\n- Verify no segments flown or are in the past\n- Plan: collect missing info, verify rules, get confirmation\n</think_tool_example_1>\n\n<think_tool_example_2>\nUser wants to book 3 tickets to NYC with 2 checked bags each\n- Need user ID to check:\n  * Membership tier for baggage allowance\n  * Which payments methods exist in profile\n- Baggage calculation:\n  * Economy class × 3 passengers\n  * If regular member: 1 free bag each → 3 extra bags = $150\n  * If silver member: 2 free bags each → 0 extra bags = $0\n  * If gold member: 3 free bags each → 0 extra bags = $0\n- Payment rules to verify:\n  * Max 1 travel certificate, 1 credit card, 3 gift cards\n  * All payment methods must be in profile\n  * Travel certificate remainder goes to waste\n- Plan:\n1. Get user ID\n2. Verify membership level for bag fees\n3. Check which payment methods in profile and if their combination is allowed\n4. Calculate total: ticket price + any bag fees\n5. Get explicit confirmation for booking\n</think_tool_example_2>"


dummy_server_think_tool = {
    "type": "function",
    "function": {
        "name": "dummy-server-think",
        "parameters": {
            "type": "object",
            "required": ["thought"],
            "properties": {"thought": {"type": "string", "description": "Your thoughts."}},
        },
        "description": "Use the tool to think about something. It will not obtain new information or make any changes to the repository, but just log the thought. Use it when complex reasoning or brainstorming is needed. For example, if you explore the repo and discover the source of a bug, call this tool to brainstorm several unique ways of fixing the bug, and assess which change(s) are likely to be simplest and most effective. Alternatively, if you receive some test results, call this tool to brainstorm ways to fix the failing tests.",
    },
}


def parse_tool_calls(content):
    """
    解析自定义格式的工具调用: <tool_call>JSON对象</tool_call>
    返回解析后的工具调用列表
    """
    if not content:
        return []

    # 使用正则表达式匹配 <tool_call>...</tool_call> 标签
    pattern = r"<tool_call>(.*?)</tool_call>"
    matches = re.findall(pattern, content, re.DOTALL)

    tool_calls = []
    for i, match in enumerate(matches):
        try:
            # 使用 json_repair 修复和解析 JSON
            json_str = match.strip()
            repaired_json = repair_json(json_str)
            tool_data = json.loads(repaired_json)

            # 转换为标准的 OpenAI 工具调用格式
            tool_call = {
                "id": f"call_{i+1}",  # 生成唯一ID
                "type": "function",
                "function": {
                    "name": tool_data.get("name", ""),
                    "arguments": json.dumps(tool_data.get("arguments", {}), ensure_ascii=False),
                },
            }
            tool_calls.append(tool_call)

        except Exception as e:
            print(f"解析工具调用失败: {match[:100]}... 错误: {str(e)}")
            continue

    return tool_calls


def clean_schema(schema):
    if isinstance(schema, dict):
        if "additionalProperties" in schema:
            del schema["additionalProperties"]

        for key, value in schema.items():
            if isinstance(value, dict):
                clean_schema(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        clean_schema(item)

    return schema


async def main():
    # with open("qwen3.jinja", "r", encoding="utf-8") as f:
    #     template = Template(f.read())

    mcp_client = Client(MCP_SERVER_URL)
    http_client = httpx.Client(timeout=60)

    async with mcp_client:
        # 获取MCP工具列表
        tools = await mcp_client.list_tools()
        mcp_tools = []
        for tool in tools:
            tool = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": clean_schema(tool.inputSchema),
                },
            }
            mcp_tools.append(tool)

        # mcp_tools.append(dummy_server_think_tool)
        # tool_prompt = template.render(messages=[{}], tools=mcp_tools)

        # 初始化消息列表
        messages = [
            {"role": "system", "content": system_prompt_1},
            # {"role": "user", "content": "LMP：2023.07.22\n当前：2024.05.02\n计算孕周"},
            {"role": "user", "content": "请使用中文回答以下问题：患者肺部肿瘤直径 4.5 厘米，侵犯胸壁，有肺门淋巴结转移，无远处转移，计算TNM分期。"}
        ]

        max_iterations = 10  # 防止无限循环
        iteration = 0
        has_made_tool_calls = False  # 跟踪是否已经进行过工具调用

        print("=== 开始LLM API调用循环 ===")

        while iteration < max_iterations:
            iteration += 1
            print(f"\n--- 第 {iteration} 轮调用 ---")

            # 调用LLM API
            print("调用LLM API...")
            response = http_client.post(
                url=f"{BASE_URL}/v1/chat/completions",
                json={"messages": messages, "tools": mcp_tools, "model": "gemini-2.5-flash"},
                headers={"Authorization": f"Bearer {API_KEY}"},
            )

            if response.status_code != 200:
                print(f"\n🔄 API调用失败: {response.status_code}，重试({iteration})...")
                continue

            data = response.json()
            assistant_message = data.get("choices")[0].get("message")

            # 将助手消息添加到对话历史
            messages.append(assistant_message)

            # 检查是否有工具调用（使用自定义格式解析）
            content = assistant_message.get("content", "")
            # tool_calls = parse_tool_calls(content)
            tool_calls = assistant_message.get("tool_calls", [])

            if not tool_calls:
                if has_made_tool_calls:
                    print("\n🎉 没有更多工具调用，循环结束")
                    print("\n最终回答:")
                    print(content)
                    break
                else:
                    print(f"\n🔄 尚未进行工具调用，重试({iteration})...")
                    continue

            print(f"\n🔧 检测到 {len(tool_calls)} 个工具调用")
            has_made_tool_calls = True  # 标记已经进行过工具调用

            # 执行所有工具调用
            tool_results = []
            for tool_call in tool_calls:
                function_name = tool_call["function"]["name"]
                function_args = json.loads(tool_call["function"]["arguments"])
                tool_call_id = tool_call["id"]

                print(f"  调用工具: {function_name}")
                print(f"  参数: {function_args}")

                # 调用MCP工具
                try:
                    mcp_result = await mcp_client.call_tool(function_name, function_args)
                    result = mcp_result.structured_content or mcp_result.data or {}
                except Exception as e:
                    result = {}

                if result == {}:
                    result = {
                        "error": "工具调用失败",
                        "timestamp": datetime.now().isoformat(),
                        "success": False,
                    }

                print(f"  结果: {result}")

                # 构建工具结果消息
                tool_result_message = {
                    "role": "tool",
                    "content": json.dumps(result, ensure_ascii=False),
                    "tool_call_id": tool_call_id,
                }
                tool_results.append(tool_result_message)

            # 将工具结果添加到消息历史
            messages.extend(tool_results)

            print(f"\n已完成第 {iteration} 轮，继续下一轮...")

        if iteration >= max_iterations:
            print(f"\n⚠️ 达到最大迭代次数 ({max_iterations})，循环结束")

        print("\n=== 完整对话历史 ===")
        for i, msg in enumerate(messages):
            print(f"消息 {i+1}: {msg['role']}")
            if msg["role"] == "tool":
                print(
                    f"  工具结果: {msg['content'][:200]}..."
                    if len(msg["content"]) > 200
                    else f"  工具结果: {msg['content']}"
                )
            else:
                content = msg.get("content", "")
                if content:
                    print(f"  内容: {content[:200]}..." if len(content) > 200 else f"  内容: {content}")
                if msg.get("tool_calls"):
                    print(f"  工具调用数量: {len(msg['tool_calls'])}")

    http_client.close()


if __name__ == "__main__":
    asyncio.run(main())
