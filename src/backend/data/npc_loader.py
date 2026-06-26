"""NPC CSV loader — reads NPC基础表.csv and produces NpcStatic + initial dynamic data.

CSV columns (v2, 19 columns):
    NpcId → id
    DisplayName → name
    AgentTier → tier
    Age → age
    Role → occupation
    Description → background
    CoreWish → core_wish
    Mind / Faith / Physique / Charm → attributes
    Kindness / Aggression / Sensibility / Rationality / Curiosity → personality
    InitialLocations → initial location (for NpcDynamic, returned separately)
"""

import csv
import os
from typing import Dict, List, Optional, Tuple

from src.backend.ai.npc_agent.static import build_static
from src.backend.models.npc import NpcStatic


# ── Default CSV path ──

_DEFAULT_CSV = os.path.join(os.path.dirname(__file__), "NPC基础表.csv")


# ── Column mapping ──

def _row_to_static_dict(row: Dict[str, str]) -> dict:
    """Convert a CSV row dict to the format expected by build_static()."""
    return {
        "id": row["NpcId"].strip(),
        "name": row["DisplayName"].strip(),
        "age": int(row["Age"].strip()),
        "occupation": row["Role"].strip(),
        "tier": row["AgentTier"].strip(),
        "background": row.get("Description", "").strip(),
        "core_wish": row.get("CoreWish", "").strip(),
        "attributes": {
            "mind": int(row.get("Mind", 5)),
            "faith": int(row.get("Faith", 5)),
            "physique": int(row.get("Physique", 5)),
            "charm": int(row.get("Charm", 5)),
        },
        "personality": {
            "kindness": float(row.get("Kindness", 0.5)),
            "aggression": float(row.get("Aggression", 0.3)),
            "sensibility": float(row.get("Sensibility", 0.5)),
            "rationality": float(row.get("Rationality", 0.5)),
            "curiosity": float(row.get("Curiosity", 0.5)),
        },
    }


def _row_to_initial_location(row: Dict[str, str]) -> Optional[str]:
    """Extract the first initial location from a CSV row.

    InitialLocations is semicolon-delimited (e.g. "school;temple;coffee_shop;beach").
    We take the first one as the starting location.
    """
    raw = row.get("InitialLocations", "").strip()
    if raw:
        locations = [loc.strip() for loc in raw.split(";") if loc.strip()]
        if locations:
            return locations[0]
    return None


# ── Public API ──

def load_npcs(csv_path: Optional[str] = None) -> List[NpcStatic]:
    """Load NPC static data from CSV.

    Args:
        csv_path: path to NPC基础表.csv. Defaults to the bundled CSV.

    Returns:
        list of NpcStatic, one per NPC row.

    Raises:
        FileNotFoundError: CSV not found at path.
        ValueError: a row has invalid data (bad int/float).
    """
    path = csv_path or _DEFAULT_CSV

    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        npcs = []
        for row in reader:
            # Skip empty rows
            if not row.get("NpcId", "").strip():
                continue
            data = _row_to_static_dict(row)
            npcs.append(build_static(data))
        return npcs


def load_npc_initial_dynamic(csv_path: Optional[str] = None) -> Dict[str, str]:
    """Load initial location for each NPC from CSV.

    Args:
        csv_path: path to NPC基础表.csv. Defaults to the bundled CSV.

    Returns:
        {npc_id: initial_location_string}, e.g. {"lin_chaoyin": "school"}
    """
    path = csv_path or _DEFAULT_CSV

    result: Dict[str, str] = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            npc_id = row.get("NpcId", "").strip()
            if not npc_id:
                continue
            loc = _row_to_initial_location(row)
            if loc:
                result[npc_id] = loc
    return result
