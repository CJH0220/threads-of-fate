"""Karma system module tests.

Coverage:
- karma_loader: CSV loading, node parsing
- karma_types: KarmaLine, KarmaNode, progress thresholds
- karma_manager: delta parsing, progress tracking, serialization
"""

import pytest

from src.backend.engine.karma import (
    KarmaManager,
    KarmaLine,
    KarmaNode,
    load_karma_nodes,
)


# ═══════════════════════════════════════════════════
# KarmaNode / KarmaLine types
# ═══════════════════════════════════════════════════

class TestKarmaTypes:
    """Tests for KarmaLine and KarmaNode."""

    def test_line_progress_default(self):
        line = KarmaLine(id="test_line", npc_id="npc_a")
        assert line.progress == 0.0
        assert not line.is_complete

    def test_line_is_complete(self):
        line = KarmaLine(id="test_line", npc_id="npc_a", progress=100.0)
        assert line.is_complete

    def test_current_node_no_nodes(self):
        line = KarmaLine(id="test_line", npc_id="npc_a")
        assert line.current_node is None

    def test_current_node_based_on_progress(self):
        nodes = [
            KarmaNode(id="n1", node_order=1, name="开始", week_range="W1",
                      required_conditions="none", success_bias="a", failure_bias="b",
                      visible_to_player="Yes", related_event_ids=[], description=""),
            KarmaNode(id="n2", node_order=2, name="发展", week_range="W2",
                      required_conditions="none", success_bias="a", failure_bias="b",
                      visible_to_player="Yes", related_event_ids=[], description=""),
            KarmaNode(id="n3", node_order=3, name="高潮", week_range="W3",
                      required_conditions="none", success_bias="a", failure_bias="b",
                      visible_to_player="Yes", related_event_ids=[], description=""),
            KarmaNode(id="n4", node_order=4, name="结局", week_range="W4",
                      required_conditions="none", success_bias="a", failure_bias="b",
                      visible_to_player="Yes", related_event_ids=[], description=""),
        ]
        line = KarmaLine(id="test", npc_id="a", progress=0.0, nodes=nodes)

        # At 0%, should be node 1
        assert line.current_node.name == "开始"

        # At 30% (between node 1 and 2), should be node 2
        line.progress = 30.0
        assert line.current_node.name == "发展"

        # At 75% (between node 2 and 3), should be node 3
        line.progress = 55.0
        assert line.current_node.name == "高潮"

        # At 100%, should be node 4
        line.progress = 100.0
        assert line.current_node.name == "结局"

    def test_next_node(self):
        nodes = [
            KarmaNode(id="n1", node_order=1, name="开始", week_range="W1",
                      required_conditions="none", success_bias="a", failure_bias="b",
                      visible_to_player="Yes", related_event_ids=[], description=""),
            KarmaNode(id="n2", node_order=2, name="发展", week_range="W2",
                      required_conditions="none", success_bias="a", failure_bias="b",
                      visible_to_player="Yes", related_event_ids=[], description=""),
        ]
        line = KarmaLine(id="test", npc_id="a", progress=0.0, nodes=nodes)
        assert line.next_node.name == "发展"
        line.progress = 100.0
        assert line.next_node is None


# ═══════════════════════════════════════════════════
# CSV loader
# ═══════════════════════════════════════════════════

class TestKarmaLoader:
    """Tests for CSV karma node loading."""

    def test_loads_nodes(self):
        nodes_by_line = load_karma_nodes()
        assert len(nodes_by_line) >= 4  # at least 4 karma lines

    def test_each_line_has_sorted_nodes(self):
        nodes_by_line = load_karma_nodes()
        for line_id, nodes in nodes_by_line.items():
            orders = [n.node_order for n in nodes]
            assert orders == sorted(orders), f"{line_id} nodes not sorted"

    def test_nodes_have_required_fields(self):
        nodes_by_line = load_karma_nodes()
        for line_id, nodes in nodes_by_line.items():
            for node in nodes:
                assert node.id
                assert node.name
                assert node.node_order >= 1
                assert node.description

    def test_chaoyin_witch_line_exists(self):
        nodes_by_line = load_karma_nodes()
        assert "chaoyin_witch_line" in nodes_by_line
        assert len(nodes_by_line["chaoyin_witch_line"]) == 4


# ═══════════════════════════════════════════════════
# KarmaManager
# ═══════════════════════════════════════════════════

class TestKarmaManager:
    """Tests for KarmaManager."""

    def setup_method(self):
        self.mgr = KarmaManager()
        self.mgr.init_from_csv()

    def test_init_loads_lines(self):
        assert len(self.mgr.all_lines()) >= 4

    def test_lines_for_npc(self):
        lines = self.mgr.lines_for_npc("lin_chaoyin")
        assert len(lines) == 1
        assert lines[0].id == "chaoyin_witch_line"

    def test_apply_single_delta(self):
        affected = self.mgr.apply_delta("chaoyin_witch_line:+15")
        assert len(affected) == 1
        assert affected[0].progress == 15.0

    def test_apply_multi_delta(self):
        affected = self.mgr.apply_delta(
            "chaoyin_witch_line:+10;yuanzhou_leave_line:+5"
        )
        assert len(affected) == 2

    def test_apply_negative_delta(self):
        self.mgr.apply_delta("chaoyin_witch_line:+30")
        self.mgr.apply_delta("chaoyin_witch_line:-10")
        assert self.mgr.get_progress("chaoyin_witch_line") == 20.0

    def test_progress_clamped_at_100(self):
        self.mgr.apply_delta("chaoyin_witch_line:+150")
        assert self.mgr.get_progress("chaoyin_witch_line") == 100.0

    def test_progress_clamped_at_0(self):
        self.mgr.apply_delta("chaoyin_witch_line:-50")
        assert self.mgr.get_progress("chaoyin_witch_line") == 0.0

    def test_empty_delta(self):
        assert self.mgr.apply_delta("none") == []
        assert self.mgr.apply_delta("") == []

    def test_unknown_line_skipped(self):
        affected = self.mgr.apply_delta("unknown_line:+10")
        assert affected == []

    def test_is_complete(self):
        self.mgr.apply_delta("chaoyin_witch_line:+100")
        line = self.mgr.get_line("chaoyin_witch_line")
        assert line.is_complete

    def test_get_progress(self):
        self.mgr.apply_delta("chaoyin_witch_line:+42.5")
        assert self.mgr.get_progress("chaoyin_witch_line") == 42.5

    def test_get_progress_unknown_line(self):
        assert self.mgr.get_progress("nonexistent") == 0.0

    def test_node_advances_with_progress(self):
        line = self.mgr.get_line("chaoyin_witch_line")
        assert line.current_node.name == "噩梦初现"  # node 1

        self.mgr.apply_delta("chaoyin_witch_line:+30")
        assert line.current_node.name == "巫女候选"  # node 2

        self.mgr.apply_delta("chaoyin_witch_line:+30")
        assert line.current_node.name == "身份回应"  # node 3


# ═══════════════════════════════════════════════════
# Serialization
# ═══════════════════════════════════════════════════

class TestKarmaSerialization:
    """Tests for to_dict / from_dict round-trip."""

    def setup_method(self):
        self.mgr = KarmaManager()
        self.mgr.init_from_csv()
        self.mgr.apply_delta("chaoyin_witch_line:+35")
        self.mgr.apply_delta("yuanzhou_leave_line:+20")

    def test_to_dict(self):
        data = self.mgr.to_dict()
        assert "lines" in data
        assert data["lines"]["chaoyin_witch_line"] == 35.0
        assert data["lines"]["yuanzhou_leave_line"] == 20.0

    def test_round_trip(self):
        data = self.mgr.to_dict()
        restored = KarmaManager.from_dict(data)
        assert restored.get_progress("chaoyin_witch_line") == 35.0
        assert restored.get_progress("yuanzhou_leave_line") == 20.0

    def test_round_trip_preserves_nodes(self):
        """After round-trip, node structure should be intact (reloaded from CSV)."""
        data = self.mgr.to_dict()
        restored = KarmaManager.from_dict(data)
        line = restored.get_line("chaoyin_witch_line")
        assert line is not None
        assert len(line.nodes) == 4
        assert line.current_node.name == "巫女候选"  # 35% → node 2


# ═══════════════════════════════════════════════════
# Integration with event delta strings
# ═══════════════════════════════════════════════════

class TestEventDeltaIntegration:
    """Tests using real event CSV karma delta strings."""

    def setup_method(self):
        self.mgr = KarmaManager()
        self.mgr.init_from_csv()

    def test_real_event_deltas(self):
        """All karma delta keys from real event outcomes should parse."""
        deltas = [
            "chaoyin_witch_line:+10",
            "yuanzhou_leave_line:+8",
            "chenhai_cult_line:+12",
            "guchenzhou_cult_line:+10",
            "huiyuan_temple_line:+8",
        ]
        for d in deltas:
            affected = self.mgr.apply_delta(d)
            assert len(affected) == 1, f"Failed to parse: {d}"

    def test_accumulated_progress(self):
        """Multiple events advancing the same line should accumulate."""
        self.mgr.apply_delta("chaoyin_witch_line:+10")
        self.mgr.apply_delta("chaoyin_witch_line:+5")
        self.mgr.apply_delta("chaoyin_witch_line:+8")
        assert self.mgr.get_progress("chaoyin_witch_line") == 23.0
