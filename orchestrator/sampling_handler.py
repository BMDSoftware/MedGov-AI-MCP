import os
import asyncio
from mcp.shared.context import RequestContext
from mcp import types


async def gemini_sampling_handler(
    context: RequestContext,
    params: types.CreateMessageRequestParams,
) -> types.CreateMessageResult | types.ErrorData:
    """
    MCP SamplingFnT implementation: routes sampling/createMessage requests from any
    MCP server back to Gemini. Stateless — safe to call from background threads.
    """
    parts = []
    if params.systemPrompt:
        parts.append(f"[System]\n{params.systemPrompt}\n")
    for msg in params.messages:
        content = msg.content
        if hasattr(content, "text"):
            parts.append(f"[{msg.role}]\n{content.text}")
        elif isinstance(content, list):
            for block in content:
                if hasattr(block, "text"):
                    parts.append(f"[{msg.role}]\n{block.text}")
    prompt = "\n\n".join(parts)

    try:
        from google import genai as google_genai
        from dotenv import load_dotenv
        load_dotenv()
        client = google_genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        model_id = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.models.generate_content(model=model_id, contents=prompt),
        )
        text = (response.text or "").strip()
    except Exception as e:
        return types.ErrorData(code=types.INTERNAL_ERROR, message=f"Gemini sampling failed: {e}")

    return types.CreateMessageResult(
        role="assistant",
        content=types.TextContent(type="text", text=text),
        model=model_id,
        stopReason="endTurn",
    )


def make_sampling_handler():
    """Return the gemini_sampling_handler (compatible with MCP SamplingFnT protocol)."""
    return gemini_sampling_handler
