"""DeepSeek LLM 客户端 —— OpenAI /v1/chat/completions 兼容 + Bearer Token 鉴权。

使用 requests（同步）+ loop.run_in_executor（Python 3.8 兼容）回避 httpx 代理问题。
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from typing import AsyncIterator, Dict, List, Optional

import requests

from .interface import BaseLLMClient


# ═══════════════════════════════════════════════════
# DeepSeekClient
# ═══════════════════════════════════════════════════

# 线程池（所有 DeepSeekClient 实例共享）
_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=8)


class DeepSeekClient(BaseLLMClient):
    """DeepSeek API 客户端（OpenAI /v1/chat/completions 兼容）。

    配置示例:
        {
            "api_key": "sk-...",
            "base_url": "https://api.deepseek.com/v1/chat/completions",
            "model": "deepseek-chat",
            "timeout": 60.0,
            "max_retries": 2,
        }
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com/v1/chat/completions",
        model: str = "deepseek-chat",
        timeout: float = 60.0,
        max_retries: int = 2,
    ):
        if not api_key:
            raise ValueError("DeepSeek API key 不能为空")

        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._max_retries = max_retries

    # ── 核心方法 ──────────────────────────────────

    async def chat(
        self,
        messages: List[Dict],
        temperature: float = 0.7,
        max_tokens: int = 256,
        **kwargs,
    ) -> Optional[str]:
        """发送消息，返回完整响应。失败返回 None。"""

        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        payload.update(kwargs)

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        loop = asyncio.get_running_loop()

        for attempt in range(self._max_retries):
            try:
                resp = await loop.run_in_executor(
                    _EXECUTOR,
                    lambda: requests.post(
                        self._base_url,
                        json=payload,
                        headers=headers,
                        timeout=self._timeout,
                        proxies={"http": None, "https": None},  # 绕过系统代理
                    ),
                )

                if resp.status_code == 200:
                    data = resp.json()
                    content = (
                        data.get("choices", [{}])[0]
                        .get("message", {})
                        .get("content", "")
                    )
                    return content if content else None

                # 429 / 503 → 可重试
                if resp.status_code in (429, 503):
                    wait = 1.5 ** (attempt + 1)
                    await asyncio.sleep(wait)
                    continue

                return None

            except requests.Timeout:
                if attempt < self._max_retries - 1:
                    wait = 1.5 ** (attempt + 1)
                    await asyncio.sleep(wait)
                    continue
                return None

            except requests.ConnectionError:
                if attempt < self._max_retries - 1:
                    wait = 1.5 ** (attempt + 1)
                    await asyncio.sleep(wait)
                    continue
                return None

            except Exception:
                return None

        return None

    async def chat_stream(
        self,
        messages: List[Dict],
        temperature: float = 0.7,
        max_tokens: int = 256,
        **kwargs,
    ) -> AsyncIterator[str]:
        """流式响应。当前简化为非流式 + yield 全文。"""
        result = await self.chat(
            messages, temperature=temperature, max_tokens=max_tokens, **kwargs
        )
        if result:
            yield result
        else:
            yield ""

    async def is_available(self) -> bool:
        """通过列出模型来检查 API 是否可用。"""
        loop = asyncio.get_running_loop()
        try:
            resp = await loop.run_in_executor(
                _EXECUTOR,
                lambda: requests.get(
                    self._base_url.rstrip("/chat/completions") + "/models",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    timeout=10.0,
                    proxies={"http": None, "https": None},
                ),
            )
            return resp.status_code == 200
        except Exception:
            return False

    # ── 统计 ──────────────────────────────────────

    def stats(self) -> dict:
        return {
            "backend": "deepseek",
            "base_url": self._base_url,
            "model": self._model,
        }
