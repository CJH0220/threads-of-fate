"""对白设计师 Agent — 润色拼接后的 SceneFilled，输出最终对白。

单次 LLM 调用：接收骨架 + NPC 填写的台词 → 输出润色后完整定稿。
只做文本审美，不改结算数据、不增删角色、不改事件走向。
"""

from src.backend.ai.dialogue_designer.designer import polish_dialogue

__all__ = ["polish_dialogue"]
