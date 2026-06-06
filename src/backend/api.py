"""对外公开的统一 API — 对图存储和持久化的薄封装。

使用示例:
    from src.backend.api import create_graph, load_graph, save_graph

    g = create_graph()
    g.add_npc("lin_chaoyin", "林潮音")
    g.add_npc("chen_yuanzhou", "陈远舟")
    g.add_edge("lin_chaoyin", "chen_yuanzhou", "红", 60, 50)
    save_graph(g, "data/relationships.json")

    g2 = load_graph("data/relationships.json")
    print(g2.get_edges_of("lin_chaoyin"))
"""

from pathlib import Path
from typing import Union

from .graph import RelationshipGraph
from .persistence import load_graph as _load_graph
from .persistence import save_graph as _save_graph


def create_graph() -> RelationshipGraph:
    """创建一个空的关系图。"""
    return RelationshipGraph()


def save_graph(graph: RelationshipGraph, filepath: Union[str, Path]) -> None:
    """将图保存到 JSON 文件。"""
    _save_graph(graph, filepath)


def load_graph(filepath: Union[str, Path]) -> RelationshipGraph:
    """从 JSON 文件加载图。"""
    return _load_graph(filepath)


def load_or_create(filepath: Union[str, Path]) -> RelationshipGraph:
    """从 JSON 文件加载图，若文件不存在则创建空图。"""
    path = Path(filepath)
    if path.exists():
        return _load_graph(path)
    return RelationshipGraph()
