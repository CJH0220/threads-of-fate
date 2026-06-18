"""负载均衡 LLM 客户端 —— 多 llama.cpp 实例轮询。

特性：
- 轮询（Round-Robin）：请求轮流分配到多个端点
- 每端点并发限制（Semaphore）：防止单个 llama.cpp 实例过载
- 故障转移：一个端点失败 → 自动尝试下一个
- 全局降级：所有端点不可用 → 返回 None（触发规则兜底）
- 超时 + 重试 + 指数退避

用法:
    client = LoadBalancedClient(
        endpoints=[
            "http://localhost:8081/v1/chat/completions",
            "http://localhost:8082/v1/chat/completions",
            "http://localhost:8083/v1/chat/completions",
        ],
        per_endpoint_concurrency=2,
        timeout=30.0,
    )
    reply = await client.chat([
        {"role": "system", "content": "你是林潮音..."},
        {"role": "user", "content": "你现在想做什么？"},
    ])
"""

from __future__ import annotations

import asyncio
import itertools
from dataclasses import dataclass
from typing import AsyncIterator, Dict, List, Optional

import httpx

from .interface import BaseLLMClient

# ═══════════════════════════════════════════════════
# 端点状态
# ═══════════════════════════════════════════════════


@dataclass
class EndpointState:
    """单个端点的运行时状态。"""
    url: str
    semaphore: asyncio.Semaphore
    failure_count: int = 0
    total_requests: int = 0
    last_failure_time: float = 0.0


# ═══════════════════════════════════════════════════
# LoadBalancedClient
# ═══════════════════════════════════════════════════


class LoadBalancedClient(BaseLLMClient):
    """轮询 + 每端点并发限制的 LLM 客户端。

    配置示例:
        {
            "endpoints": [
                "http://localhost:8081/v1/chat/completions",
                "http://localhost:8082/v1/chat/completions",
                "http://localhost:8083/v1/chat/completions",
            ],
            "per_endpoint_concurrency": 2,
            "timeout": 30.0,
            "max_retries": 3,
            "retry_backoff_base": 1.5,
        }
    """

    def __init__(
        self,
        endpoints: List[str],
        per_endpoint_concurrency: int = 2,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_backoff_base: float = 1.5,
    ):
        if not endpoints:
            raise ValueError("至少需要一个端点")

        self._endpoints = [
            EndpointState(
                url=url.strip("/"),
                semaphore=asyncio.Semaphore(per_endpoint_concurrency),
            )
            for url in endpoints
        ]
        self._counter: int = 0
        self._timeout = timeout
        self._max_retries = max_retries
        self._retry_backoff_base = retry_backoff_base

        # 共享 httpx 客户端（连接池复用）
        self._http: Optional[httpx.AsyncClient] = None

    # ── 核心方法 ──────────────────────────────────

    async def chat(
        self,
        messages: List[Dict],
        temperature: float = 0.7,
        max_tokens: int = 128,
        **kwargs,
    ) -> Optional[str]:
        """发送消息 → 轮询端点 → 故障转移 → 返回响应。

        所有端点都失败时返回 None（调用方走规则兜底）。
        """
        await self._ensure_client()

        # 尝试次数：最多尝试所有端点，但不超过 max_retries
        attempts = min(len(self._endpoints), self._max_retries)
        tried: set[int] = set()

        for attempt in range(attempts):
            idx = self._next_index(tried)
            tried.add(idx)
            endpoint = self._endpoints[idx]

            # 获取端点信号量（排队等待）
            try:
                async with asyncio.timeout(self._timeout):
                    async with endpoint.semaphore:
                        result = await self._do_request(
                            endpoint, idx, messages, temperature, max_tokens,
                            attempt, **kwargs,
                        )
                        if result is not None:
                            return result
            except asyncio.TimeoutError:
                # 排队超时 → 跳过这个端点
                endpoint.failure_count += 1
                continue

        # 所有端点失败 → 降级
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
        """至少一个端点可达。"""
        await self._ensure_client()
        for endpoint in self._endpoints:
            try:
                resp = await self._http.get(
                    f"{endpoint.url}/../models",
                    timeout=5.0,
                )
                if resp.status_code == 200:
                    return True
            except Exception:
                continue
        return False

    # ── 内部方法 ──────────────────────────────────

    async def _ensure_client(self) -> None:
        """懒初始化 httpx 客户端。"""
        if self._http is None:
            self._http = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout),
                limits=httpx.Limits(
                    max_keepalive_connections=len(self._endpoints) * 2,
                    max_connections=len(self._endpoints) * 4,
                ),
            )

    def _next_index(self, exclude: set) -> int:
        """轮询下一个端点索引（跳过 exclude 中的）。"""
        for _ in range(len(self._endpoints)):
            idx = self._counter % len(self._endpoints)
            self._counter += 1
            if idx not in exclude:
                return idx
        # 全部被排除 → 随机选
        return self._counter % len(self._endpoints)

    async def _do_request(
        self,
        endpoint: EndpointState,
        idx: int,
        messages: List[Dict],
        temperature: float,
        max_tokens: int,
        attempt: int,
        **kwargs,
    ) -> Optional[str]:
        """执行单次 HTTP 请求（含重试）。"""
        payload = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
            **kwargs,
        }

        for retry in range(self._max_retries):
            try:
                resp = await self._http.post(
                    endpoint.url,
                    json=payload,
                    timeout=self._timeout,
                )

                if resp.status_code == 200:
                    data = resp.json()
                    content = (
                        data.get("choices", [{}])[0]
                        .get("message", {})
                        .get("content", "")
                    )
                    endpoint.total_requests += 1
                    return content if content else None

                # 429 / 503 → 可重试
                if resp.status_code in (429, 503):
                    wait = self._retry_backoff_base ** (retry + 1)
                    await asyncio.sleep(wait)
                    continue

                # 其他错误 → 记失败
                endpoint.failure_count += 1
                return None

            except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError):
                if retry < self._max_retries - 1:
                    wait = self._retry_backoff_base ** (retry + 1)
                    await asyncio.sleep(wait)
                    continue
                endpoint.failure_count += 1
                return None

            except Exception:
                endpoint.failure_count += 1
                return None

        endpoint.failure_count += 1
        return None

    # ── 资源释放 ──────────────────────────────────

    async def close(self) -> None:
        """关闭 HTTP 客户端。"""
        if self._http:
            await self._http.aclose()
            self._http = None

    # ── 统计（调试用） ────────────────────────────

    def stats(self) -> dict:
        """返回各端点的统计信息。"""
        return {
            "endpoints": [
                {
                    "url": ep.url,
                    "total_requests": ep.total_requests,
                    "failure_count": ep.failure_count,
                    "semaphore_available": ep.semaphore._value,
                }
                for ep in self._endpoints
            ],
            "total_counter": self._counter,
        }
