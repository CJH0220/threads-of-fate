# Game1 开发日志

## 2026-07-29 — Bug 修复与内容生成质量提升

### Bug 修复

#### 1. 时间推进卡死 (Blocker)
- **问题**: 点击"推进时间"后界面永久卡在"命运流转中……"
- **根因**: GDScript 4 中 `CONNECT_ONE_SHOT` 连接的 lambda 回调在某些信号链路下不会触发
- **修复**: 用共享实例变量 `_settlement_arrived` 替代 lambda，`_on_settlement_complete()` 直接设置标志位
- **涉及文件**: `godot/scripts/adapters/backend_game_state.gd`

#### 2. 时间推进后仍显示"第1天 早上" (High)
- **问题**: 后端返回正确的 slot=noon，但 UI 显示未更新
- **根因**: `_on_settlement_complete()` 只设置了 `time_slot` 但漏了 `time_slot_label`
- **修复**: 三个时间跳转路径 (`_on_settlement_complete`, `_normalize_state`, `_mock_advance_time`) 均同步更新 label
- **涉及文件**: `godot/scripts/adapters/backend_game_state.gd`

#### 3. 前端软锁防护 (Medium)
- **问题**: `_do_advance_time()` 中 `await state.advance_time()` 异常时 `_advancing` 永久为 true
- **修复**: 用超时竞速模式替代直接 await，协程异常/超时自动恢复 UI
- **涉及文件**: `godot/scripts/ui/main_game_ui.gd`

#### 4. WebSocket 断线快速恢复 (Medium)
- **问题**: 等待 `settlement_complete` 期间 WS 断开，需等满 300 秒才降级
- **修复**: 循环内检测 `Backend.is_ws_connected()`，断开立即降级到 Mock
- **涉及文件**: `godot/scripts/adapters/backend_game_state.gd`

### 内容生成质量提升

#### 5. 对白内容丰富度 (High)
- **轻量对白**: 输出从 2-4 行@20 字 → 6-12 行@35 字，附带完整示例
- **完整对白**: Polish prompt 从"保守修剪"→"创造性扩展"，鼓励潜台词、节奏变化、微表情
- **Token 限制**: 轻量 512→2048，完整 2048→4096
- **涉及文件**: `src/backend/ai/dialogue_designer/pipeline.py`, `designer.py`

#### 6. 事件模板扩展 (High)
- 从 6 个模板扩展到 10 个：新增 heated_debate(争论), share_secret(分享秘密), ask_for_help(求助), shared_memory(回忆)
- `max_spontaneous_per_slot`: 2→3, `min_spontaneous`: 1→2
- `total_daily_bond_cap`: 5→8, `total_daily_happiness_cap`: 3→5
- 夜晚允许的模板从 3 个扩展到 7 个
- **涉及文件**: `design/data/event_templates.json`, `src/backend/ai/screenwriter/screenwriter.py`

#### 7. Screenwriter 提示词增强 (High)
- 新增【对话骨架要求】: score≥3 的事件必须提供 dialogue_skeleton
- 新增【时间背景】段: 早/午/晚各有时段特征指引
- 新增【有效地点列表】段: 列出 32 个地点 ID↔中文名对照
- 新增 `format_locations_for_system_prompt()` 和 `_SLOT_LABELS`
- **涉及文件**: `src/backend/ai/screenwriter/prompts.py`, `screenwriter.py`

#### 8. 地点名中文化 (Medium)
- `_LOCATION_CN` 字典扩展到 32 个地点，含所有 NPC 住所
- `_location_cn()` 函数：英文ID→中文名转换
- event_triggered 消息的 location_id 自动转换
- **涉及文件**: `src/backend/server/routes/ws_game.py`

### 新功能

#### 9. 托梦后 NPC 即时反馈 (Medium)
- 后端: `_generate_dream_reflection()` — NPC 收到托梦后生成 50-100 字第一人称内心思考
- 新增 WS 消息类型 `dream_reflection` (npc_name, dream_text, reflection)
- 前端: `DreamTextDialog.show_reflection()` — 只读弹窗展示 NPC 回响
- **涉及文件**: `ws_game.py`, `backend_client.gd`, `main_game_ui.gd`, `dream_text_dialog.gd`

### 修改文件清单

| 文件 | 改动 |
|------|------|
| `godot/scripts/adapters/backend_game_state.gd` | settlement_flag, time_slot_label, WS断线检测 |
| `godot/scripts/app/backend_client.gd` | dream_reflection 信号, 诊断日志 |
| `godot/scripts/ui/main_game_ui.gd` | 超时竞速模式, dream_reflection 处理 |
| `godot/scripts/ui/dream_text_dialog.gd` | show_reflection 只读弹窗 |
| `godot/scripts/ui/time_transition.gd` | (还原为原始状态) |
| `src/backend/ai/dialogue_designer/pipeline.py` | 轻量对白 6-12行, token 2048 |
| `src/backend/ai/dialogue_designer/designer.py` | Polish prompt 重写, token 4096 |
| `src/backend/ai/screenwriter/prompts.py` | 地点列表, 时间上下文, 对话骨架规则 |
| `src/backend/ai/screenwriter/screenwriter.py` | min_spontaneous=2, location_list, slot_label |
| `src/backend/server/routes/ws_game.py` | dream_reflection, _LOCATION_CN, _generate_dream_reflection |
| `design/data/event_templates.json` | 10 模板, composition_rules 更新 |
