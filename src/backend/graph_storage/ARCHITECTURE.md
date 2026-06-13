# 缘线图存储 — 架构与工作流

## 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                      Python 后端（数据管理）                      │
│                                                                 │
│  models.py          graph.py           persistence.py           │
│  ┌──────────┐      ┌──────────────┐    ┌──────────────────┐    │
│  │ NPC      │──────│ Relationship │────│ save_graph()     │    │
│  │ Edge     │      │ Graph        │    │ load_graph()     │    │
│  └──────────┘      │              │    │                  │    │
│                    │ 邻接表+边字典 │    │ → JSON 文件      │    │
│                    └──────────────┘    └──────┬───────────┘    │
│                                               │                │
│    用途：策划配表 / AI批量生成 / 数据校验      │                │
└───────────────────────────────────────────────┼────────────────┘
                                                │
                                          JSON 文件
                                      data/relationships.json
                                                │
┌───────────────────────────────────────────────┼────────────────┐
│                       Godot 前端（游戏运行）   │                │
│                                               ▼                │
│  ┌──────────────────────────────────────────────────────┐     │
│  │  Autoload 单例: RelationshipGraph (GDScript)          │     │
│  │                                                      │     │
│  │  func _ready():                                      │     │
│  │      var file = FileAccess.open(json_path, READ)     │     │
│  │      var data = JSON.parse(file.get_as_text())       │     │
│  │      # 加载到内存，运行时直接读写                        │     │
│  │                                                      │     │
│  │  func get_edges_of(npc_id: String) -> Array:         │     │
│  │      ...                                             │     │
│  └──────────────────────────────────────────────────────┘     │
│                                                                 │
│    用途：运行时查询 / 玩家干预修改 / 存档导出                    │
└─────────────────────────────────────────────────────────────────┘
```

## 数据流向

```
策划配表 / AI生成
       │
       ▼
Python: create_graph() → add_npc() → add_edge() → save_graph()
       │
       ▼
data/relationships.json    ←── 统一的中间格式，两边都能读写
       │
       ▼
Godot: FileAccess + JSON.parse() → Dictionary → 运行时使用
```

## JSON 格式规范

```json
{
  "npcs": {
    "<npc_id>": {
      "id": "<npc_id>",
      "name": "<中文名>"
    }
  },
  "edges": [
    {
      "from": "<源NPC id>",
      "to": "<目标NPC id>",
      "type": "红|金|蓝|灰|黑",
      "strength": 0~100,
      "glow": 0~100
    }
  ]
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `npcs.<id>.id` | string | 唯一标识，仅含字母/数字/下划线 |
| `npcs.<id>.name` | string | 中文名，用于 UI 显示 |
| `edges[].from` | string | 源 NPC id，缘线为**有向边** |
| `edges[].to` | string | 目标 NPC id |
| `edges[].type` | string | 关系性质：红(爱情)/金(利益)/蓝(友情)/灰(陌生)/黑(仇恨) |
| `edges[].strength` | int | 强度 0~100，映射 UI 线条粗细 |
| `edges[].glow` | int | 活跃值 0~100，映射 UI 光效强弱 |

## API 对照表

| 操作 | Python (src/backend/api.py) | Godot (GDScript) |
|------|----------------------------|-------------------|
| 创建空图 | `create_graph()` | `RelationshipGraph.new()` |
| 加载 JSON | `load_graph(path)` | `FileAccess.open() + JSON.parse()` |
| 保存 JSON | `save_graph(graph, path)` | 运行时一般不需要回写文件 |
| 获取 NPC | `graph.get_npc(id)` | `npcs[id]` |
| 列出 NPC | `graph.list_npcs()` | `npcs.values()` |
| 获取某 NPC 所有边 | `graph.get_edges_of(id)` | 遍历 `edges` 数组过滤 |
| 查询单条边 | `graph.get_edge(from, to)` | 遍历 `edges` 匹配 from+to |
| 图统计 | `graph.summary()` | `{"npc_count": npcs.size(), "edge_count": edges.size()}` |

## 在 Godot 中读取（示例代码）

```gdscript
extends Node

var npcs: Dictionary = {}
var edges: Array = []

func load_relationships(path: String) -> void:
    var file = FileAccess.open(path, FileAccess.READ)
    if file == null:
        push_error("无法打开关系数据文件: " + path)
        return

    var json_string = file.get_as_text()
    file.close()

    var json = JSON.new()
    var error = json.parse(json_string)
    if error != OK:
        push_error("JSON 解析失败: " + json.get_error_message())
        return

    var data = json.get_data()
    npcs = data.get("npcs", {})
    edges = data.get("edges", [])

func get_edges_of(npc_id: String) -> Array:
    var result: Array = []
    for edge in edges:
        if edge["from"] == npc_id or edge["to"] == npc_id:
            result.append(edge)
    return result

func get_neighbors(npc_id: String) -> Array:
    var result: Array = []
    for edge in edges:
        if edge["from"] == npc_id:
            result.append(npcs[edge["to"]])
        elif edge["to"] == npc_id:
            result.append(npcs[edge["from"]])
    return result
```

## 文件位置约定

```
项目根目录/
├── src/
│   ├── backend/              ← Python 数据管理端
│   │   ├── models.py
│   │   ├── graph.py
│   │   ├── persistence.py
│   │   ├── api.py
│   │   └── ARCHITECTURE.md   ← 本文档
│   └── frontend/             ← Godot 项目（后续）
├── data/
│   └── relationships.json    ← Python 导出 & Godot 读取的共享文件
└── work.md                   ← 游戏策划案
```

## 后续扩展方向

- **Godot Autoload**：将加载逻辑封装为 autoload 单例 `RelationshipDB`，全局可访问
- **运行时修改**：Godot 侧增加 `add_edge` / `remove_edge` / `update_edge` 方法
- **增量更新**：大型关系变更时 Python 重新导出 JSON，Godot 热重载
- **存档系统**：游戏存档时 Godot 将当前关系图导出为 JSON
