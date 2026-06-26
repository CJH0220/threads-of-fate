"""Karma system — NPC life path progression tracker.

Manages karma lines (业线): each NPC has 1 main line + 2-3 side lines,
each with 5-10 nodes and 0-100% progress.

Integrates with event system: parses "chaoyin_witch_line:+10" delta strings
from event outcomes and accumulates progress.

Public API:
    KarmaManager: progress tracker + delta parser + node queries
    KarmaLine: a single karma line with nodes and progress
    KarmaNode: a single node definition
"""

from src.backend.engine.karma.karma_manager import KarmaManager
from src.backend.engine.karma.karma_types import KarmaLine, KarmaNode
from src.backend.engine.karma.karma_loader import load_karma_nodes

__all__ = ["KarmaManager", "KarmaLine", "KarmaNode", "load_karma_nodes"]
