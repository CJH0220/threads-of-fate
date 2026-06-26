"""Karma node CSV loader — reads 业线节点表.csv into KarmaNode definitions."""

import csv
import os
from typing import Dict, List, Optional

from src.backend.engine.karma.karma_types import KarmaNode


def _design_data_dir() -> str:
    backend = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    return os.path.join(backend, os.pardir, "design", "data")


_KARMA_CSV = os.path.join(_design_data_dir(), "业线节点表.csv")


def _parse_related_events(raw: str) -> List[str]:
    """Parse "w3_chaoyin_nightmare;w3_witch_candidate" → list."""
    if not raw or raw.strip().lower() in ("none", ""):
        return []
    return [e.strip() for e in raw.split(";") if e.strip()]


def load_karma_nodes(path: Optional[str] = None) -> Dict[str, List[KarmaNode]]:
    """Load karma nodes from CSV, grouped by KarmaLineId.

    Args:
        path: path to 业线节点表.csv

    Returns:
        {line_id: [KarmaNode, ...]} sorted by NodeOrder
    """
    path = path or _KARMA_CSV
    nodes_by_line: Dict[str, List[KarmaNode]] = {}

    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            node_id = row.get("KarmaNodeId", "").strip()
            line_id = row.get("KarmaLineId", "").strip()
            if not node_id or not line_id:
                continue

            node = KarmaNode(
                id=node_id,
                node_order=int(row.get("NodeOrder", 1)),
                name=row.get("NodeName", "").strip(),
                week_range=row.get("WeekRange", "").strip(),
                required_conditions=row.get("RequiredConditions", "none").strip(),
                success_bias=row.get("SuccessBias", "").strip(),
                failure_bias=row.get("FailureBias", "").strip(),
                visible_to_player=row.get("VisibleToPlayer", "Yes").strip(),
                related_event_ids=_parse_related_events(row.get("RelatedEventIds", "")),
                description=row.get("Description", "").strip(),
            )

            if line_id not in nodes_by_line:
                nodes_by_line[line_id] = []
            nodes_by_line[line_id].append(node)

    # Sort each line's nodes by order
    for line_id in nodes_by_line:
        nodes_by_line[line_id].sort(key=lambda n: n.node_order)

    return nodes_by_line
