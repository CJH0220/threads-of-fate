"""Karma manager — runtime progress tracker for NPC karma lines.

Stores karma lines with mutable progress. Parses event delta strings
like "chaoyin_witch_line:+10" and accumulates progress.

Usage:
    mgr = KarmaManager()
    mgr.init_from_csv()  # load node definitions
    lines = mgr.lines_for_npc("lin_chaoyin")
    mgr.apply_delta("chaoyin_witch_line:+10")
    if mgr.get_line("chaoyin_witch_line").is_complete:
        print("Karma line complete!")
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.backend.engine.karma.karma_types import KarmaLine, KarmaNode
from src.backend.engine.karma.karma_loader import load_karma_nodes


@dataclass
class KarmaManager:
    """Runtime karma progress tracker.

    Holds all karma lines for all NPCs. Progress is mutable and serializable.
    Node definitions are loaded from CSV and are immutable.
    """
    _lines: Dict[str, KarmaLine] = field(default_factory=dict)

    def init_from_csv(self, path: Optional[str] = None) -> None:
        """Load node definitions from CSV and create KarmaLine instances."""
        nodes_by_line = load_karma_nodes(path)
        for line_id, nodes in nodes_by_line.items():
            if nodes:
                npc_id = nodes[0].id.split("_")[1]  # Extract from "karma_linchaoyin_01"
                # Better: get owner from first node's CSV data
                # For now, derive npc_id from the first related event or node id pattern
                npc_id = self._derive_npc_id(line_id, nodes)
                self._lines[line_id] = KarmaLine(
                    id=line_id,
                    npc_id=npc_id,
                    progress=0.0,
                    nodes=nodes,
                )

    @staticmethod
    def _derive_npc_id(line_id: str, nodes: List[KarmaNode]) -> str:
        """Derive NPC ID from the karma line ID or node data."""
        # Line IDs like "chaoyin_witch_line", "yuanzhou_leave_line"
        # Map to NPC IDs via known patterns
        prefix_map = {
            "chaoyin": "lin_chaoyin",
            "yuanzhou": "chen_yuanzhou",
            "chenhai": "chen_haisheng",
            "guchenzhou": "gu_chenzhou",
            "huiyuan": "huiyuan",
        }
        for prefix, npc_id in prefix_map.items():
            if line_id.startswith(prefix):
                return npc_id
        return line_id.split("_")[0]  # fallback

    # ── Queries ──

    def get_line(self, line_id: str) -> Optional[KarmaLine]:
        """Get a karma line by ID."""
        return self._lines.get(line_id)

    def lines_for_npc(self, npc_id: str) -> List[KarmaLine]:
        """Get all karma lines for a given NPC."""
        return [line for line in self._lines.values() if line.npc_id == npc_id]

    def all_lines(self) -> List[KarmaLine]:
        """Get all karma lines."""
        return list(self._lines.values())

    def get_progress(self, line_id: str) -> float:
        """Get progress for a karma line (0.0-100.0). Returns 0.0 if not found."""
        line = self._lines.get(line_id)
        return line.progress if line else 0.0

    # ── Delta application ──

    def apply_delta(self, delta_string: str) -> List[KarmaLine]:
        """Parse and apply a karma delta string from an event outcome.

        Format: "chaoyin_witch_line:+10;yuanzhou_leave_line:+4"
        Returns list of affected lines.
        """
        results: List[KarmaLine] = []
        if not delta_string or delta_string.strip().lower() in ("none", ""):
            return results

        for part in delta_string.split(";"):
            part = part.strip()
            if not part or ":" not in part:
                continue

            # "chaoyin_witch_line:+10" → "chaoyin_witch_line", +10
            colon_idx = part.rfind(":")
            line_id = part[:colon_idx].strip()
            delta_str = part[colon_idx + 1:].strip()

            try:
                delta = float(delta_str)
            except ValueError:
                continue

            line = self._lines.get(line_id)
            if line is None:
                continue  # Unknown line, skip

            line.progress = max(0.0, min(100.0, line.progress + delta))
            results.append(line)

        return results

    # ── Serialization ──

    def to_dict(self) -> Dict[str, Any]:
        """Serialize progress only (node definitions are CSV-derived, not stored)."""
        return {
            "lines": {
                line_id: line.progress
                for line_id, line in self._lines.items()
            }
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KarmaManager":
        """Deserialize progress. Node definitions must be loaded separately via init_from_csv()."""
        mgr = cls()
        mgr.init_from_csv()
        lines_data = data.get("lines", {})
        for line_id, progress in lines_data.items():
            if line_id in mgr._lines:
                mgr._lines[line_id].progress = float(progress)
        return mgr
