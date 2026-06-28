"""Data loading module — reads CSV/JSON config files into game objects.

Design principle (D8): CSV is the blueprint (loaded once, read-only).
GameSession is the instance (runtime, mutable).

Current scope:
    - NPC static data from CSV → list[NpcStatic]
    - Initial dynamic data (location) from CSV → dict

Future scope:
    - Bond initial relations (CSV)
    - Karma node definitions (JSON)
    - Event config (CSV)
"""

from src.backend.data.npc_loader import load_npcs

__all__ = ["load_npcs"]
