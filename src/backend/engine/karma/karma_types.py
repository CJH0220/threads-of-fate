"""Karma system data types."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class KarmaNode:
    """A single node on a karma line.

    Loaded from CSV (业线节点表.csv). Immutable at runtime.
    """
    id: str                        # "karma_chaoyin_01"
    node_order: int                # 1-4
    name: str                      # "噩梦初现"
    week_range: str                # "W1-W3"
    required_conditions: str       # "bond_chaoyin_huiyuan>=25" | "none"
    success_bias: str              # outcome bias name
    failure_bias: str              # outcome bias name
    visible_to_player: str         # "Yes" | "Partial" | "Hidden"
    related_event_ids: List[str]   # ["w3_chaoyin_nightmare"]
    description: str               # Chinese description

    @property
    def threshold(self) -> float:
        """Progress percentage at which this node becomes active.

        Nodes are evenly spaced: node 1 at 0%, node N at 100%.
        """
        return 0.0  # set by parent line based on total nodes


@dataclass
class KarmaLine:
    """A complete karma line for one NPC.

    Progress is mutable — tracked by KarmaManager.
    Nodes are loaded from CSV and immutable.
    """
    id: str                        # "chaoyin_witch_line"
    npc_id: str                    # "lin_chaoyin"
    progress: float = 0.0          # 0.0-100.0
    nodes: List[KarmaNode] = field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        return self.progress >= 100.0

    @property
    def current_node(self) -> Optional[KarmaNode]:
        """The active node based on current progress."""
        if not self.nodes:
            return None
        # Nodes are triggered when progress reaches their threshold
        active = self.nodes[0]
        for node in sorted(self.nodes, key=lambda n: n.node_order):
            threshold = ((node.node_order - 1) / len(self.nodes)) * 100.0
            if self.progress >= threshold:
                active = node
        return active

    @property
    def next_node(self) -> Optional[KarmaNode]:
        """The next node to be reached, or None if complete."""
        if not self.nodes:
            return None
        current = self.current_node
        if current is None:
            return self.nodes[0]
        for node in sorted(self.nodes, key=lambda n: n.node_order):
            if node.node_order > current.node_order:
                return node
        return None
