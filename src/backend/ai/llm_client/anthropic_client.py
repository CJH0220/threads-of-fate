"""Anthropic Messages API 客户端（火山方舟 Coding 端点兼容）。

用途：将本地 llama.cpp 后端替换为 Anthropic 兼容的云端 LLM，
      通过 Volcengine Ark 的 /api/coding 走 Anthropic Messages 协议。

配置来源（按优先级）：
    1. 构造参数
    2. 环境变量 ANTHROPIC_BASE_URL / ANTHROPIC_AUTH_TOKEN / ANTHROPIC_MODEL
    3. 内置默认值（本项目开发期硬编码）

协议差异（相对 OpenAI /v1/chat/completions）：
    - 端点：{base_url}/v1/messages
    - system 消息从 messages 列表中抽出，放到顶级 system 字段
    - Content 为 [{"type": "text", "text": ...}] 列表
    - Headers: anthropic-version + Bearer/x-api-key
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import AsyncIterator, Dict, List, Optional

import httpx

from .interface import BaseLLMClient


# ═══════════════════════════════════════════════════
# 默认配置（可被 env / 构造参数覆盖）
# ═══════════════════════════════════════════════════

DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/coding"
DEFAULT_MODEL = "ark-code-latest"
DEFAULT_ANTHROPIC_VERSION = "2023-06-01"


class AnthropicClient(BaseLLMClient):
    """Anthropic Messages API 兼容客户端。

    使用示例:
        client = AnthropicClient()  # 从环境变量读取
        reply = await client.chat([
            {"role": "system", "content": "你是林潮音..."},
            {"role": "user", "content": "你现在想做什么？"},
        ])
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        auth_token: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 60.0,
        max_retries: int = 2,
        retry_backoff_base: float = 1.5,
        concurrency: int = 4,
    ):
        self._base_url = (
            base_url
            or os.environ.get("ANTHROPIC_BASE_URL")
            or DEFAULT_BASE_URL
        ).rstrip("/")
        self._auth_token = (
            auth_token
            or os.environ.get("ANTHROPIC_AUTH_TOKEN")
            or os.environ.get("ANTHROPIC_API_KEY")
            or ""
        )
        self._model = (
            model
            or os.environ.get("ANTHROPIC_MODEL")
            or DEFAULT_MODEL
        )
        self._timeout = timeout
        self._max_retries = max_retries
        self._retry_backoff_base = retry_backoff_base
        self._semaphore = asyncio.Semaphore(concurrency)

        # 共享 httpx 客户端（连接池复用）
        self._http: Optional[httpx.AsyncClient] = None

        # 统计
        self._total_requests = 0
        self._failure_count = 0

        if not self._auth_token:
            # 不抛异常，保留降级空间：所有请求会返回 None 触发规则兜底
            print("[AnthropicClient] 警告：未配置 ANTHROPIC_AUTH_TOKEN，LLM 调用将全部返回 None")

    # ── 核心方法 ──────────────────────────────────

    async def chat(
        self,
        messages: List[Dict],
        temperature: float = 0.7,
        max_tokens: int = 256,
        extra_body: Optional[Dict] = None,
        **kwargs,
    ) -> Optional[str]:
        """发送消息，返回完整响应。失败返回 None（触发规则兜底）。"""
        if not self._auth_token:
            return None

        await self._ensure_client()

        # 将 OpenAI 风格的 messages 转换为 Anthropic 风格
        system_prompt, anthropic_messages = self._split_system(messages)

        payload: Dict = {
            "model": self._model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": anthropic_messages,
        }
        if system_prompt:
            payload["system"] = system_prompt
        # kwargs / extra_body 合并（覆盖默认值）
        if extra_body:
            payload.update(extra_body)
        if kwargs:
            payload.update(kwargs)

        async with self._semaphore:
            for retry in range(self._max_retries):
                try:
                    resp = await self._http.post(
                        f"{self._base_url}/v1/messages",
                        json=payload,
                        headers=self._headers(),
                        timeout=self._timeout,
                    )
                except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError) as e:
                    print(f"[AnthropicClient] 网络异常 (retry {retry+1}/{self._max_retries}): {e}")
                    if retry < self._max_retries - 1:
                        await asyncio.sleep(self._retry_backoff_base ** (retry + 1))
                        continue
                    self._failure_count += 1
                    return None
                except Exception as e:
                    print(f"[AnthropicClient] 未预期错误: {type(e).__name__}: {e}")
                    self._failure_count += 1
                    return None

                if resp.status_code == 200:
                    self._total_requests += 1
                    return self._extract_text(resp.json())

                # 429 / 5xx → 重试
                if resp.status_code in (429, 500, 502, 503, 504):
                    print(f"[AnthropicClient] HTTP {resp.status_code}，退避重试")
                    if retry < self._max_retries - 1:
                        await asyncio.sleep(self._retry_backoff_base ** (retry + 1))
                        continue
                    self._failure_count += 1
                    return None

                # 其他 4xx → 直接失败，打印诊断
                print(f"[AnthropicClient] HTTP {resp.status_code}: {resp.text[:300]}")
                self._failure_count += 1
                return None

        self._failure_count += 1
        return None

    async def chat_stream(
        self,
        messages: List[Dict],
        temperature: float = 0.7,
        max_tokens: int = 256,
        **kwargs,
    ) -> AsyncIterator[str]:
        """流式响应。当前简化为非流式 + yield 全文（游戏内不依赖流式）。"""
        result = await self.chat(
            messages, temperature=temperature, max_tokens=max_tokens, **kwargs
        )
        yield result or ""

    async def is_available(self) -> bool:
        """有 token 且能够 ping 通根路径视为可用。"""
        if not self._auth_token:
            return False
        await self._ensure_client()
        try:
            # 用一个极小的探针请求验证。Anthropic 没有独立 /health，
            # 用最小 messages 请求，能拿到 200 就是可用。
            resp = await self._http.post(
                f"{self._base_url}/v1/messages",
                json={
                    "model": self._model,
                    "max_tokens": 1,
                    "messages": [{"role": "user", "content": "ping"}],
                },
                headers=self._headers(),
                timeout=5.0,
            )
            return resp.status_code == 200
        except Exception:
            return False

    # ── 内部方法 ──────────────────────────────────

    async def _ensure_client(self) -> None:
        """懒初始化 httpx 客户端。"""
        if self._http is None:
            self._http = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout),
                limits=httpx.Limits(
                    max_keepalive_connections=8,
                    max_connections=16,
                ),
            )

    def _headers(self) -> Dict[str, str]:
        """构造 Anthropic 请求头。

        Volcengine Ark 兼容 Anthropic 协议时接受 Authorization: Bearer 或 x-api-key。
        两个都带上以兼容不同网关。
        """
        return {
            "content-type": "application/json",
            "anthropic-version": DEFAULT_ANTHROPIC_VERSION,
            "authorization": f"Bearer {self._auth_token}",
            "x-api-key": self._auth_token,
        }

    @staticmethod
    def _split_system(messages: List[Dict]) -> tuple[str, List[Dict]]:
        """将 OpenAI 风格 messages 拆成 (system_prompt, anthropic_messages)。

        - 合并连续 system 消息为单一 system_prompt（Anthropic 只接受顶级 system 字段）
        - 其余 user/assistant 消息按顺序保留
        - Anthropic 要求首条为 user，若首条是 assistant，插入占位 user
        """
        system_parts: List[str] = []
        rest: List[Dict] = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "system":
                if isinstance(content, str) and content:
                    system_parts.append(content)
                continue
            # 只允许 user / assistant
            if role not in ("user", "assistant"):
                role = "user"
            rest.append({"role": role, "content": content if isinstance(content, str) else str(content)})

        if rest and rest[0]["role"] == "assistant":
            rest.insert(0, {"role": "user", "content": "(继续)"})

        # 若完全没有消息，补一个占位问句，避免 API 400
        if not rest:
            rest = [{"role": "user", "content": "继续。"}]

        return ("\n\n".join(system_parts), rest)

    @staticmethod
    def _extract_text(data: Dict) -> Optional[str]:
        """从 Anthropic response 中提取文本内容。

        response 格式:
            {"content": [{"type": "text", "text": "..."}, ...], ...}
        """
        content = data.get("content", [])
        if not isinstance(content, list):
            return None
        parts: List[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text", "")
                if text:
                    parts.append(text)
        result = "".join(parts).strip()
        return result if result else None

    # ── 资源释放 ──────────────────────────────────

    async def close(self) -> None:
        """关闭 HTTP 客户端。"""
        if self._http:
            await self._http.aclose()
            self._http = None

    # ── 统计（调试用） ────────────────────────────

    def stats(self) -> dict:
        """返回运行时统计信息。"""
        return {
            "base_url": self._base_url,
            "model": self._model,
            "total_requests": self._total_requests,
            "failure_count": self._failure_count,
            "has_token": bool(self._auth_token),
        }
