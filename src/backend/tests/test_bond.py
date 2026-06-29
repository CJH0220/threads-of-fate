"""Bond system module tests.

Coverage:
- bond_manager: set, get, change, delta parsing, serialization
- Bond: validation, type constraints
"""

import pytest

from src.backend.engine.bond import BondManager, Bond
from src.backend.data.npc_loader import load_npcs


# ═══════════════════════════════════════════════════
# Bond dataclass
# ═══════════════════════════════════════════════════

class TestBond:
    """Tests for Bond dataclass and validation."""

    def test_create_valid_bond(self):
        bond = Bond(from_id="lin_chaoyin", to_id="chen_yuanzhou",
                    type="红", strength=70, glow=50)
        assert bond.from_id == "lin_chaoyin"
        assert bond.to_id == "chen_yuanzhou"
        assert bond.type == "红"
        assert bond.strength == 70
        assert bond.glow == 50

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError, match="Invalid bond type"):
            Bond(from_id="a", to_id="b", type="绿", strength=50, glow=0)

    def test_strength_clamped(self):
        with pytest.raises(ValueError):
            Bond(from_id="a", to_id="b", type="灰", strength=150, glow=0)
        with pytest.raises(ValueError):
            Bond(from_id="a", to_id="b", type="灰", strength=-1, glow=0)

    def test_glow_clamped(self):
        with pytest.raises(ValueError):
            Bond(from_id="a", to_id="b", type="灰", strength=50, glow=101)


# ═══════════════════════════════════════════════════
# BondManager CRUD
# ═══════════════════════════════════════════════════

class TestBondManagerCRUD:
    """Tests for BondManager set/get/change."""

    def setup_method(self):
        self.mgr = BondManager()
        self.mgr.register_npcs(["lin_chaoyin", "chen_yuanzhou"])

    def test_set_and_get(self):
        self.mgr.set("lin_chaoyin", "chen_yuanzhou", "红", strength=80, glow=60)
        bond = self.mgr.get("lin_chaoyin", "chen_yuanzhou")
        assert bond is not None
        assert bond.type == "红"
        assert bond.strength == 80
        assert bond.glow == 60

    def test_get_nonexistent_returns_none(self):
        assert self.mgr.get("lin_chaoyin", "chen_yuanzhou") is None

    def test_set_overwrites(self):
        self.mgr.set("lin_chaoyin", "chen_yuanzhou", "蓝", strength=30, glow=0)
        self.mgr.set("lin_chaoyin", "chen_yuanzhou", "红", strength=85, glow=70)
        bond = self.mgr.get("lin_chaoyin", "chen_yuanzhou")
        assert bond.type == "红"
        assert bond.strength == 85

    def test_change_existing(self):
        self.mgr.set("lin_chaoyin", "chen_yuanzhou", "红", strength=50, glow=30)
        self.mgr.change("lin_chaoyin", "chen_yuanzhou", strength_delta=10, glow_delta=5)
        bond = self.mgr.get("lin_chaoyin", "chen_yuanzhou")
        assert bond.strength == 60
        assert bond.glow == 35

    def test_change_creates_if_missing(self):
        """change() on a nonexistent bond creates one with default type=灰."""
        bond = self.mgr.change("lin_chaoyin", "chen_yuanzhou", strength_delta=20)
        assert bond is not None
        assert bond.type == "灰"
        assert bond.strength == 70  # 50 default + 20

    def test_change_clamps_at_100(self):
        self.mgr.set("lin_chaoyin", "chen_yuanzhou", "红", strength=95, glow=0)
        self.mgr.change("lin_chaoyin", "chen_yuanzhou", strength_delta=20)
        assert self.mgr.get("lin_chaoyin", "chen_yuanzhou").strength == 100

    def test_change_clamps_at_0(self):
        self.mgr.set("lin_chaoyin", "chen_yuanzhou", "红", strength=5, glow=0)
        self.mgr.change("lin_chaoyin", "chen_yuanzhou", strength_delta=-20)
        assert self.mgr.get("lin_chaoyin", "chen_yuanzhou").strength == 0

    def test_change_self_bond_returns_none(self):
        result = self.mgr.change("lin_chaoyin", "lin_chaoyin", strength_delta=10)
        assert result is None


# ═══════════════════════════════════════════════════
# Delta parsing
# ═══════════════════════════════════════════════════

class TestDeltaParsing:
    """Tests for apply_delta() — event outcome bond strings."""

    def setup_method(self):
        npcs = load_npcs()
        self.npc_ids = [n.id for n in npcs]
        self.mgr = BondManager()
        self.mgr.register_npcs(self.npc_ids)

    def test_single_positive_delta(self):
        bonds = self.mgr.apply_delta("bond_chaoyin_yuanzhou:+3")
        assert len(bonds) == 1
        b = bonds[0]
        assert b.from_id == "lin_chaoyin"
        assert b.to_id == "chen_yuanzhou"

    def test_single_negative_delta(self):
        bonds = self.mgr.apply_delta("bond_yuanzhou_chenhai:-5")
        assert len(bonds) == 1

    def test_multi_delta(self):
        bonds = self.mgr.apply_delta(
            "bond_chaoyin_yuanzhou:+3;bond_chenhai_suwan:-4"
        )
        assert len(bonds) == 2

    def test_delta_changes_strength(self):
        self.mgr.set("lin_chaoyin", "chen_yuanzhou", "红", strength=70, glow=0)
        self.mgr.apply_delta("bond_chaoyin_yuanzhou:+5")
        b = self.mgr.get("lin_chaoyin", "chen_yuanzhou")
        assert b.strength == 75

    def test_empty_delta(self):
        assert self.mgr.apply_delta("none") == []
        assert self.mgr.apply_delta("") == []

    def test_unknown_bond_key_skipped(self):
        """Unknown bond keys are silently skipped."""
        bonds = self.mgr.apply_delta("bond_missing_key:+10")
        assert bonds == []

    def test_delta_increases_glow(self):
        self.mgr.set("lin_chaoyin", "chen_yuanzhou", "红", strength=50, glow=10)
        self.mgr.apply_delta("bond_chaoyin_yuanzhou:+8")
        b = self.mgr.get("lin_chaoyin", "chen_yuanzhou")
        assert b.glow == 18  # 10 + abs(8)

    def test_no_delta_does_not_change_glow(self):
        self.mgr.set("lin_chaoyin", "chen_yuanzhou", "红", strength=50, glow=10)
        self.mgr.apply_delta("bond_chaoyin_yuanzhou:+0")
        b = self.mgr.get("lin_chaoyin", "chen_yuanzhou")
        assert b.glow == 10


# ═══════════════════════════════════════════════════
# Queries
# ═══════════════════════════════════════════════════

class TestQueries:
    """Tests for bond query methods."""

    def setup_method(self):
        self.mgr = BondManager()
        self.mgr.register_npcs(["lin_chaoyin", "chen_yuanzhou", "chen_haisheng"])
        self.mgr.set("lin_chaoyin", "chen_yuanzhou", "红", strength=80, glow=60)
        self.mgr.set("lin_chaoyin", "chen_haisheng", "灰", strength=10, glow=0)
        self.mgr.set("chen_yuanzhou", "lin_chaoyin", "红", strength=70, glow=50)

    def test_all_bonds(self):
        assert len(self.mgr.all_bonds()) == 3

    def test_bonds_from(self):
        outgoing = self.mgr.bonds_from("lin_chaoyin")
        assert len(outgoing) == 2

    def test_bonds_to(self):
        incoming = self.mgr.bonds_to("lin_chaoyin")
        assert len(incoming) == 1
        assert incoming[0].from_id == "chen_yuanzhou"

    def test_bonds_from_empty(self):
        assert self.mgr.bonds_from("unknown") == []


# ═══════════════════════════════════════════════════
# Serialization
# ═══════════════════════════════════════════════════

class TestSerialization:
    """Tests for to_dict / from_dict round-trip."""

    def setup_method(self):
        self.mgr = BondManager()
        self.mgr.register_npcs(["lin_chaoyin", "chen_yuanzhou", "gu_chenzhou"])
        self.mgr.set("lin_chaoyin", "chen_yuanzhou", "红", strength=85, glow=70)
        self.mgr.set("gu_chenzhou", "lin_chaoyin", "黑", strength=30, glow=40)

    def test_to_dict(self):
        data = self.mgr.to_dict()
        assert len(data["bonds"]) == 2

    def test_round_trip(self):
        data = self.mgr.to_dict()
        restored = BondManager.from_dict(data)
        assert len(restored.all_bonds()) == 2

        original = self.mgr.get("lin_chaoyin", "chen_yuanzhou")
        restored_bond = restored.get("lin_chaoyin", "chen_yuanzhou")
        assert restored_bond.type == original.type
        assert restored_bond.strength == original.strength
        assert restored_bond.glow == original.glow

    def test_from_empty_dict(self):
        mgr = BondManager.from_dict({})
        assert mgr.all_bonds() == []


# ═══════════════════════════════════════════════════
# Real NPC data integration
# ═══════════════════════════════════════════════════

class TestWithRealNPCs:
    """Tests using the real 14 NPC list and event bond deltas."""

    def setup_method(self):
        npcs = load_npcs()
        self.npc_ids = [n.id for n in npcs]
        self.mgr = BondManager()
        self.mgr.register_npcs(self.npc_ids)

    def test_all_csv_bond_keys_parse(self):
        """Every bond delta key from the event CSV should parse correctly."""
        # These come from actual CSV bond deltas
        bond_strings = [
            "bond_chaoyin_yuanzhou:+3",
            "bond_chaoyin_huiyuan:+8",
            "bond_he_laosan_guchenzhou:+8",
            "bond_chenhai_guchenzhou:+10",
            "bond_yuanzhou_chenhai:-3",
            "bond_chenhai_suwan:-4",
            "bond_xuqing_jiangxueyi:-5",
            "bond_xumingchuan_xuqing:+3",
            "bond_zhouxingzhi_xumingchuan:+8",
            "bond_xumingchuan_zhao:+5",
            "bond_zhouxingzhi_huiyuan:-8",
            "bond_yuanzhou_chenhai:-10",
            "bond_chenhai_suwan:-8",
        ]
        for s in bond_strings:
            bonds = self.mgr.apply_delta(s)
            assert len(bonds) == 1, f"Failed to parse: {s}"

    def test_preset_relationships(self):
        """Set up key relationships from the design doc and verify."""
        # 林潮音→陈远舟: 红, strength 70, glow 60
        self.mgr.set("lin_chaoyin", "chen_yuanzhou", "红", strength=70, glow=60)
        self.mgr.set("chen_yuanzhou", "lin_chaoyin", "红", strength=75, glow=55)

        # 陈海生→陈远舟: 蓝(家庭), 但紧张
        self.mgr.set("chen_haisheng", "chen_yuanzhou", "蓝", strength=40, glow=30)

        # 顾沉舟→陈海生: 金(利用)
        self.mgr.set("gu_chenzhou", "chen_haisheng", "金", strength=60, glow=80)

        assert self.mgr.get("lin_chaoyin", "chen_yuanzhou").type == "红"
        assert self.mgr.get("chen_yuanzhou", "lin_chaoyin").type == "红"
        # Bond is asymmetric
        assert self.mgr.get("lin_chaoyin", "chen_yuanzhou").strength == 70
        assert self.mgr.get("chen_yuanzhou", "lin_chaoyin").strength == 75
