"""服务器全局状态管理。

Demo 阶段：使用模块级单例持有 GameSession。
后期升级：替换为会话池（如 Redis / 内存 dict），对外接口不变。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

# 自动加载项目根目录的 .env 文件
try:
    from dotenv import load_dotenv, find_dotenv
    _env_path = find_dotenv(usecwd=True)
    if not _env_path:
        # fallback: 从当前文件向上找到项目根
        _project_root = Path(__file__).resolve().parent.parent.parent.parent
        _env_path = str(_project_root / ".env")
    load_dotenv(_env_path)
except ImportError:
    pass  # python-dotenv 未安装时静默跳过

from src.backend.ai.npc_agent.manager import AgentManager
from src.backend.data.npc_loader import load_npcs
from src.backend.ai.llm_client.interface import BaseLLMClient
from src.backend.ai.llm_client.anthropic_client import AnthropicClient
from src.backend.ai.llm_client.deepseek_client import DeepSeekClient
from src.backend.ai.llm_client.load_balanced import LoadBalancedClient
from src.backend.engine.bond import BondManager
from src.backend.engine.karma import KarmaManager
from src.backend.engine.time import TimeState
from src.backend.engine.resource import ResourceState
from src.backend.engine.game_session import GameSession


# ── LLM 客户端 ───────────────────────────────────

## LLM 后端切换开关（环境变量 LLM_BACKEND）：
##   "llama"（默认）    -> 走本地 llama.cpp（172.21.125.241:8080），响应快、免公网
##   "anthropic"        -> 走 Volcengine Ark Anthropic 兼容端点（公网、有额度限制）
##   "deepseek"         -> 走 DeepSeek API（公网、OpenAI 兼容、需 API Key）
LLM_BACKEND = os.environ.get("LLM_BACKEND", "llama").lower()

## Anthropic 兼容端点兜底配置（env 未设置时使用）。
## 部署时优先使用环境变量 ANTHROPIC_BASE_URL / ANTHROPIC_AUTH_TOKEN / ANTHROPIC_MODEL。
_FALLBACK_ANTHROPIC_BASE_URL = "https://ark.cn-beijing.volces.com/api/coding"
_FALLBACK_ANTHROPIC_MODEL = "ark-code-latest"
## 开发期硬编码 token（用户明确表示不介意泄露；生产环境请改用环境变量）
_FALLBACK_ANTHROPIC_TOKEN = "ark-2fd6a835-b807-4f74-817f-b3d1bd8b4073-9fabe"


def _create_llm_client() -> BaseLLMClient:
    """创建 LLM 客户端。根据 LLM_BACKEND 环境变量切换实现。"""
    if LLM_BACKEND == "deepseek":
        api_key = os.environ.get("DEEPSEEK_API_KEY") or ""
        base_url = os.environ.get("DEEPSEEK_BASE_URL") or "https://api.deepseek.com/v1/chat/completions"
        model = os.environ.get("DEEPSEEK_MODEL") or "deepseek-chat"
        timeout = float(os.environ.get("LLM_TIMEOUT", "60.0"))
        print(f"[state] 使用 DeepSeekClient base_url={base_url} model={model} key={'已配置' if api_key else '缺失'}")
        return DeepSeekClient(
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout=timeout,
            max_retries=2,
        )

    if LLM_BACKEND == "anthropic":
        # Anthropic 兼容端点（火山方舟 Coding）
        base_url = os.environ.get("ANTHROPIC_BASE_URL") or _FALLBACK_ANTHROPIC_BASE_URL
        token = (
            os.environ.get("ANTHROPIC_AUTH_TOKEN")
            or os.environ.get("ANTHROPIC_API_KEY")
            or _FALLBACK_ANTHROPIC_TOKEN
        )
        model = os.environ.get("ANTHROPIC_MODEL") or _FALLBACK_ANTHROPIC_MODEL
        print(f"[state] 使用 AnthropicClient base_url={base_url} model={model} token={'已配置' if token else '缺失'}")
        return AnthropicClient(
            base_url=base_url,
            auth_token=token,
            model=model,
            timeout=60.0,
            max_retries=2,
            concurrency=4,
        )

    # 默认：本地 llama.cpp（OpenAI /v1/chat/completions 兼容）
    endpoint = os.environ.get("LLAMA_ENDPOINT") or "http://172.21.125.241:8080/v1/chat/completions"
    print(f"[state] 使用 LoadBalancedClient (llama.cpp) endpoint={endpoint}")
    return LoadBalancedClient(
        endpoints=[endpoint],
        per_endpoint_concurrency=10,
        timeout=30.0,
        max_retries=2,
        default_extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )


# ── 缘线 ────────────────────────────────────────

def _create_bond_manager(npcs) -> BondManager:
    """创建缘线管理器并注入初始关系。"""
    mgr = BondManager()
    mgr.register_npcs([n.id for n in npcs])

    # 核心初始关系（设计文档 §8.7）
    mgr.set("lin_chaoyin", "chen_yuanzhou", "红", 70, 60)
    mgr.set("chen_yuanzhou", "lin_chaoyin", "红", 75, 55)
    mgr.set("lin_chaoyin", "huiyuan", "灰", 20, 50)
    mgr.set("huiyuan", "lin_chaoyin", "金", 50, 70)
    mgr.set("gu_chenzhou", "chen_haisheng", "金", 60, 85)
    mgr.set("gu_chenzhou", "lin_chaoyin", "黑", 15, 80)
    mgr.set("chen_haisheng", "chen_yuanzhou", "蓝", 35, 20)
    mgr.set("chen_yuanzhou", "chen_haisheng", "蓝", 40, 30)
    mgr.set("chen_haisheng", "su_wan", "蓝", 45, 15)
    mgr.set("lin_yueqin", "lin_chaoyin", "蓝", 70, 40)
    mgr.set("jiang_xueyi", "xu_qing", "金", 45, 60)
    mgr.set("xu_mingchuan", "xu_qing", "蓝", 80, 30)
    mgr.set("xu_mingchuan", "zhou_xingzhi", "蓝", 55, 50)

    return mgr


# ── 业线 ────────────────────────────────────────

def _create_karma_manager() -> KarmaManager:
    """创建业线管理器并加载节点定义。"""
    mgr = KarmaManager()
    mgr.init_from_csv()
    return mgr


# 全局单例
_session: Optional[GameSession] = None


def get_session() -> GameSession:
    """获取当前 GameSession。"""
    global _session
    if _session is None:
        raise RuntimeError("游戏尚未初始化，请先调用 POST /new-game")
    return _session


def get_manager() -> AgentManager:
    """获取当前 AgentManager（便捷方法）。"""
    return get_session().agents


def init_session() -> GameSession:
    """初始化完整游戏会话。"""
    global _session
    npcs = load_npcs()
    llm = _create_llm_client()

    bonds = _create_bond_manager(npcs)
    karma = _create_karma_manager()
    agents = AgentManager(llm=llm, bond_manager=bonds)
    agents.init_from_statics(npcs)

    _session = GameSession(
        time=TimeState(day=1),
        resource=ResourceState(),
        agents=agents,
        bonds=bonds,
        karma=karma,
    )
    return _session


def load_session(session: GameSession) -> None:
    """从存档恢复 GameSession，重新注入 LLM 客户端。"""
    global _session
    llm = _create_llm_client()
    for npc_id in session.agents.npc_ids:
        agent = session.agents.get(npc_id)
        if agent:
            agent.llm = llm
    _session = session


def is_initialized() -> bool:
    """检查是否已初始化。"""
    return _session is not None


def reset() -> None:
    """重置游戏会话。"""
    global _session
    _session = None
