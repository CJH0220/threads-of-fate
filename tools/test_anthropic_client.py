"""快速验证 AnthropicClient 能不能调通 Volcengine Ark。

用法：
    python tools/test_anthropic_client.py
"""

import asyncio
import sys

sys.path.insert(0, ".")

from src.backend.ai.llm_client.anthropic_client import AnthropicClient


async def main() -> int:
    print("=" * 60)
    print("AnthropicClient 联通性测试")
    print("=" * 60)

    client = AnthropicClient()
    print(f"配置: {client.stats()}")
    print()

    print("→ 发送测试消息...")
    reply = await client.chat(
        messages=[
            {"role": "system", "content": "你是一位居住在归潮镇沙滩边的少女，语气温柔。"},
            {"role": "user", "content": "土地公问：你现在最想做什么？请用一句话回答。"},
        ],
        max_tokens=100,
        temperature=0.7,
    )
    await client.close()

    if reply is None:
        print("❌ 调用失败（返回 None）")
        print(f"统计: {client.stats()}")
        return 1

    print(f"✅ 回复: {reply}")
    print(f"统计: {client.stats()}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
