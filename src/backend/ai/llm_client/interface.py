"""LLM 客户端抽象接口。

所有 LLM 后端（本地 llama.cpp / DeepSeek API / Ollama / 桩）必须实现此接口。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator, Dict, List, Optional


class BaseLLMClient(ABC):
    """LLM 客户端抽象基类。"""

    @abstractmethod
    async def chat(
        self, messages: List[Dict], **kwargs
    ) -> Optional[str]:
        """发送消息，返回完整响应。失败返回 None。"""
        ...

    @abstractmethod
    async def chat_stream(
        self, messages: List[Dict], **kwargs
    ) -> AsyncIterator[str]:
        """流式响应生成器。"""
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """检查至少一个后端是否可用。"""
        ...


class StubLLMClient(BaseLLMClient):
    """桩实现 —— 始终返回 None（触发规则兜底）。"""

    async def chat(self, messages: List[Dict], **kwargs) -> Optional[str]:
        return None

    async def chat_stream(self, messages: List[Dict], **kwargs) -> AsyncIterator[str]:
        yield ""
        return

    async def is_available(self) -> bool:
        return False
