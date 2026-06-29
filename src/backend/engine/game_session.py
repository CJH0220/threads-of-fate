"""GameSession — container for all engine modules.

A single GameSession holds references to the five stateful engine modules.
It's the unit of save/load: to_dict() serializes everything, from_dict() rebuilds.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from src.backend.engine.time import TimeState
from src.backend.engine.resource import ResourceState
from src.backend.engine.bond import BondManager
from src.backend.engine.karma import KarmaManager
from src.backend.ai.npc_agent.manager import AgentManager


@dataclass
class GameSession:
    """Container for all runtime engine state.

    Created on /new-game, used for save/load, holds everything needed
    to reconstruct a game at any point.
    """
    time: TimeState
    resource: ResourceState
    agents: AgentManager
    bonds: BondManager
    karma: KarmaManager

    def to_dict(self) -> Dict[str, Any]:
        """Serialize all modules to a single dict."""
        return {
            "time": self.time.to_dict(),
            "resource": self.resource.to_dict(),
            "agents": self.agents.to_dict(),
            "bonds": self.bonds.to_dict(),
            "karma": self.karma.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> GameSession:
        """Deserialize all modules from a dict.

        AgentManager needs NPC static data from CSV to reconstruct agents.
        BondManager needs NPC id list to rebuild alias registry.
        Name maps are rebuilt from the loaded agents.
        """
        from src.backend.data.npc_loader import load_npcs
        npcs = load_npcs()
        static_map = {n.id: n for n in npcs}
        agents = AgentManager.from_dict(data["agents"], static_map)

        bonds = BondManager.from_dict(data.get("bonds", {}))
        bonds.register_npcs([n.id for n in npcs])

        karma = KarmaManager.from_dict(data.get("karma", {}))

        # Rebuild name_map for each agent (lost during serialization)
        name_map = {aid: agent.static.name for aid, agent in agents._agents.items()}
        for agent in agents._agents.values():
            agent._name_map = name_map
            agent._bond_manager = bonds

        return cls(
            time=TimeState.from_dict(data["time"]),
            resource=ResourceState.from_dict(data["resource"]),
            agents=agents,
            bonds=bonds,
            karma=karma,
        )
