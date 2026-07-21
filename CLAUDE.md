# 《命运的织线》(Threads of Fate)

2D 像素风命运干预 / 叙事模拟游戏。玩家扮演归潮镇土地公，在 60 天内通过间接干预改变 14 名镇民的命运。

## 技术栈

- **引擎**: Godot 4.4 + GDScript（前端）
- **后端**: Python FastAPI + asyncio
- **AI**: Anthropic Claude API（编剧 Agent / NPC Agent）+ llama.cpp（本地推理）
- **通信**: HTTP REST + WebSocket
- **美术**: 简约 2D 像素风（Stardew Valley 方向）
- **版本控制**: Git, trunk-based development

## 项目结构

```
/
├── godot/             # Godot 前端（场景、脚本、资源）
├── src/backend/       # FastAPI 后端 + AI Agent（编剧/NPC/叙事）
├── design/            # 策划文档总目录
│   ├── 总体策划案.md   # 主策划案 v1.9（项目总权威）
│   ├── README.md      # 策划文档索引
│   ├── system/        # 11 个系统策划文档
│   ├── story/         # 剧情大纲 v3.0（72 beats, 全 9 周）
│   ├── gdd/           # 游戏概念 + 多 Agent 架构
│   ├── content/       # NPC 设定、剧情脚本
│   ├── UI/            # 33 个 UI 界面规格书
│   ├── art/           # 美术方向 + AI 提示词
│   ├── data/          # 数据表（CSV/JSON）
│   ├── audio/         # 音频方向
│   ├── check/         # QA 检查清单
│   └── 架构决策/       # 架构决策记录
├── docs/technical/    # 技术集成文档
├── scripts/           # 独立测试脚本
├── tools/             # 工具脚本（AI 头像生成等）
├── prototypes/        # 概念原型
├── production/        # 制作管理（会话状态/日志）
├── TEAMWORK.md        # 团队协作指南
└── 前后端交付案.md     # 前后端交付文档
```

## 权威层级

修改任何内容前，请先确认权威源：

| 优先级 | 权威源 | 说明 |
|--------|--------|------|
| 1 | `design/总体策划案.md` (v1.9) | 项目总权威 |
| 2 | `design/system/*.md` | 各子系统权威 |
| 3 | `design/story/story_outline_full.json` (v3.0) | 剧情大纲权威（72 beats） |
| 4 | `design/data/*.csv`（中文表） | 数据表策划权威 |
| 5 | `design/UI/ui-spec-*.md` | 各界面 UI 权威 |

**事件表三层关系**：`事件配置表.csv`（策划主表）→ `events_complete.csv`（英文导出，勿手动编辑）→ `godot/data/mock/events.json`（Mock 子集）

## 协作规则

- **用户驱动协作**：提问 → 选项 → 决策 → 草稿 → 审批
- 写文件前必须问"我可以写入 [路径] 吗？"
- 多文件变更需要明确审批
- **不自动推送 git**——提交可以，推送需要单独确认
- 所有交流与输出使用中文，代码/变量/路径使用英文

## 一致性规则

| 维度 | 规范 |
|------|------|
| 地点 | 归潮镇 |
| 玩家 | 土地公 / 岛爷 |
| 资源 | 香火、神力、阳德、阴德 |
| 时间 | 60 天 × 3 时段（早/午/晚）× 9 周 |
| NPC (14) | 林潮音、陈远舟、顾沉舟、江雪仪、许明川、陈海生、许晴、周行知、慧圆、苏婉、叶可可、林月琴、何老三、赵守正 |
| 内容尺度 | 暴力/情感/邪教使用暗示，禁止露骨描写 |
| 托梦消耗 | **3 神力**（v1.1 后统一值） |

## 当前进度

- **剧情大纲**: v3.0 完成（W1-W9 全覆盖, 72 beats）
- **后端**: 编剧 Agent + NPC Agent 核心逻辑已实现，W1-W2 测试通过
- **前端**: Godot UI 框架搭建完成，Mock 数据离线可用
- **美术**: 15 个 NPC 头像 + 11 个地点背景已生成
- **UI**: 33 个界面规格书完成

> 首次会话？阅读 `design/README.md` 了解策划文档结构，或 `design/项目现状梳理.md` 了解项目全貌。
