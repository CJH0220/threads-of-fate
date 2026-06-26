"""Bond system — runtime NPC relationship manager.

Manages directed bonds between NPCs:
    - type: 红(love) / 金(interest) / 蓝(friendship) / 灰(stranger) / 黑(hatred)
    - strength: 0-100
    - glow: 0-100 (activity level)

Integrates with event system: parses "bond_chaoyin_yuanzhou:+3" delta strings
from event outcomes and applies them.

Public API:
    BondManager: mutable bond ledger
    Bond: single directed relationship
"""

from src.backend.engine.bond.bond_manager import BondManager, Bond

__all__ = ["BondManager", "Bond"]
