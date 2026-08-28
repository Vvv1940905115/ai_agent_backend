"""
工具注册表（Tools Registry）

设计目标：
- 用 @tool 装饰器把任意 Python 函数注册为「Agent 可调用工具」
- 自动把函数描述 + 参数 JSON Schema 转换为 OpenAI 兼容的 function tool 格式
- 全局字典 TOOL_REGISTRY 让 BaseAgent 按名字动态分发调用

新增业务工具时，只需：
    @tool(name="my_tool", description="...", parameters={...})
    def my_tool(arg1: str) -> dict: ...
并在 Agent 初始化时把 "my_tool" 加入 tool_names 即可。
"""
import json
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class Tool:
    name: str
    description: str
    func: Callable
    parameters: dict  # OpenAI function 工具的 JSON Schema

    def to_openai_schema(self) -> dict:
        """转换为 OpenAI / 兼容接口要求的 tools 元素。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


# 全局工具表：name -> Tool
TOOL_REGISTRY: dict[str, Tool] = {}


def tool(name: Optional[str] = None, description: str = "", parameters: Optional[dict] = None):
    """
    工具装饰器。

    :param name: 工具名（默认取函数名）
    :param description: 给 LLM 看的功能说明，越清晰工具调用越准确
    :param parameters: 参数 JSON Schema，例如
        {"type":"object","properties":{"url":{"type":"string","description":"视频链接"}},"required":["url"]}
    """

    def decorator(func: Callable) -> Callable:
        tool_name = name or func.__name__
        TOOL_REGISTRY[tool_name] = Tool(
            name=tool_name,
            description=description or (func.__doc__ or "").strip(),
            func=func,
            parameters=parameters or {"type": "object", "properties": {}},
        )
        return func

    return decorator


def dispatch(tool_name: str, **kwargs) -> dict:
    """
    执行工具。所有异常在此兜底，返回统一结构，避免工具崩溃中断 Agent 循环。
    工具函数应当返回 dict；非 dict 会包成 {"result": ...}。
    """
    t = TOOL_REGISTRY.get(tool_name)
    if not t:
        return {"error": f"unknown tool: {tool_name}"}
    try:
        out = t.func(**kwargs)
        return out if isinstance(out, dict) else {"result": out}
    except Exception as e:  # 业务异常不要抛出，交给 LLM 自行判断重试
        return {"error": str(e)}


def get_tools_schema(tool_names: list[str]) -> list[dict]:
    """根据工具名列表生成 tools schema（过滤未注册项）。"""
    schemas = []
    for n in tool_names:
        if n in TOOL_REGISTRY:
            schemas.append(TOOL_REGISTRY[n].to_openai_schema())
    return schemas
