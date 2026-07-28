"""Screenwriter Agent — LLM-driven narrative orchestration.

Replaces old CSV event matching with intelligent,
outline-guided story beat triggering + NPC intervention.
"""

from src.backend.ai.screenwriter.screenwriter import screenwriter_think, ScreenwriterResult

__all__ = ["screenwriter_think", "ScreenwriterResult"]
