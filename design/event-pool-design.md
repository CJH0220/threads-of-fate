# 事件池系统设计文档

## 1. 概述

事件池是《命运的织线》的核心叙事驱动系统，负责在合适的时间、地点、状态下触发对应的剧情事件，推动 NPC 命运线与小镇整体剧情发展。

### 1.1 设计目标

| 目标 | 说明 |
|------|------|
| **确定性** | 锚点事件必须在指定时间触发，确保核心剧情不丢失 |
| **涌现性** | 日常事件根据 NPC 状态与关系动态匹配，营造真实感 |
| **可扩展性** | 新增事件无需修改代码，仅需更新 CSV 配置 |
| **可追溯性** | 完整记录事件触发历史与条件匹配过程 |

### 1.2 事件分类层级

```
事件池
├─ 锚点事件 (Anchor Events) —— 100% 强制触发，不可跳过
│  ├─ 剧情锚点：关键剧情节点
│  └─ 结局前置：触发特定结局的必要条件
├─ 关键事件 (Key Events) —— 高权重，NPC 命运转折点
│  ├─ 个人主线：单一 NPC 核心命运线
│  └─ 关系事件：多 NPC 互动节点
└─ 日常事件 (Daily Events) —— 填充型，低权重随机触发
   ├─ 地点事件：特定地点发生
   ├─ NPC 互动：两人或多人日常
   └─ 环境事件：天气、节日等背景叙事
```

---

## 2. 触发条件体系

### 2.1 触发条件维度

| 维度 | 字段 | 说明 | 示例值 |
|------|------|------|--------|
| **时间范围** | `week_range` | 周范围 | `W1`, `W2-W4`, `Final` |
| | `day_range` | 天范围 | `Day1`, `Day3-5`, 留空=任意 |
| | `time_slot` | 时段 | `Morning`, `Afternoon`, `Night`, `Any` |
| **空间范围** | `location` | 地点 | `school`, `beach`, 留空=任意 |
| **人物在场** | `participants` | 必须同时在场的 NPC ID 列表 | `["lin_chaoyin", "chen_fanghua"]` |
| **关系条件** | `bond_min` | 缘线最小值 | `bond_chaoyin_fanghua >= 50` |
| | `bond_max` | 缘线最大值 | `bond_chaoyin_laowang < 20` |
| **业线进度** | `karma_min` | 业线进度最小值 | `chaoyin_witch >= 30` |
| | `karma_max` | 业线进度最大值 | `fanghua_redemption <= 80` |
| **NPC 状态** | `npc_happiness_min` | 幸福度下限 | `lin_chaoyin:happiness >= 60` |
| | `npc_energy_min` | 精力下限 | `chen_fanghua:energy >= 30` |
| | `npc_emotion` | 情绪要求 | `laowang:emotion = angry` |
| **资源条件** | `resource_min` | 资源下限 | `incense >= 80` |
| | `resource_max` | 资源上限 | `divine_power < 5` |
| **历史条件** | `prev_event` | 前置事件已触发 | `w1_chaoyin_study triggered` |
| | `prev_not_event` | 前置事件未触发 | `w2_fanghua_secret not triggered` |
| **玩家干预** | `intervention_used` | 某干预已使用 | `intervention_chaoyin_wake used` |
| **随机权重** | `weight` | 1-1000，越高越容易触发 | `500` |

### 2.2 条件组合规则

- **AND 逻辑**：所有列出的条件必须同时满足
- **OR 逻辑**：同一字段多值使用逗号分隔（如 `time_slot = "Morning,Afternoon"`）
- **NOT 逻辑**：条件前加 `!`（如 `!location = temple`）

---

## 3. 事件池管理表格

### 3.1 锚点事件表（Anchor Events）

| 事件 ID | 事件名称 | 周范围 | 天范围 | 时段 | 地点 | 参与 NPC | 风险 | 权重 | 关键条件 | 说明 |
|---------|----------|--------|--------|------|------|----------|------|------|----------|------|
| `w1d1_intro_town` | 归潮镇的清晨 | W1 | Day1 | Morning | plaza | | Low | 1000 | 游戏开局触发 | 开场叙事锚点 |
| `w1d3_temple_ritual` | 土地公诞辰 | W1 | Day3 | Night | temple | 全镇 | Medium | 1000 | 香火 >= 30 | 第一个关键仪式 |
| `w2d1_missing_person` | 失踪的渔夫 | W2 | Day1 | Morning | beach | 老汪, 阿海 | High | 1000 | | 邪教线开启锚点 |
| `w3d5_storm_warning` | 风暴预警 | W3 | Day5 | Any | beach | 全镇 | Fatal | 1000 | W3 之后自动 | 灾厄线前置 |
| `w4_final_crisis` | 大潮之夜 | W4 | Day7 | Night | beach | 全镇 | Fatal | 1000 | 强制触发 | 最终危机 |

### 3.2 关键事件表（Key Events）- 林潮音线

| 事件 ID | 事件名称 | 周范围 | 天范围 | 时段 | 地点 | 参与 NPC | 风险 | 权重 | 触发条件 | 关联业线 |
|---------|----------|--------|--------|------|------|----------|------|------|----------|----------|
| `w1_chaoyin_study` | 海边苦读的少女 | W1 | Any | Morning | beach | 潮音 | Low | 800 | 初次遇见 | 魔女线 +5 |
| `w1_chaoyin_dream` | 奇怪的梦境 | W1 | Any | Night | residence | 潮音 | Low | 600 | study 已触发 | 魔女线 +10 |
| `w2_chaoyin_bookshelf` | 旧书里的秘密 | W2 | Any | Afternoon | bookstore | 潮音, 芳华 | Medium | 700 | 缘线 >= 30 | 魔女线 +15 |
| `w2_chaoyin_confession` | 我不是怪物 | W2 | Any | Night | beach | 潮音, 芳华 | High | 750 | bookshelf 已触发 | 魔女线 +25 |
| `w3_chaoyin_power_awaken` | 力量觉醒 | W3 | Any | Night | mountain_forest | 潮音 | High | 900 | 魔女线 >= 50 | 魔女线 +30 |
| `w3_chaoyin_redemption` | 救赎的选择 | W3 | Any | Day | temple | 潮音, 土地公 | Medium | 850 | 阳德 >= 60 | 救赎线 +40 |

### 3.3 关键事件表（Key Events）- 陈芳华线

| 事件 ID | 事件名称 | 周范围 | 天范围 | 时段 | 地点 | 参与 NPC | 风险 | 权重 | 触发条件 | 关联业线 |
|---------|----------|--------|--------|------|------|----------|------|------|----------|----------|
| `w1_fanghua_clinic` | 新来的医生 | W1 | Day2-3 | Any | clinic | 芳华 | Low | 800 | | 医者线 +5 |
| `w1_fanghua_patient` | 深夜的病人 | W1 | Any | Night | clinic | 芳华, 神秘人 | Medium | 600 | clinic 已触发 | 医者线 +10 |
| `w2_fanghua_secret` | 不可告人的处方 | W2 | Any | Night | clinic | 芳华 | High | 700 | patient 已触发 | 暗黑线 +20 |
| `w2_fanghua_exposure` | 东窗事发 | W2 | Any | Day | plaza | 芳华, 警察 | High | 750 | secret 已触发 | 暗黑线 +30 |
| `w3_fanghua_choice` | 医者的抉择 | W3 | Any | Any | clinic | 芳华 | Fatal | 900 | 暗黑线 >= 50 | 结局分支点 |

### 3.4 日常事件表（Daily Events）

| 事件 ID | 事件名称 | 周范围 | 天范围 | 时段 | 地点 | 参与 NPC | 风险 | 权重 | 触发条件 |
|---------|----------|--------|--------|------|------|----------|------|------|----------|
| `daily_coffee_chat` | 咖啡店闲聊 | Any | Any | Afternoon | cafe | 任意 2 人 | Low | 200 | 两人缘线 >= 30 |
| `daily_beach_walk` | 海边散步 | Any | Any | Morning | beach | 任意 1 人 | Low | 150 | 幸福度 >= 50 |
| `daily_school_bully` | 校园霸凌 | Any | Any | Day | school | 学生 NPC | Medium | 300 | 阴德 >= 20 概率增加 |
| `daily_market_encounter` | 集市偶遇 | Any | Any | Morning | plaza | 任意 2 人 | Low | 250 | |
| `daily_temple_pray` | 神庙祈福 | Any | Any | Morning | temple | 任意 1 人 | Low | 300 | 自动 +2 香火 |
| `daily_police_patrol` | 警察巡逻 | W2-W4 | Any | Any | Any | 警察 | Low | 100 | 失踪事件后权重 *2 |
| `daily_fisherman_argument` | 渔民争吵 | Any | Any | Morning | port | 老汪, 阿海 | Medium | 350 | 两人缘线 < 0 |

---

## 4. 事件匹配算法

### 4.1 匹配流程

```
时段推进
    ↓
[ 收集候选事件 ]
    │  从池筛选满足 时间/地点/NPC在场 的所有事件
    ↓
[ 锚点事件优先 ]
    │  如有 weight >= 1000 的锚点事件 → 直接触发
    ↓
[ 条件过滤 ]
    │  逐一检查 关系/业线/NPC状态/资源/历史 条件
    │  移除不满足条件的事件
    ↓
[ 权重随机抽取 ]
    │  剩余事件按 weight 加权随机
    │  同一时段最多触发 1 个 Key + 1 个 Daily
    ↓
[ 执行事件 ]
    │  应用资源/缘线/业线/NPC状态变化
    │  记录事件历史
    └─ 排入后续事件链
```

### 4.2 权重计算公式

```
最终权重 = base_weight
         × location_match_factor        (地点完全匹配 ×1.5, 泛匹配 ×1.0)
         × bond_strength_factor         (缘线越高 ×1.0~1.5)
         × karma_progress_factor        (业线越接近 ×1.0~2.0)
         × recent_event_penalty         (同 NPC 3 时段内触发过 ×0.3)
         × risk_adjustment              (风险越高 ×0.5~1.2, 受玩家阴阳德影响)
```

### 4.3 冲突解决规则

1. **锚点优先**：锚点事件直接触发，忽略其他事件
2. **同优先级选高权重**：相同类型选 weight 大的
3. **NPC 参与限制**：同一 NPC 连续两个时段不重复触发
4. **地点热度限制**：同一地点连续触发事件权重 ×0.5

---

## 5. 事件 CSV 配置格式

### 5.1 events.csv（事件主表）

| 列名 | 类型 | 必填 | 示例 |
|------|------|------|------|
| `event_id` | String | ✅ | `w1_chaoyin_study` |
| `event_name` | String | ✅ | 海边苦读的少女 |
| `event_type` | Enum | ✅ | `Anchor` / `Key` / `Daily` |
| `week_range` | String | ✅ | `W1` |
| `day_range` | String | | `Day3-5` |
| `time_slot` | String | | `Morning` |
| `location` | String | | `beach` |
| `participants` | String[] | ✅ | `["lin_chaoyin"]` |
| `weight` | Int | ✅ | `800` |
| `risk_level` | Enum | ✅ | `Low` |
| `trigger_conditions` | String | | `bond_chaoyin_player >= 20` |
| `ai_text_policy` | Enum | ✅ | `None` / `DialogueAllowed` |
| `description` | String | ✅ | 潮音在海边读一本奇怪的书... |

### 5.2 event_outcomes.csv（事件结果表）

| 列名 | 类型 | 必填 | 示例 |
|------|------|------|------|
| `outcome_id` | String | ✅ | `out_w1_chaoyin_study_good` |
| `event_id` | String | ✅ | `w1_chaoyin_study` |
| `outcome_name` | String | ✅ | 暗中相助 |
| `trigger_condition` | String | ✅ | `default` / `intervention_applied` |
| `incense_delta` | Int | | `+5` |
| `divine_power_delta` | Int | | `-2` |
| `yin_de_delta` | Int | | `0` |
| `yang_de_delta` | Int | | `+10` |
| `bond_deltas` | String | | `bond_chaoyin_player:+15` |
| `karma_deltas` | String | | `chaoyin_witch:+5` |
| `npc_state_deltas` | String | | `lin_chaoyin:happiness:+10` |
| `follow_up_events` | String[] | | `["w1_chaoyin_dream"]` |
| `history_text` | String | ✅ | 你托梦给潮音一些启发... |

---

## 6. 事件历史与回溯

### 6.1 历史记录字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `event_id` | String | 触发的事件 ID |
| `trigger_day` | Int | 触发天数 1-28 |
| `trigger_slot` | String | `Morning` / `Afternoon` / `Night` |
| `location` | String | 触发地点 |
| `participants_at_time` | String[] | 触发时在场 NPC |
| `outcome_selected` | String | 选择的结局 ID |
| `intervention_used` | String | 玩家使用的干预（如有） |
| `matched_conditions` | String[] | 匹配成功的条件列表（Debug 用） |
| `trigger_weight` | Int | 触发时的最终权重（Debug 用） |

### 6.2 事件链追踪

每个事件记录：
- 前置事件（`follow_up_from`）
- 后续事件（`follow_up_to`）
- 干预影响（`intervention_altered_outcome`）

---

## 7. 开发与测试清单

### 7.1 实现阶段

| 阶段 | 任务 | 完成状态 |
|------|------|----------|
| Phase 1 | 事件 CSV 加载器 | ✅ 已有 event_loader.py |
| | 条件匹配引擎 | ✅ 已有 event_matcher.py |
| | 事件执行器 | ✅ 已有 event_executor.py |
| Phase 2 | 锚点事件强制触发逻辑 | ⏳ 待实现 |
| | 加权随机抽取 | ⏳ 待实现 |
| | NPC/地点热度惩罚 | ⏳ 待实现 |
| Phase 3 | 事件历史记录 | ⏳ 待实现 |
| | 事件链追踪 | ⏳ 待实现 |
| | 调试工具：匹配过程日志 | ⏳ 待实现 |

### 7.2 测试用例类型

| 测试类型 | 说明 |
|----------|------|
| 条件单元测试 | 单条件 true/false 验证 |
| 组合条件测试 | AND/OR/NOT 逻辑组合 |
| 锚点优先级测试 | 同条件下锚点必须优先 |
| 权重分布测试 | 10000 次随机抽取分布符合预期 |
| NPC 连续触发测试 | 同一 NPC 不应连续触发 |
| 完整周目测试 | 28 天完整运行事件覆盖率 >= 80% |

---

## 8. 配置维护规范

### 8.1 事件 ID 命名规范

```
{scope}_{npc}_{descriptor}

scope: w1/w2/w3/w4 = 指定周, daily = 日常, final = 终局
npc: 主要 NPC 标识, 多角色用下划线连接
descriptor: 事件描述, 动词+名词结构

示例:
  w1_chaoyin_study      = 第一周 潮音 学习事件
  w2_fanghua_secret     = 第二周 芳华 秘密事件
  daily_coffee_chat     = 日常 咖啡店 闲聊
```

### 8.2 权重设定指南

| 权重范围 | 使用场景 |
|----------|----------|
| >= 1000 | 锚点事件，必触发 |
| 800-999 | 关键事件主线，高概率 |
| 500-799 | 关键事件支线，中高概率 |
| 200-499 | 日常事件，中等概率 |
| < 200 | 稀有彩蛋事件 |

### 8.3 风险等级标准

| 风险等级 | 对玩家的影响 |
|----------|------------|
| Low | 纯叙事，无资源/属性损失 |
| Medium | 可能消耗神力或影响 NPC 心情 |
| High | 可能损失大量香火，或触发负面业线进展 |
| Fatal | 可能直接导致坏结局，需谨慎干预 |
