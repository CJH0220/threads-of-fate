# 美术资产需求清单

> 文档状态：初版  
> 更新日期：2026-06-12  
> 用途：记录《命运的织线》MVP 与后续阶段所需美术资产

---

## 1. 优先级定义

| 优先级 | 说明 |
|---|---|
| P0 | MVP 必须，缺失会阻塞首个可玩版本 |
| P1 | 完整体验需要，但不阻塞 MVP |
| P2 | 表现增强、氛围增强或后续扩展 |

---

## 2. 命名规范

建议资产命名使用英文 snake_case：

```text
类型_对象_状态_尺寸
```

示例：

```text
ui_icon_incense_32.png
ui_button_wood_default.png
portrait_lin_chaoyin_default_96.png
loc_temple_icon_128.png
bg_map_guichao_town_day.png
fx_incense_smoke_loop.png
```

---

## 3. MVP P0 资产

### 3.1 UI 基础组件

| AssetId | 中文名 | 用途 | 建议规格 | 优先级 | 状态 |
|---|---|---|---|---|---|
| `ui_panel_parchment` | 纸张面板 | 通用面板底 | 9-slice PNG | P0 | 待制作 |
| `ui_panel_wood` | 木质面板 | 主菜单 / HUD 边框 | 9-slice PNG | P0 | 待制作 |
| `ui_button_wood_default` | 木质按钮默认 | 通用按钮 | 9-slice PNG | P0 | 待制作 |
| `ui_button_wood_focus` | 木质按钮焦点 | 键盘 / Hover 状态 | 9-slice PNG | P0 | 待制作 |
| `ui_button_wood_pressed` | 木质按钮按下 | 点击反馈 | 9-slice PNG | P0 | 待制作 |
| `ui_button_wood_disabled` | 木质按钮禁用 | 不可用状态 | 9-slice PNG | P0 | 待制作 |
| `ui_frame_warning` | 警告边框 | 危险确认 / 高风险事件 | 9-slice PNG | P0 | 待制作 |
| `ui_focus_outline` | 焦点描边 | 键盘导航焦点 | 9-slice PNG | P0 | 待制作 |

### 3.2 UI 图标

| AssetId | 中文名 | 用途 | 建议规格 | 优先级 | 状态 |
|---|---|---|---|---|---|
| `ui_icon_incense` | 香火图标 | 资源栏 | 32×32 PNG | P0 | 待制作 |
| `ui_icon_divine_power` | 神力图标 | 资源栏 | 32×32 PNG | P0 | 待制作 |
| `ui_icon_yang_de` | 阳德图标 | 资源栏 | 32×32 PNG | P0 | 待制作 |
| `ui_icon_yin_de` | 阴德图标 | 资源栏 | 32×32 PNG | P0 | 待制作 |
| `ui_icon_warning` | 危险警告 | 高风险事件 | 32×32 PNG | P0 | 待制作 |
| `ui_icon_event` | 事件标记 | 地图事件热点 | 32×32 PNG | P0 | 待制作 |
| `ui_icon_time` | 时间图标 | 时间栏 | 32×32 PNG | P0 | 待制作 |
| `ui_icon_save` | 保存图标 | 存档反馈 | 32×32 PNG | P0 | 待制作 |

### 3.3 主地图与地点

| AssetId | 中文名 | 用途 | 建议规格 | 优先级 | 状态 |
|---|---|---|---|---|---|
| `bg_map_guichao_town_day` | 归潮镇主地图 | 主地图 HUD 背景 | 1280×720 或 960×540 PNG | P0 | 待制作 |
| `loc_temple_icon` | 寺庙地点图标 | 地图地点按钮 | 128×128 PNG | P0 | 待制作 |
| `loc_school_icon` | 学校地点图标 | 地图地点按钮 | 128×128 PNG | P0 | 待制作 |
| `loc_port_icon` | 港口地点图标 | 地图地点按钮 | 128×128 PNG | P0 | 待制作 |
| `loc_clinic_icon` | 诊所地点图标 | 地图地点按钮 | 128×128 PNG | P0 | 待制作 |
| `loc_coffee_shop_icon` | 咖啡店地点图标 | 地图地点按钮 | 128×128 PNG | P0 | 待制作 |
| `loc_seafood_shop_icon` | 海鲜店地点图标 | 地图地点按钮 | 128×128 PNG | P0 | 待制作 |

### 3.4 MVP NPC 头像

| AssetId | 中文名 | 用途 | 建议规格 | 优先级 | 状态 |
|---|---|---|---|---|---|
| `portrait_lin_chaoyin_default` | 林潮音默认头像 | 人物 / 事件面板 | 96×96 PNG | P0 | 待制作 |
| `portrait_chen_yuanzhou_default` | 陈远舟默认头像 | 人物 / 事件面板 | 96×96 PNG | P0 | 待制作 |
| `portrait_chen_haisheng_default` | 陈海生默认头像 | 人物 / 事件面板 | 96×96 PNG | P0 | 待制作 |
| `portrait_gu_chenzhou_default` | 顾沉舟默认头像 | 事件 / 邪教线 | 96×96 PNG | P0 | 待制作 |
| `portrait_huiyuan_default` | 慧圆默认头像 | 寺庙 / 巫女线 | 96×96 PNG | P0 | 待制作 |

### 3.5 事件与结算插图

| AssetId | 中文名 | 用途 | 建议规格 | 优先级 | 状态 |
|---|---|---|---|---|---|
| `event_scene_temple_warning` | 寺庙异常插图 | 事件面板 | 320×180 PNG | P0 | 待制作 |
| `event_scene_school_daily` | 学校日常插图 | 事件面板 | 320×180 PNG | P0 | 待制作 |
| `event_scene_port_night` | 港口夜晚插图 | 事件面板 | 320×180 PNG | P0 | 待制作 |
| `event_scene_home_conflict` | 家庭冲突插图 | 事件面板 | 320×180 PNG | P0 | 待制作 |
| `summary_bg_week` | 周总结背景 | 周结算界面 | 640×360 PNG | P0 | 待制作 |

### 3.6 基础特效

| AssetId | 中文名 | 用途 | 建议规格 | 优先级 | 状态 |
|---|---|---|---|---|---|
| `fx_incense_smoke_loop` | 香火烟雾 | 寺庙 / 香火状态 | PNG 序列 | P0 | 待制作 |
| `fx_fate_line_pulse` | 命运线闪烁 | 缘线 / 业线变化 | PNG 序列或 shader | P0 | 待制作 |
| `fx_warning_blink` | 警告闪烁 | 危险事件 | PNG 序列 | P0 | 待制作 |

---

## 4. P1 资产

### 4.1 扩展 NPC 头像

| AssetId | 中文名 | 用途 | 建议规格 | 优先级 | 状态 |
|---|---|---|---|---|---|
| `portrait_jiang_xueyi_default` | 江雪仪默认头像 | 诊所 / 邪教线 | 96×96 PNG | P1 | 待制作 |
| `portrait_xu_mingchuan_default` | 许明川默认头像 | 侦探线 | 96×96 PNG | P1 | 待制作 |
| `portrait_xu_qing_default` | 许晴默认头像 | 校园 / 医疗线 | 96×96 PNG | P1 | 待制作 |
| `portrait_zhou_xingzhi_default` | 周行知默认头像 | 调查 / 记者线 | 96×96 PNG | P1 | 待制作 |
| `portrait_su_wan_default` | 苏婉默认头像 | 家庭线 | 96×96 PNG | P1 | 待制作 |
| `portrait_ye_keke_default` | 叶可可默认头像 | 咖啡店日常 | 96×96 PNG | P1 | 待制作 |
| `portrait_lin_yueqin_default` | 林月琴默认头像 | 母女 / 酒屋线 | 96×96 PNG | P1 | 待制作 |
| `portrait_he_laosan_default` | 何老三默认头像 | 港口线 | 96×96 PNG | P1 | 待制作 |
| `portrait_zhao_shouzheng_default` | 赵守正默认头像 | 警察线 | 96×96 PNG | P1 | 待制作 |

### 4.2 扩展地点

| AssetId | 中文名 | 用途 | 建议规格 | 优先级 | 状态 |
|---|---|---|---|---|---|
| `loc_wine_bar_icon` | 酒屋图标 | 地点按钮 | 128×128 PNG | P1 | 待制作 |
| `loc_plaza_icon` | 广场图标 | 地点按钮 | 128×128 PNG | P1 | 待制作 |
| `loc_police_station_icon` | 派出所图标 | 地点按钮 | 128×128 PNG | P1 | 待制作 |
| `loc_mountain_forest_icon` | 山林图标 | 地点按钮 | 128×128 PNG | P1 | 待制作 |

### 4.3 氛围与路线表现

| AssetId | 中文名 | 用途 | 建议规格 | 优先级 | 状态 |
|---|---|---|---|---|---|
| `overlay_sea_fog` | 海雾遮罩 | 天灾预兆 | 1280×720 PNG | P1 | 待制作 |
| `overlay_cult_shadow` | 邪教阴影遮罩 | 邪路氛围 | 1280×720 PNG | P1 | 待制作 |
| `fx_blessing_gold` | 金色赐福光点 | 正向干预反馈 | PNG 序列 | P1 | 待制作 |
| `fx_yin_de_shadow` | 阴德阴影扩散 | 阴德反馈 | PNG 序列 | P1 | 待制作 |
| `ending_bg_good` | 正神结局背景 | 结局界面 | 1280×720 PNG | P1 | 待制作 |
| `ending_bg_bad` | 邪神结局背景 | 结局界面 | 1280×720 PNG | P1 | 待制作 |

---

## 5. P2 资产

| AssetId | 中文名 | 用途 | 建议规格 | 优先级 | 状态 |
|---|---|---|---|---|---|
| `portrait_expression_set` | NPC 表情差分 | 情绪演出 | 96×96 PNG 组 | P2 | 待制作 |
| `map_time_variants` | 主地图时段差分 | 早 / 午 / 晚氛围 | 1280×720 PNG 组 | P2 | 待制作 |
| `ending_gallery_frames` | 结局回顾边框 | 结局回顾 | 9-slice PNG | P2 | 待制作 |
| `fx_large_fate_weave` | 大型命运线特效 | 高级演出 | PNG 序列 / shader | P2 | 待制作 |
| `cutscene_panels_final` | 终局演出插图 | 结局演出 | 多张 16:9 PNG | P2 | 待制作 |

---

## 6. 资产验收标准

- [ ] 文件名符合命名规范。
- [ ] PNG 使用透明背景，除非是背景图。
- [ ] 像素边缘清晰，不因缩放模糊。
- [ ] 图标在 32×32 下仍可识别。
- [ ] 头像在 96×96 下能区分角色。
- [ ] 危险、资源、状态图标不能只靠颜色表达。
- [ ] UI 组件有 default / focus / pressed / disabled 状态。
- [ ] P0 资产能支撑首个可玩竖切。

---

## 7. 首个竖切最小资产包

若只做最小可玩版本，优先制作：

```text
ui_panel_parchment
ui_panel_wood
ui_button_wood_default / focus / pressed / disabled
ui_icon_incense
ui_icon_divine_power
ui_icon_yang_de
ui_icon_yin_de
ui_icon_warning
ui_icon_event
bg_map_guichao_town_day
loc_temple_icon
loc_school_icon
loc_port_icon
loc_coffee_shop_icon
portrait_lin_chaoyin_default
portrait_chen_yuanzhou_default
portrait_chen_haisheng_default
event_scene_temple_warning
event_scene_school_daily
fx_incense_smoke_loop
fx_warning_blink
```
