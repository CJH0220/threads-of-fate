# data 数据目录

> 文档状态：整理版  
> 更新日期：2026-06-12  
> 用途：可配置数据、表格和导出给研发使用的数据文件

---

## 1. 目录职责

`data/` 用于承接 `system/` 和 `content/` 的策划结果，把规则、事件、NPC、资源、地点等内容整理成可导入、可测试、可版本管理的数据表。

本目录面向：

- 程序实现
- 内容配置
- 自动化检查
- 数值调试
- 后续导出 CSV / JSON / Godot Resource

---

## 2. 当前数据文件

| 文件 | 用途 | 状态 |
|---|---|---|
| `事件配置表.csv` | 事件池草案，包含锚点事件、关键事件、日常事件和终局事件 | P0 草案 |
| `NPC基础表.csv` | NPC ID、姓名、职业、初始地点、剧情优先级和 MVP 优先级 | P0 草案 |
| `地点配置表.csv` | 地点 ID、可访问时段、核心 NPC、功能和视觉优先级 | P0 草案 |
| `资源数值表.csv` | 香火、神力、阳德、阴德及扩展镇域状态资源 | P0 草案 |
| `干预技能表.csv` | 托梦、赐福、牵引机缘、遮蔽灾兆、显灵警示等技能配置 | P0 草案 |
| `结局判定表.csv` | Game Over、正神、邪神、中性、传奇路线判定条件 | P0 草案 |
| `缘线初始关系表.csv` | NPC 初始关系、关系类型、强度和可见性 | P1 草案 |
| `业线节点表.csv` | 关键 NPC 业线节点、条件、成功 / 失败倾向 | P1 草案 |
| `事件结果表.csv` | 事件选项、干预修正、资源变化、NPC 状态变化 | P1 草案 |
| `本地化文本表.csv` | UI、系统提示、事件摘要和结局文本 key | P1 草案 |
| `周阶段参数表.csv` | 每周事件节奏、压力参数和主角色 / 地点 | P1 草案 |

---

## 3. 推荐维护方式

建议源表使用 Excel / Google Sheets / LibreOffice 维护，再导出为 CSV。

导出规则：

- UTF-8 编码
- 第一行为字段名
- 不合并单元格
- 不使用中文逗号作为字段分隔符
- 多个 ID 使用英文分号 `;` 分隔
- 同一列保持同一种数据类型
- 玩家可见中文名称和内部 ID 分列存放

---

## 4. 通用 ID 命名规则

| 类型 | 命名规则 | 示例 |
|---|---|---|
| EventId | 小写 snake_case | `w3_witch_candidate` |
| LocationId | 小写 snake_case | `temple`, `coffee_shop` |
| NpcId | 小写 snake_case | `lin_chaoyin`, `chen_yuanzhou` |
| WeekRange | `W1`-`W8` 或 `Final` | `W5` |
| DayRange | `DayX` 或 `DayX-Y` | `Day29-35` |
| TimeSlot | 英文枚举 | `Morning`, `Noon`, `Afternoon`, `Night`, `Any` |

---

## 5. 事件配置表字段说明

| 字段 | 说明 |
|---|---|
| `EventId` | 事件唯一 ID |
| `EventName` | 策划和 UI 可读事件名 |
| `EventType` | `Anchor` / `Key` / `Daily` / `Major` / `Sudden` |
| `WeekRange` | 所属周阶段 |
| `DayRange` | 触发天数或天数范围 |
| `TimeSlot` | 触发时段 |
| `LocationId` | 地点 ID |
| `ParticipantNpcIds` | 参与 NPC ID，多个用 `;` 分隔 |
| `RiskLevel` | `Low` / `Medium` / `High` / `Fatal` |
| `TriggerWeight` | 触发权重，锚点事件建议 `1000`，普通事件使用较小数字 |
| `AiTextPolicy` | `None` / `DialogueAllowed` / `DescriptionOnly` |
| `HistoryRecordPolicy` | `None` / `Summary` / `Full` |
| `Description` | 策划说明，不直接等同最终游戏文本 |

---

## 6. 建议后续补齐的数据表

当前研发前置数据表已补齐。后续进入内容扩量阶段时，可继续追加：

| 优先级 | 建议文件 | 用途 |
|---|---|---|
| P2 | `支线事件扩展表.csv` | 扩展低优先级日常事件和角色支线 |
| P2 | `地点状态表.csv` | 细化地点安全、开放、破坏和修复状态 |
| P2 | `结局后日谈片段表.csv` | 扩展角色结局和路线后日谈模板 |

---

## 7. 当前一致性基准

数据表应统一使用：

- `lin_chaoyin`：林潮音
- `chen_yuanzhou`：陈远舟
- `gu_chenzhou`：顾沉舟
- `jiang_xueyi`：江雪仪
- `xu_mingchuan`：许明川
- `chen_haisheng`：陈海生
- `xu_qing`：许晴
- `zhou_xingzhi`：周行知
- `huiyuan`：慧圆
- `su_wan`：苏婉
- `ye_keke`：叶可可
- `lin_yueqin`：林月琴
- `he_laosan`：何老三
- `zhao_shouzheng`：赵守正

如果内容文档改名，数据表必须同步更新。
