# 《命运的织线》事件库说明

## 事件统计

| 类别 | 数量 | 说明 |
|------|------|------|
| **锚点事件 (Anchor)** | 15 个 | 必触发，权重 1000，核心剧情节点 |
| **关键事件 (Key)** | 72 个 | 高权重，NPC 个人业线节点 |
| **日常事件 (Daily)** | 22 个 | 填充剧情，营造真实感 |
| **事件总数** | **109 个** | |

| 结果表 | 数量 |
|--------|------|
| 事件结果分支 | 52 个 |

## NPC 事件覆盖

| NPC | 关联事件数 | 核心业线 | S/A 级 |
|-----|-----------|----------|--------|
| 林潮音 | 16 | Witch Line | S |
| 陈远舟 | 14 | Leave Line | S |
| 陈海生 | 14 | Cult Line | S |
| 顾沉舟 | 12 | Cult Leader | S |
| 慧圆 | 10 | Temple Line | A |
| 江雪仪 | 12 | Medical Cult | S |
| 许明川 | 12 | Detective Line | S |
| 周行知 | 10 | Journalist Line | A |
| 许晴 | 5 | Support | A |
| 苏婉 | 6 | Family Line | A |
| 叶可可 | 5 | Info Hub | A |
| 林月琴 | 6 | Mother Line | A |
| 何老三 | 7 | Port Witness | B |
| 赵守正 | 5 | Order Anchor | B |

## 时间线分布

| 周次 | 锚点事件 | 关键事件 | 日常事件 | 小计 |
|------|---------|---------|---------|------|
| W1 | 3 | 8 | 7 | 18 |
| W2 | 4 | 12 | 5 | 21 |
| W3 | 5 | 14 | 3 | 22 |
| W4 | 2 | 12 | 2 | 16 |
| W5 | 3 | 10 | 2 | 15 |
| W6 | 3 | 10 | 1 | 14 |
| W7 | 3 | 6 | 0 | 9 |
| W8/Final | 2 | 0 | 0 | 2 |

## 事件结构说明

### 触发条件层级

1. **时间条件**：WeekRange, DayRange, TimeSlot
2. **空间条件**：LocationId
3. **人物在场**：ParticipantNpcIds
4. **关系条件**：Bond 阈值
5. **业线条件**：Karma 节点进度
6. **前置事件**：Previous Event 触发记录
7. **随机权重**：TriggerWeight（锚点 1000 = 必触发）

### AI 文本策略 (AiTextPolicy)

| 策略 | 适用场景 | 说明 |
|------|---------|------|
| `None` | 锚点事件、纯系统事件 | 不调用 LLM，使用预设文本 |
| `DialogueAllowed` | NPC 互动事件 | 可以生成 NPC 对话 |
| `FullNarration` | 重要剧情节点 | 完整 LLM 叙事生成 |

### 历史记录策略 (HistoryRecordPolicy)

| 策略 | 说明 |
|------|------|
| `Full` | 完整记录事件描述、所有变量变化 |
| `Summary` | 仅记录摘要和关键数值变化 |
| `Minimum` | 仅记录事件 ID 和触发时间 |
| `None` | 不记录 |

## CSV 字段说明

### events_complete.csv

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `EventId` | String | ✓ | 唯一标识，命名规范：`{week}_{npc}_{descriptor}` |
| `EventName` | String | ✓ | 中文事件名称 |
| `EventType` | Enum | ✓ | `Anchor` / `Key` / `Daily` |
| `WeekRange` | String | ✓ | `W1` / `W2-W4` / `Final` / `Any` |
| `DayRange` | String | | `Day1` / `Day3-5` / 空 = 任意 |
| `TimeSlot` | String | | `Morning` / `Afternoon` / `Night` / `Any` |
| `LocationId` | String | ✓ | 地点 ID |
| `ParticipantNpcIds` | String[] | ✓ | 参与 NPC ID 列表，逗号分隔 |
| `RiskLevel` | Enum | ✓ | `Low` / `Medium` / `High` / `Fatal` |
| `TriggerWeight` | Int | ✓ | 1-1000，>=1000 为必触发 |
| `AiTextPolicy` | Enum | ✓ | `None` / `DialogueAllowed` / `FullNarration` |
| `HistoryRecordPolicy` | Enum | ✓ | `Full` / `Summary` / `Minimum` / `None` |
| `RequiredConditions` | String | | 复合条件表达式，如 `bond_a_b>=50;prev_event_id` |
| `Description` | String | ✓ | 事件描述文本 |

### event_outcomes_complete.csv

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `OutcomeId` | String | ✓ | 结果唯一标识 |
| `EventId` | String | ✓ | 关联事件 ID |
| `OutcomeName` | String | ✓ | 中文结果名称 |
| `TriggerCondition` | String | ✓ | `default` / `intervention_used` / 条件表达式 |
| `IncenseDelta` | Int | | 香火变化值 |
| `DivinePowerDelta` | Int | | 神力变化值 |
| `YinDeDelta` | Int | | 阴德变化值 |
| `YangDeDelta` | Int | | 阳德变化值 |
| `BondDeltas` | String | | 缘线变化，如 `bond_a_b:+20;bond_c_d:-10` |
| `KarmaDeltas` | String | | 业线变化，如 `line_a:+15;line_b:-5` |
| `NpcStateDeltas` | String | | NPC 状态变化，如 `a:happiness:+10;b:stress:+5` |
| `FollowUpEvents` | String[] | | 后续事件 ID 列表 |
| `HistoryText` | String | ✓ | 历史记录显示文本 |

## 事件间关系示例

### 林潮音 Witch Line 链条
```
w1_chaoyin_nightmare1
    → w1_chaoyin_nightmare2
        → w2_chaoyin_bookshelf_find
            → w3_chaoyin_awakening
                → w3_witch_candidate (锚点)
                    → w4_chaoyin_witch_decision
                        → w5_chaoyin_power_manifest
                            → w7_chaoyin_guardian_choice
```

### 陈海生 Cult Line 链条
```
w1_chenhai_debt1
    → w2_chenhai_gus_first_offer
        → w3_gus_contact_chenhai (锚点)
            → w4_chenhai_first_gathering
                → w5_chenhai_first_sacrifice
                    → w6_chenhai_critical_point
                        → w7_chenhai_final_stand
```

### 顾沉舟 Cult Leader Line 链条
```
w2_gus_cult_arrive (锚点)
    → w3_gus_contact_chenhai (锚点)
        → w4_gus_secret_meeting (锚点)
            → w5_gus_sacrifice_failure
                → w6_gus_public_gathering (锚点)
                    → w7_gus_new_faith_announce
```

## 风险等级分布

| 风险等级 | 数量 | 比例 |
|---------|------|------|
| Low | 55 | 50% |
| Medium | 31 | 28% |
| High | 19 | 17% |
| Fatal | 4 | 4% |
| **合计** | **109** | 100% |

## 下一步工作

1. [ ] 将事件表导入后端 EventSystem
2. [ ] 补全所有日常事件的干预选项和结果分支
3. [ ] 编写条件匹配引擎规则
4. [ ] 编写事件链测试用例
5. [ ] 调整权重平衡，确保事件分布合理
