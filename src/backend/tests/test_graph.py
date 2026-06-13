"""RelationshipGraph 单元测试。

运行方式:
    cd src/backend
    python -m unittest discover tests/ -v
    # 或
    python -m pytest tests/ -v
"""

import json
import os
import tempfile
import unittest

from ..graph_storage.graph import RelationshipGraph
from ..graph_storage.persistence import load_graph, save_graph


class TestNPC(unittest.TestCase):
    """NPC 节点 CRUD 测试。"""

    def setUp(self):
        self.g = RelationshipGraph()

    def test_add_npc(self):
        npc = self.g.add_npc("aaa", "角色A")
        self.assertEqual(npc.id, "aaa")
        self.assertEqual(npc.name, "角色A")
        self.assertEqual(self.g.npc_count, 1)

    def test_add_duplicate_npc_raises(self):
        self.g.add_npc("aaa", "角色A")
        with self.assertRaises(ValueError):
            self.g.add_npc("aaa", "角色B")

    def test_add_npc_invalid_id(self):
        with self.assertRaises(ValueError):
            self.g.add_npc("", "空id")
        with self.assertRaises(ValueError):
            self.g.add_npc("a-b", "有连字符")  # 连字符不允许
        with self.assertRaises(ValueError):
            self.g.add_npc("中文", "中文id")

    def test_add_npc_empty_name(self):
        with self.assertRaises(ValueError):
            self.g.add_npc("valid_id", "")

    def test_remove_npc(self):
        self.g.add_npc("aaa", "角色A")
        self.g.remove_npc("aaa")
        self.assertEqual(self.g.npc_count, 0)
        self.assertIsNone(self.g.get_npc("aaa"))

    def test_remove_nonexistent_npc(self):
        # 不存在也不抛异常
        self.g.remove_npc("ghost")

    def test_remove_npc_cascades_edges(self):
        self.g.add_npc("aaa", "A")
        self.g.add_npc("bbb", "B")
        self.g.add_edge("aaa", "bbb", "红", 50, 50)
        self.g.add_edge("bbb", "aaa", "蓝", 30, 20)

        self.g.remove_npc("aaa")
        self.assertEqual(self.g.edge_count, 0)
        self.assertEqual(len(self.g.get_edges_of("bbb")), 0)

    def test_get_npc(self):
        self.g.add_npc("aaa", "A")
        self.assertIsNotNone(self.g.get_npc("aaa"))
        self.assertIsNone(self.g.get_npc("ghost"))

    def test_list_npcs(self):
        self.g.add_npc("aaa", "A")
        self.g.add_npc("bbb", "B")
        npcs = self.g.list_npcs()
        self.assertEqual(len(npcs), 2)
        self.assertIn(self.g.get_npc("aaa"), npcs)


class TestEdge(unittest.TestCase):
    """缘线边 CRUD 测试。"""

    def setUp(self):
        self.g = RelationshipGraph()
        self.g.add_npc("aaa", "A")
        self.g.add_npc("bbb", "B")
        self.g.add_npc("ccc", "C")

    def test_add_edge(self):
        edge = self.g.add_edge("aaa", "bbb", "红", 60, 50)
        self.assertEqual(edge.from_id, "aaa")
        self.assertEqual(edge.to_id, "bbb")
        self.assertEqual(edge.type, "红")
        self.assertEqual(edge.strength, 60)
        self.assertEqual(edge.glow, 50)
        self.assertEqual(self.g.edge_count, 1)

    def test_add_edge_overwrites(self):
        self.g.add_edge("aaa", "bbb", "红", 60, 50)
        self.g.add_edge("aaa", "bbb", "金", 30, 80)
        self.assertEqual(self.g.edge_count, 1)
        edge = self.g.get_edge("aaa", "bbb")
        self.assertEqual(edge.type, "金")
        self.assertEqual(edge.strength, 30)
        self.assertEqual(edge.glow, 80)

    def test_add_edge_missing_npc_raises(self):
        with self.assertRaises(ValueError):
            self.g.add_edge("aaa", "ghost", "红", 50, 50)
        with self.assertRaises(ValueError):
            self.g.add_edge("ghost", "aaa", "红", 50, 50)

    def test_add_edge_invalid_type(self):
        with self.assertRaises(ValueError):
            self.g.add_edge("aaa", "bbb", "绿", 50, 50)  # 没有绿色

    def test_add_edge_invalid_range(self):
        with self.assertRaises(ValueError):
            self.g.add_edge("aaa", "bbb", "红", -1, 50)
        with self.assertRaises(ValueError):
            self.g.add_edge("aaa", "bbb", "红", 101, 50)
        with self.assertRaises(ValueError):
            self.g.add_edge("aaa", "bbb", "红", 50, -1)
        with self.assertRaises(ValueError):
            self.g.add_edge("aaa", "bbb", "红", 50, 101)

    def test_remove_edge(self):
        self.g.add_edge("aaa", "bbb", "红", 60, 50)
        removed = self.g.remove_edge("aaa", "bbb")
        self.assertTrue(removed)
        self.assertEqual(self.g.edge_count, 0)
        self.assertIsNone(self.g.get_edge("aaa", "bbb"))

    def test_remove_nonexistent_edge(self):
        removed = self.g.remove_edge("aaa", "bbb")
        self.assertFalse(removed)

    def test_get_edge(self):
        self.g.add_edge("aaa", "bbb", "红", 60, 50)
        edge = self.g.get_edge("aaa", "bbb")
        self.assertIsNotNone(edge)
        self.assertEqual(edge.type, "红")

    def test_get_all_edges(self):
        self.g.add_edge("aaa", "bbb", "红", 60, 50)
        self.g.add_edge("bbb", "ccc", "蓝", 40, 30)
        self.assertEqual(len(self.g.get_all_edges()), 2)


class TestGraphQueries(unittest.TestCase):
    """图查询测试。"""

    def setUp(self):
        self.g = RelationshipGraph()
        self.g.add_npc("aaa", "A")
        self.g.add_npc("bbb", "B")
        self.g.add_npc("ccc", "C")
        self.g.add_npc("ddd", "D")
        # aaa → bbb (红)
        self.g.add_edge("aaa", "bbb", "红", 60, 50)
        # aaa → ccc (蓝)
        self.g.add_edge("aaa", "ccc", "蓝", 40, 30)
        # ddd → aaa (灰)
        self.g.add_edge("ddd", "aaa", "灰", 20, 10)

    def test_get_edges_of(self):
        edges = self.g.get_edges_of("aaa")
        self.assertEqual(len(edges), 3)  # aaa→bbb, aaa→ccc, ddd→aaa

    def test_get_edges_of_filter_type(self):
        edges = self.g.get_edges_of("aaa", edge_type="红")
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0].to_id, "bbb")

    def test_get_edges_of_nonexistent_npc(self):
        self.assertEqual(len(self.g.get_edges_of("ghost")), 0)

    def test_get_outgoing(self):
        outgoing = self.g.get_outgoing("aaa")
        self.assertEqual(len(outgoing), 2)

    def test_get_incoming(self):
        incoming = self.g.get_incoming("aaa")
        self.assertEqual(len(incoming), 1)
        self.assertEqual(incoming[0].from_id, "ddd")

    def test_get_neighbors(self):
        neighbors = self.g.get_neighbors("aaa")
        self.assertSetEqual(neighbors, {"bbb", "ccc", "ddd"})

    def test_get_neighbors_filter_type(self):
        neighbors = self.g.get_neighbors("aaa", edge_type="红")
        self.assertSetEqual(neighbors, {"bbb"})

    def test_get_neighbors_nonexistent_npc(self):
        self.assertEqual(len(self.g.get_neighbors("ghost")), 0)

    def test_summary(self):
        s = self.g.summary()
        self.assertEqual(s["npc_count"], 4)
        self.assertEqual(s["edge_count"], 3)
        self.assertIn("红", s["edge_type_distribution"])


class TestPersistence(unittest.TestCase):
    """JSON 持久化往返测试。"""

    def setUp(self):
        self.g = RelationshipGraph()
        self.g.add_npc("lin_chaoyin", "林潮音")
        self.g.add_npc("chen_yuanzhou", "陈远舟")
        self.g.add_npc("gu_chenzhou", "顾沉舟")
        self.g.add_edge("lin_chaoyin", "chen_yuanzhou", "红", 60, 50)
        self.g.add_edge("lin_chaoyin", "gu_chenzhou", "黑", 80, 30)
        self.g.add_edge("chen_yuanzhou", "lin_chaoyin", "红", 55, 45)

    def test_save_and_load_roundtrip(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            tmp_path = f.name

        try:
            save_graph(self.g, tmp_path)
            loaded = load_graph(tmp_path)

            self.assertEqual(loaded.npc_count, 3)
            self.assertEqual(loaded.edge_count, 3)

            # 验证 NPC
            npc = loaded.get_npc("lin_chaoyin")
            self.assertIsNotNone(npc)
            self.assertEqual(npc.name, "林潮音")

            # 验证边
            edge = loaded.get_edge("lin_chaoyin", "chen_yuanzhou")
            self.assertIsNotNone(edge)
            self.assertEqual(edge.type, "红")
            self.assertEqual(edge.strength, 60)
            self.assertEqual(edge.glow, 50)
        finally:
            os.unlink(tmp_path)

    def test_save_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "sub", "data.json")
            save_graph(self.g, path)
            self.assertTrue(os.path.exists(path))

    def test_load_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            load_graph("/nonexistent/path/graph.json")


class TestEdgeCases(unittest.TestCase):
    """边界情况测试。"""

    def test_empty_graph(self):
        g = RelationshipGraph()
        self.assertEqual(g.npc_count, 0)
        self.assertEqual(g.edge_count, 0)
        self.assertEqual(g.list_npcs(), [])
        self.assertEqual(g.get_all_edges(), [])
        self.assertEqual(g.summary()["npc_count"], 0)

    def test_self_loop(self):
        """自环边：NPC 指向自己的关系也应支持（如自我厌恶）。"""
        g = RelationshipGraph()
        g.add_npc("aaa", "A")
        g.add_edge("aaa", "aaa", "黑", 70, 50)
        self.assertEqual(g.edge_count, 1)
        self.assertIn("aaa", g.get_neighbors("aaa"))

    def test_multiple_types_between_same_pair(self):
        """同一对 NPC 之间只能有一条边（后加覆盖先加）。"""
        g = RelationshipGraph()
        g.add_npc("aaa", "A")
        g.add_npc("bbb", "B")
        g.add_edge("aaa", "bbb", "红", 60, 50)
        g.add_edge("aaa", "bbb", "金", 30, 20)
        self.assertEqual(g.edge_count, 1)
        self.assertEqual(g.get_edge("aaa", "bbb").type, "金")

    def test_large_stress(self):
        """100 NPC + 500 边的压力测试。"""
        g = RelationshipGraph()
        for i in range(100):
            g.add_npc(f"npc_{i:03d}", f"角色{i}")

        edge_count = 0
        for i in range(100):
            # 每个 NPC 指向后面 5 个
            for j in range(1, 6):
                target = (i + j) % 100
                g.add_edge(
                    f"npc_{i:03d}",
                    f"npc_{target:03d}",
                    "灰",
                    (i * 7 + j * 13) % 101,
                    (i * 3 + j * 11) % 101,
                )
                edge_count += 1

        self.assertEqual(g.npc_count, 100)
        self.assertEqual(g.edge_count, edge_count)


if __name__ == "__main__":
    unittest.main()
