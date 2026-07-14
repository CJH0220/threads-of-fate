# UI 规格：主地图 HUD

> 文档状态：v1.1（2026-07-14 前端重构同步）
> 前次版本：初稿（2026-06-10）
> 所属阶段：P0
> 引擎方向：Godot
> 美术方向：简约像素风

## 更新说明（v1.1）

- **危险征兆紧凑化**：左侧"危险提醒"从分行的垂直列表改为**横向紧凑筹码**（§5.1），不再占据地图视觉主导。
- **地图头像行程显示**：地点瓦片内嵌**当前时段在场角色头像**（§5.2），`MAX_PORTRAITS = 3`，超出显示 `+N`。NPC 的位置由 schedule 实时驱动。

---

## 0. 全局规范引用

本界面必须遵循：

- `ui-accessibility-guidelines.md`
- `ui-interaction-patterns.md`
- `ui-localization-guidelines.md`

---

## 1. 用途

主地图 HUD 是游戏内核心界面。玩家通过它观察归潮镇、查看时间和资源、选择地点或人物、处理事件，并推动时间流逝。

该界面必须始终回答玩家四个问题：

1. 现在是什么时间？
2. 我还剩多少资源？
3. 小镇哪里发生了什么？
4. 我下一步可以做什么？

---

## 2. 布局规格

```text
┌──────────────────────────────────────────────┐
│ 第12天 · 夜晚 │ 香火63 神力4 阳德20 阴德8 │ 设置 │
├──────────────────────────────────────────────┤
│ 归潮镇地图                                       │
│ 危险征兆筹码（紧凑）：[⚠ 港口] [✓ 寺庙]        │
│                                                │
│   [学校]   [寺庙]   [港口]                      │
│   👤👤     👤+1     👤👤👤                    │
│   [咖啡厅] [诊所]   [广场]   ...               │
│     👤      👤                                  │
├──────────────────────────────────────────────┤
│ [人物] [事件] [缘线] [业线]     [推动时间]     │
│ 当前上下文详情区                              │
└──────────────────────────────────────────────┘
```

---

## 3. 信息层级

### 一级信息

- 当前天数与时段
- 香火、神力、阳德、阴德
- 中央地图与当前事件标记
- 推动时间按钮

### 二级信息

- 当前天气
- 特殊日提示
- 当前选中地点 / 人物 / 事件摘要
- 底栏 Tab 内容

### 三级信息

- 资源变化来源
- 事件详细说明
- 缘线、业线的完整列表

---

## 4. 组件清单

| 组件 | 类型 | 内容 | 交互 |
|---|---|---|---|
| 顶栏 | `HBoxContainer` | 时间、资源、设置 | 设置按钮可点击 |
| 时间显示 | `Label` | 第 X 天 · 早/午/晚 | Hover 显示周进度 |
| 资源显示 | 图标 + `Label` | 香火、神力、阳德、阴德 | Hover 显示解释 |
| **危险征兆筹码**（v1.1） | `HBoxContainer` 内 `DangerWarningItem` 列表 | 横向紧凑筹码：未查看 `⚠ 地点名`，已查看 `✓ 地点名 已阅` | 点击打开事件详情弹窗；推动时间前若有未查看筹码会触发"是否仍要推进"二次确认 |
| 地图区 | `Control` / `TextureRect` | 归潮镇地图 | 地点与事件可点击 |
| **地点瓦片**（v1.1） | `PanelContainer` 内嵌头像行 | 地点名 + **当前时段在场角色头像**（最多 3 张，超出显示 `+N`） | 点击打开地点面板；头像 Hover 显示角色名 |
| 事件标记 | `TextureButton` | 当前事件图标 | 打开事件面板 |
| 底栏 Tab | Button 组 | 人物、事件、缘线、业线 | 切换上下文 |
| 上下文区 | `PanelContainer` | 当前 Tab 内容 | 内容项可点击 |
| 推动时间 | `Button` | 结束当前时段 | 触发确认 / 结算 |

---

## 5. 地图交互

MVP 阶段地图可以是固定尺寸像素背景，不强制实现缩放和平移。

| 操作 | 结果 |
|---|---|
| 点击地点 | 打开地点面板 |
| 点击地点瓦片内的角色头像 | 打开人物面板（v1.1） |
| 点击人物头像 / 标记 | 打开人物面板 |
| 点击事件标记 | 打开事件推进面板或事件详情 |
| Hover 地点 | 显示地点名和当前人数 |
| Hover 事件 | 显示事件名、紧急程度 |
| Hover 地点内头像 | 显示角色姓名 |

事件标记优先级：

1. 强硬不幸 / 危险事件
2. 主线事件
3. NPC 业线事件
4. 日常事件

---

## 5.1 危险征兆筹码（v1.1）

危险征兆采用**横向紧凑筹码**形式，不再独占左侧面板：

| 项目 | 规格 |
|---|---|
| 容器 | `HBoxContainer`，单行，间距 6px，高度 28px |
| 条目 | `DangerWarningItem` 筹码（`PanelContainer`） |
| 未查看态 | 红底红边（约 `#c1504a`），图标 `⚠`，文本仅显示 `地点名` |
| 已查看态 | 绿底绿边（约 `#6a8a65`），图标 `✓`，文本 `{地点名} 已阅` |
| 点击 | 打开对应事件详情弹窗 |
| 推动时间前 | 若仍有**未查看**筹码，弹出二次确认对话框 |
| 无危险征兆时 | 容器隐藏，不占地图空间 |

设计意图：危险征兆从"地图左侧固定列"改为"地图上方紧凑筹码"，让地图视觉更主导，同时保留推动时间前的二次确认语义。

---

## 5.2 地点瓦片头像行（v1.1）

每个地点瓦片在地点名下方嵌入**当前时段在场角色头像**，让玩家一眼看出"谁在哪里"。

| 项目 | 规格 |
|---|---|
| 头像来源 | `PortraitService` 统一服务（v1.1） |
| 最大显示 | `MAX_PORTRAITS = 3` |
| 超出显示 | 显示前 3 张 + 文字 `+N`（N = 在场人数 − 3） |
| 头像尺寸 | `PORTRAIT_SIZE = 32` px（像素风） |
| 数据驱动 | NPC 的 `schedule[current_time_slot]` → `location_id`（v1.1 修复：原来用静态 `current_location_id`，导致时段变化后地点头像未刷新） |
| 时段切换 | 推动时间后由状态服务发出 `npc_updated` 信号，地点瓦片订阅刷新 |
| 点击头像 | 打开人物面板 |
| 空地点 | 仅显示地点名，不显示头像行 |

示例（Day 1 下午）：

| 地点 | 在场 | 瓦片显示 |
|---|---|---|
| 学校 | 林潮音、陈海生 | 两张头像 |
| 咖啡厅 | 林潮音、陈远舟 | 两张头像 |
| 港口 | 4 人 | 前 3 头像 + `+1` |

---

## 6. 底栏 Tab

| Tab | 内容 | MVP |
|---|---|---|
| 人物 | 当前选中 NPC 摘要；无选中时提示选择居民 | 是 |
| 事件 | 当前时段事件列表，按优先级排序 | 是 |
| 缘线 | 简版关系列表 | P1 |
| 业线 | 简版命运进度列表 | P1 |

---

## 7. 推动时间流程

```text
点击“推动时间”
→ 检查是否有未查看危险事件
→ 若有，弹出二次确认
→ 显示“命运流转中……”短暂过渡
→ 系统推进到下一时段
→ 刷新地图、资源、NPC 位置、事件
→ 如触发关键事件，进入事件推进面板
```

---

## 8. 状态与变体

| 状态 | 表现 |
|---|---|
| 默认状态 | 显示地图和基础 HUD |
| 无事件 | 事件 Tab 显示“此刻风平浪静” |
| 有危险事件 | 左侧提示区和事件标记变红 |
| 神力为 0 | 干预入口灰化 |
| 推动时间中 | 遮罩 + 加载文案 |
| 周末结算 | 推动时间后进入周结算界面 |

---

## 9. Godot 实现建议

```text
MainGameUI (Control)
├── TopBar (HBoxContainer)
│   ├── TimeLabel
│   ├── IncenseDisplay
│   ├── DivinePowerDisplay
│   ├── YangVirtueDisplay
│   ├── YinVirtueDisplay
│   ├── MenuButton
├── MainArea (VBoxContainer)            # v1.1 改为 VBox
│   ├── MapTitleBar (HBoxContainer)
│   │   ├── MapTitle
│   │   └── HintLabel
│   ├── DangerWarnings (HBoxContainer)  # v1.1 紧凑筹码容器
│   ├── MapScroll (ScrollContainer)
│   │   └── MapArea (Control)
│   │       ├── MapBackground (ColorRect)
│   │       └── LocationsContainer (Control)  # v1.1 内嵌 MapLocationTile
├── BottomPanel (PanelContainer)
│   ├── TabButtons (HBoxContainer)
│   │   ├── CharactersTabButton / EventsTabButton
│   │   ├── BondViewButton / DestinyViewButton
│   │   └── AdvanceTimeButton
│   └── ContextBody (ScrollContainer)
│       └── ContextList (HBoxContainer)
├── ModalLayer (CanvasLayer)
│   ├── DetailPopup (含 BondView / DestinyView / CharacterEndingScreen / DialogueEventScreen / TimeTransition / DreamTextDialog / NpcChatDialog)
│   ├── DangerConfirm (ConfirmationDialog)
│   ├── InterventionConfirm (ConfirmationDialog)
│   └── MenuConfirm (ConfirmationDialog)
```

---

## 10. 数据需求

| 数据 | 来源 | 刷新时机 |
|---|---|---|
| 当前天数 / 时段 | TimeSystem | 推动时间后 |
| 香火 / 神力 / 阳德 / 阴德 | PlayerResourceSystem | 事件、干预、结算后 |
| 地点列表 | LocationRegistry | 初始化 |
| 地点状态 | LocationStateSystem | 每时段 |
| NPC 当前时段位置（v1.1） | **NPCScheduleSystem · `schedule[current_time_slot]`** | 每时段（推动时间时刷新） |
| NPC 在场名单（v1.1） | StateService `get_locations()` | 每时段（适配器层聚合 `present_npc_ids` / `present_names` / `npc_count`） |
| NPC 头像 | **PortraitService**（v1.1） | 按需异步加载 |
| 事件标记 | EventScheduler | 每时段 |
| 危险事件状态 | EventRiskSystem | 每时段 |

---

## 11. 验收标准

- [ ] 顶栏正确显示当前天数、时段、香火、神力、阳德、阴德。
- [ ] 地图上至少 3 个地点可点击并打开地点面板。
- [ ] 当前时段事件能以图标显示在地图上。
- [ ] 点击事件标记能进入事件推进面板。
- [ ] 底栏人物 / 事件 Tab 可切换并显示正确空状态。
- [ ] 点击推动时间后，时段推进且地图事件刷新。
- [ ] 有危险事件未查看时，推动时间前出现二次确认。
- [ ] 神力为 0 时，干预入口不可点击并给出提示。
- [ ] **v1.1**：危险征兆以横向紧凑筹码显示在地图上方，未查看为红色 `⚠`，已查看为绿色 `✓ 已阅`；无征兆时筹码容器隐藏。
- [ ] **v1.1**：每个地点瓦片显示当前时段在场角色头像，最多 3 张；超出显示 `+N`。
- [ ] **v1.1**：推动时间（时段切换）后，地点瓦片内的头像按 `schedule[current_time_slot]` 实时刷新。
- [ ] **v1.1**：点击地点瓦片内的头像能打开对应人物面板。
