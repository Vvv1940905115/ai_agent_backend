"""
通用 Agent 基类（工具调用循环 / ReAct 风格）

核心能力：
1. 维护 system prompt 与可用工具集合
2. 与 LLM 多轮对话：LLM 返回 tool_calls 时，自动执行工具并把结果回灌，直到 LLM 产出最终文本
3. 带最大迭代上限，防止无限循环
4. 支持 memory（按 conversation_id 记忆历史）

子类只需定义 system_prompt 与 tool_names 即可快速搭建业务 Agent。
"""
import json
from typing import Optional

from app.agent.llm import get_active_llm
from app.agent.tool import dispatch, get_tools_schema
from app.core.logging import get_logger

logger = get_logger("agent")


class BaseAgent:
    name: str = "base"
    system_prompt: str = "你是一个乐于助人的企业 AI 助手，可调用工具完成任务。"
    tool_names: list[str] = []

    def __init__(self, max_iterations: int = 6, temperature: float = 0.3):
        self.max_iterations = max_iterations
        self.temperature = temperature
        # 会话记忆：conversation_id -> messages
        self._memory: dict[str, list[dict]] = {}

    # ---------- 记忆管理 ----------
    def _history(self, conversation_id: Optional[str]) -> list[dict]:
        if conversation_id and conversation_id in self._memory:
            return self._memory[conversation_id]
        return [{"role": "system", "content": self.system_prompt}]

    def _save(self, conversation_id: Optional[str], messages: list[dict]) -> None:
        if conversation_id:
            self._memory[conversation_id] = messages

    # ---------- 主入口 ----------
    def run(self, user_input: str, conversation_id: Optional[str] = None) -> dict:
        """
        执行一次用户任务。

        :return: {"content": str, "iterations": int, "tool_calls": list}
        """
        messages = self._history(conversation_id)
        messages.append({"role": "user", "content": user_input})

        tools_schema = get_tools_schema(self.tool_names)
        llm = get_active_llm()
        used_tools: list[str] = []

        for i in range(self.max_iterations):
            try:
                resp = llm.chat(
                    messages=messages,
                    tools=tools_schema or None,
                    temperature=self.temperature,
                )
            except Exception as e:
                logger.exception("LLM 调用失败")
                return {"content": f"LLM 调用失败: {e}", "iterations": i + 1, "tool_calls": used_tools}

            msg = resp.choices[0].message

            # 没有工具调用 -> 任务完成，返回最终文本
            if not msg.tool_calls:
                messages.append({"role": "assistant", "content": msg.content or ""})
                self._save(conversation_id, messages)
                return {"content": msg.content or "", "iterations": i + 1, "tool_calls": used_tools}

            # 有工具调用 -> 执行并把结果回灌
            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in msg.tool_calls
                ],
            })
            for tc in msg.tool_calls:
                fn_name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                logger.info("[%s] 调用工具 %s(%s)", self.name, fn_name, args)
                result = dispatch(tool_name=fn_name, **args)
                used_tools.append(fn_name)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": fn_name,
                    "content": json.dumps(result, ensure_ascii=False),
                })

        # 达到最大迭代仍未产出文本
        return {
            "content": "（已达到最大工具调用轮次，请简化任务或提高 max_iterations）",
            "iterations": self.max_iterations,
            "tool_calls": used_tools,
        }
