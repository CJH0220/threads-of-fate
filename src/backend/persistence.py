"""JSON 文件持久化：将 RelationshipGraph 保存/加载到 JSON 文件。"""

import json
from pathlib import Path
from typing import Union

from .graph import RelationshipGraph
from .models import NPC, Edge


def save_graph(graph: RelationshipGraph, filepath: Union[str, Path]) -> None:
    """将图保存到 JSON 文件。

    Args:
        graph: 要保存的 RelationshipGraph 实例
        filepath: JSON 文件路径
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "npcs": {
            npc.id: {"id": npc.id, "name": npc.name}
            for npc in graph.list_npcs()
        },
        "edges": [
            {
                "from": edge.from_id,
                "to": edge.to_id,
                "type": edge.type,
                "strength": edge.strength,
                "glow": edge.glow,
            }
            for edge in graph.get_all_edges()
        ],
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_graph(filepath: Union[str, Path]) -> RelationshipGraph:
    """从 JSON 文件加载图。

    Args:
        filepath: JSON 文件路径

    Returns:
        加载好的 RelationshipGraph 实例

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: JSON 格式非法或数据校验失败
    """
    filepath = Path(filepath)

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    graph = RelationshipGraph()

    # 先加节点
    npcs_data = data.get("npcs", {})
    if not isinstance(npcs_data, dict):
        raise ValueError("JSON 中 'npcs' 字段必须是对象")

    for npc_id, npc_data in npcs_data.items():
        if not isinstance(npc_data, dict):
            raise ValueError(f"NPC '{npc_id}' 数据格式错误")
        graph.add_npc(npc_id, npc_data.get("name", npc_id))

    # 再加边
    edges_data = data.get("edges", [])
    if not isinstance(edges_data, list):
        raise ValueError("JSON 中 'edges' 字段必须是数组")

    for edge_data in edges_data:
        graph.add_edge(
            from_id=edge_data["from"],
            to_id=edge_data["to"],
            edge_type=edge_data["type"],
            strength=edge_data["strength"],
            glow=edge_data["glow"],
        )

    return graph
