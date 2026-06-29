# 时间系统设计决策记录

> 模块路径：`src/backend/engine/time/`  
> 创建日期：2026-06-25  
> 状态：设计定稿，待实现

---

## 目录

1. [已解决的设计问题](#1-已解决的设计问题)
2. [数据模型](#2-数据模型)
3. [推进算法](#3-推进算法)
4. [周阶段配置](#4-周阶段配置)
5. [边界条件](#5-边界条件)
6. [待讨论问题](#6-待讨论问题)

---

## 1. 已解决的设计问题

### D1: 时间推进的原子单位

**结论**: **时段级推进**（不是天级）

**理由**:
- 策划案明确写了 "180 次决策窗口上限"（60天 × 3时段）
- 不同时段有不同的技能约束（托梦只能夜晚执行）
- NPC 在不同时段出现在不同地点，时段级才有策略深度
- 周结算是自动的（每 21 个时段触发一次）

### D2: 时间模块的职责边界

**结论**: **纯计时器**（不是编排器）

**理由**:
- 单一职责：时间系统只管"现在是什么时候"
- 可独立测试，不依赖其他模块
- 与架构文档中 `engine/time/` 和其他子模块平级的设计一致
- 上层编排器（未来 `GameSession`）决定结算顺序

### D3: 周的计算方式

**结论**: **纯派生**，`week = ceil(day / 7)`，不存储

**理由**:
- 减少状态冗余，单一真相源
- 60 天 ÷ 7 = 9 周（最后一周 day 57-60，只有 4 天）
- 周阶段表（§13.4）实际上就是按 7 天一周排列

### D4: 周结算触发时机

**结论**: day 7/14/21/28/35/42/49/56 的 NIGHT 结算后触发

由上层编排器通过检查 `TimeAdvanceResult.is_new_week` 来决定是否执行周结算。

### D5: 时段映射

**结论**: 沿用现有 `Slot` 枚举（`MORNING → NOON → NIGHT → 次日 MORNING`），不做修改

### D6: TimeState 的可变性

**结论**: **可变状态**（不是不可变值对象）

**理由**:
- 游戏是单线推进，不需要分支/回滚
- 与 `AgentManager` 的内存管理模式一致
- 存档时直接序列化当前状态即可

### D7: TimeState 的独立性

**结论**: **独立模型**，不和 `GameStateResponse` 合并

**理由**:
- `engine/time/` 是纯逻辑，不依赖 `models/` 或 `server/`
- `advance()` 返回 `TimeAdvanceResult`，上层编排器决定如何消费
- 符合单一职责

### D10: TimeState 的 API 风格

**结论**: **实例方法**（`state.advance()`），而非模块级函数

**理由**:
- `TimeState` 是可变对象，`state.advance()` 更自然地表达"状态自身在演进"
- 保留了底层实现为实例方法的灵活性
- 对外也在模块级重导出 `advance(state)` 别名，兼容函数式调用风格

### D8: 阶段名配置方式

**结论**: **当前硬编码**，预留未来迁移到 CSV

**理由**:
- `data/` 模块尚未实现
- 9 个阶段是固定数据，硬编码不会在短期内造成维护负担
- `WeekPhase` dataclass 结构设计为未来 CSV 迁移预留了字段映射

### D11: 公共 API 面

**结论**: TimeState 暴露以下方法：

| 方法 | 类型 | 用途 |
|------|------|------|
| `state.advance()` | 实例方法 | 推进一个时段，修改自身，返回 `TimeAdvanceResult` |
| `state.can_advance()` | 实例方法 | 返回 `bool`，day=60+NIGHT 时返回 False |
| `state.peek()` | 实例方法 | 返回推进后的 `TimeAdvanceResult`，不修改自身。封装了 `is_new_week` 计算逻辑 |
| `state.to_dict()` | 实例方法 | 序列化，存档用 |
| `TimeState.from_dict(d)` | 类方法 | 反序列化，读档用 |
| `get_phase(week)` | 模块函数 | 根据周数查 `WeekPhase` |

### D9: 终局边界行为

**结论**: `advance()` 在 day=60, slot=NIGHT 时抛出 `GameTimeExceededError`

**设计细节**:
- 提供 `can_advance(state)` 方法供外部编排器提前检查
- 编排器应在 day=60 NIGHT 跳过 advance() 直接执行终局判定
- 异常是防御性安全网，不是主控制流

---

### D12: 序列化格式

**结论**: 只存 `day` 和 `slot`，其余全部派生

```python
# to_dict() → {"day": 15, "slot": "night"}
# from_dict({"day": 15, "slot": "night"}) → TimeState(day=15, slot=Slot.NIGHT)
```

- `from_dict()` 校验 day∈[1,60] 和 slot 合法性，不合法抛 `ValueError`
- `week` 和 `phase_name` 不存储，避免数据不一致

---

## 2. 数据模型

### TimeState（时间状态）

```python
@dataclass
class TimeState:
    day: int = 1                      # 1–60
    slot: Slot = Slot.MORNING         # 早晨/正午/夜晚
    # week 和 phase_name 均为派生属性
```

### TimeAdvanceResult（推进结果）

```python
@dataclass
class TimeAdvanceResult:
    slot: Slot          # 推进后时段
    day: int            # 推进后天数
    week: int           # 推进后周数（派生）
    is_new_day: bool    # NIGHT→MORNING
    is_new_week: bool   # day 变为 8/15/22/29/36/43/50/57
    phase_name: str     # 当前周阶段中文名
```

### WeekPhase（周阶段）

```python
@dataclass(frozen=True)
class WeekPhase:
    week: int           # 1–9
    day_range: str      # "1-7", "8-14", ...
    name: str           # 中文阶段名
    theme: str          # 气氛描述，可用于 LLM prompt 注入
```

### GameTimeExceededError（时间超出异常）

```python
class GameTimeExceededError(Exception):
    """已超出 60 天游戏周期，无法继续推进时间"""
    pass
```

---

## 3. 推进算法

```
advance(state: TimeState) → TimeAdvanceResult

1. 终局检查: if day >= 60 AND slot == NIGHT → raise GameTimeExceededError
2. 时段推进:
   - MORNING → NOON    (is_new_day = False)
   - NOON   → NIGHT    (is_new_day = False)
   - NIGHT  → MORNING  (is_new_day = True, day += 1)
3. 跨天检查: if day 变为 8/15/22/29/36/43/50/57 → is_new_week = True
4. 查表获取 phase_name
5. 返回 TimeAdvanceResult
```

---

## 4. 周阶段配置

策划案 §13.4 定义的 9 个周阶段：

| Week | Day Range | 阶段名 | 气氛 |
|------|-----------|--------|------|
| 1 | 1–7 | 旧神将熄 | 建立土地公绩效压力，介绍小镇和主要人物 |
| 2 | 8–14 | 外来者入潮 | 邪教核心人物入场，外来力量开始渗透 |
| 3 | 15–21 | 异常初显 | 巫女线、港口线索和第一起案件出现 |
| 4 | 22–28 | 命运交错 | 三条主线开始交织 |
| 5 | 29–35 | 潮声入梦 | 第60天天灾被明确化，邪教秘密聚会成型 |
| 6 | 36–42 | 信仰裂缝 | 寺庙、家庭、警局、邪教四线压力集中 |
| 7 | 43–49 | 庙会争夺 | 庙会 vs 邪教集会进入公开争夺 |
| 8 | 50–56 | 终局锁定 | 聚集地点、证据链、火灾风险、巫女状态定型 |
| 9 | 57–60 | 潮落见神 | 最后选择与天灾结算 |

---

## 5. 边界条件

### 正常推进

```
MORNING → NOON:   正常，is_new_day=False
NOON → NIGHT:     正常，is_new_day=False
NIGHT → MORNING:  正常，is_new_day=True, day+=1
```

### 跨周检测

仅在 `is_new_day=True` 时检测。跨周发生在 day 变为 8, 15, 22, 29, 36, 43, 50, 57 时。

公式：`(day - 1) % 7 == 0`

### 终局

```
day=60, slot=NIGHT + advance() → GameTimeExceededError
```

编排器应使用 `can_advance(state)` 提前检查。

### 游戏开始

初始状态：`TimeState(day=1, slot=Slot.MORNING)`

开局叙事（天界绩效通知、邪神低语）发生在 day=1 MORNING，由上层编排器负责，非时间模块职责。

---

## 6. 实施计划

### 6.1 文件清单

| 文件 | 内容 |
|------|------|
| `engine/__init__.py` | 空文件（包标记） |
| `engine/time/__init__.py` | 公开导出：`TimeState`、`TimeAdvanceResult`、`GameTimeExceededError`、`WeekPhase`、`get_phase`、`PHASES` |
| `engine/time/time_state.py` | `TimeState` + `TimeAdvanceResult` + `GameTimeExceededError` |
| `engine/time/week_phases.py` | `WeekPhase` + `PHASES` 常量 + `get_phase()` |
| `tests/test_time.py` | 单元测试（约 20 个用例） |

### 6.2 公开 API

```
state.advance()       → TimeAdvanceResult   # 推进一个时段，修改自身
state.can_advance()   → bool                 # 终局前检查
state.peek()          → TimeAdvanceResult    # 预览推进结果，不修改自身
state.to_dict()       → dict                 # 序列化
TimeState.from_dict(d) → TimeState           # 反序列化
get_phase(week)       → WeekPhase            # 查周阶段表
```

### 6.3 测试覆盖

| 类别 | 用例 |
|------|------|
| 正常推进 | 早晨→正午、正午→夜晚、夜晚→次日早晨 |
| 跨天 | 天数递增、跨天标记为真 |
| 跨周 | 第7天→第8天触发跨周 |
| 终局边界 | day=60 + NIGHT 抛异常、能否推进返回 False |
| 序列化 | 转为字典/从字典加载 往返 |
| 预览 | 不修改原状态 |
| 终局周 | 第9周覆盖 day 57-60 |
| 阶段名 | 全部9个周阶段查表验证 |

---

## 7. 待讨论问题

_当前无。所有已识别问题已在设计阶段解决。_
