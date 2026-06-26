"""Bond manager — runtime relationship ledger for NPC-NPC bonds.

Each bond is a directed edge: A→B can differ from B→A.
Storage: flat dict keyed by (from_id, to_id).

Delta parsing: event outcomes produce strings like
    "bond_chaoyin_yuanzhou:+3;bond_chenhai_suwan:-4"
which are parsed into (from_id, to_id, delta) tuples and applied.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


# ── Edge type constants ──

VALID_TYPES: Set[str] = {"红", "金", "蓝", "灰", "黑"}


# ── Bond dataclass ──

@dataclass
class Bond:
    """A single directed relationship from one NPC to another."""
    from_id: str
    to_id: str
    type: str          # 红/金/蓝/灰/黑
    strength: int      # 0-100
    glow: int          # 0-100

    def __post_init__(self):
        if self.type not in VALID_TYPES:
            raise ValueError(f"Invalid bond type: {self.type}, expected one of {VALID_TYPES}")
        if not (0 <= self.strength <= 100):
            raise ValueError(f"Invalid strength: {self.strength}, expected 0-100")
        if not (0 <= self.glow <= 100):
            raise ValueError(f"Invalid glow: {self.glow}, expected 0-100")


# ── BondManager ──

@dataclass
class BondManager:
    """Runtime ledger for all NPC-NPC bonds.

    Usage:
        mgr = BondManager(npc_ids=["lin_chaoyin", "chen_yuanzhou", ...])
        mgr.set("lin_chaoyin", "chen_yuanzhou", "红", strength=70, glow=50)
        bond = mgr.get("lin_chaoyin", "chen_yuanzhou")  # → Bond or None
        mgr.apply_delta("bond_chaoyin_yuanzhou:+3")     # strength += 3
    """
    _bonds: Dict[Tuple[str, str], Bond] = field(default_factory=dict)
    _alias_registry: Dict[str, str] = field(default_factory=dict)
    _bond_key_map: Dict[str, Tuple[str, str]] = field(default_factory=dict)

    def register_npcs(self, npc_ids: List[str]) -> None:
        """Build alias registry and bond key map from the full NPC list.

        Call once after initialization, before applying deltas.
        """
        # Build alias registry: {short_name: full_id}
        aliases: Dict[str, str] = {}
        for nid in npc_ids:
            # Full id → itself
            aliases[nid] = nid
            # De-underscored version
            short = nid.replace("_", "")
            aliases[short] = nid
            # Last part of id
            parts = nid.split("_")
            if len(parts) >= 2:
                aliases[parts[-1]] = nid

        # Special overrides for known CSV short names
        if "chen_haisheng" in npc_ids:
            aliases["chenhai"] = "chen_haisheng"
        if "zhao_shouzheng" in npc_ids:
            aliases["zhao"] = "zhao_shouzheng"
        if "xu_mingchuan" in npc_ids:
            aliases["mingchuan"] = "xu_mingchuan"

        self._alias_registry = aliases

        # Build bond key map for all NPC pairs
        for s1, id1 in aliases.items():
            for s2, id2 in aliases.items():
                if id1 == id2:
                    continue
                key = f"{s1}_{s2}"
                self._bond_key_map[key] = (id1, id2)

    # ── CRUD ──

    def get(self, from_id: str, to_id: str) -> Optional[Bond]:
        """Get the bond from from_id → to_id. Returns None if not set."""
        return self._bonds.get((from_id, to_id))

    def set(self, from_id: str, to_id: str, type: str = "灰",
            strength: int = 50, glow: int = 0) -> Bond:
        """Create or overwrite a bond."""
        bond = Bond(from_id=from_id, to_id=to_id,
                    type=type, strength=strength, glow=glow)
        self._bonds[(from_id, to_id)] = bond
        return bond

    def change(self, from_id: str, to_id: str,
               strength_delta: int = 0, glow_delta: int = 0,
               new_type: Optional[str] = None) -> Optional[Bond]:
        """Apply delta changes to an existing bond. Creates one if missing.

        Returns the updated Bond, or None if the IDs are the same (no self-bonds).
        """
        if from_id == to_id:
            return None

        bond = self.get(from_id, to_id)
        if bond is None:
            bond = Bond(from_id=from_id, to_id=to_id, type="灰",
                        strength=50, glow=0)
            self._bonds[(from_id, to_id)] = bond

        bond.strength = max(0, min(100, bond.strength + strength_delta))
        bond.glow = max(0, min(100, bond.glow + glow_delta))
        if new_type is not None and new_type in VALID_TYPES:
            bond.type = new_type
        return bond

    # ── Delta parsing ──

    def apply_delta(self, delta_string: str) -> List[Bond]:
        """Parse and apply a bond delta string from an event outcome.

        Format: "bond_chaoyin_yuanzhou:+3;bond_chenhai_suwan:-4"
        Returns list of affected bonds.
        """
        results: List[Bond] = []
        if not delta_string or delta_string.strip().lower() in ("none", ""):
            return results

        for part in delta_string.split(";"):
            part = part.strip()
            if not part or ":" not in part:
                continue

            # Split "bond_chaoyin_yuanzhou:+3" → key, delta
            colon_idx = part.rfind(":")
            key = part[:colon_idx].strip()
            delta_str = part[colon_idx + 1:].strip()

            # Strip "bond_" prefix if present
            if key.startswith("bond_"):
                key = key[5:]

            try:
                delta = int(delta_str)
            except ValueError:
                continue

            # Look up full IDs
            pair = self._bond_key_map.get(key)
            if pair is None:
                continue  # Unknown bond key, skip silently

            from_id, to_id = pair
            bond = self.change(from_id, to_id, strength_delta=delta,
                               glow_delta=abs(delta) if delta != 0 else 0)
            if bond:
                results.append(bond)

        return results

    # ── Queries ──

    def all_bonds(self) -> List[Bond]:
        """Return all bonds."""
        return list(self._bonds.values())

    def bonds_from(self, npc_id: str) -> List[Bond]:
        """All bonds originating from an NPC."""
        return [b for (f, _), b in self._bonds.items() if f == npc_id]

    def bonds_to(self, npc_id: str) -> List[Bond]:
        """All bonds pointing to an NPC."""
        return [b for (_, t), b in self._bonds.items() if t == npc_id]

    # ── Serialization ──

    def to_dict(self) -> Dict[str, Any]:
        """Serialize all bonds to a dict."""
        bonds_data = []
        for (f, t), b in self._bonds.items():
            bonds_data.append({
                "from": f, "to": t,
                "type": b.type, "strength": b.strength, "glow": b.glow,
            })
        return {"bonds": bonds_data}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BondManager":
        """Deserialize from a dict."""
        mgr = cls()
        for item in data.get("bonds", []):
            mgr._bonds[(item["from"], item["to"])] = Bond(
                from_id=item["from"], to_id=item["to"],
                type=item["type"], strength=item["strength"], glow=item["glow"],
            )
        return mgr
