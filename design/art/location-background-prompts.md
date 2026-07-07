# 地点背景 Prompt 集

> 文档状态：初版
> 更新日期：2026-07-02
> 用途：为 11 个游戏内地点批量生成 1280×720 的像素风背景空镜（用于 `DialogueEventScreen.Background`）

---

## 0. 通用规格

| 项目 | 规格 |
|---|---|
| 输出尺寸 | 1280×720（16:9，匹配游戏视口） |
| 视角 | 水平（近似侧视 / 三分之二视角），非俯视 |
| 内容 | **无人物**、无 UI、无文字水印 |
| 风格 | 像素艺术（pixel art），有限调色板，颗粒清晰不模糊 |
| 层次 | 前景 / 中景 / 背景三层可辨；主体在中景 |
| 时段 | 每张按下表单选一个时段生成；后续可用色板叠色扩展昼夜 |
| 情绪 | 温暖日常 + 潮湿暗涌，避免过度写实和过强反差 |
| 分层参考 | 参见 `location-art-spec.md` §4 |

**通用负向 prompt**（追加到每条 prompt 尾部）：

```text
Avoid: 3D, photorealistic, blurry, anti-alias, gradient sky, complex background clutter,
people, characters, silhouettes of people, text, watermark, signature, UI overlay,
hyper-saturated colors, cropped subject, tilted horizon, top-down bird view
```

**通用正向前缀**（追加到每条 prompt 前面）：

```text
2D pixel art background, 16:9 landscape 1280x720, side view of an empty scene,
limited palette, clean pixel edges, distinct fore/mid/back layers, no characters,
soft ambient lighting, moody coastal town of Guichao (归潮镇)
```

---

## 1. 寺庙 (temple)

| 主色 | 情绪 | 时段 | 核心物件 | 风险暗示 |
|---|---|---|---|---|
| 暖橙 + 旧木棕 + 香灰灰 | 破旧但有人情味 | 清晨（薄雾未散） | 神龛、香炉、功德箱、旧红布 | 忽明忽暗的香火、裂开的梁 |

```text
Pixel art background of an old rural Chinese Tudi shrine on a hillside at early misty morning,
warm ochre wooden beams, weathered stone altar with brass incense burner emitting one thin
curl of pale smoke, faded red cloth banners hanging still, mossy tile roof with one cracked
beam, wooden merit box in front, worn stone steps in foreground, distant faint sea horizon
through mist in background, empty scene no people, cozy but slightly forlorn atmosphere
```

---

## 2. 学校 (school)

| 主色 | 情绪 | 时段 | 核心物件 | 风险暗示 |
|---|---|---|---|---|
| 淡蓝 + 米白 + 课桌木色 | 安静青春，压抑中带希望 | 上午（阳光斜射） | 黑板、课桌、窗外海光、考试倒计时 | 窗外淡淡潮水影子 |

```text
Pixel art background interior of an empty small-town classroom, morning sunlight slanting
through tall windows onto rows of wooden desks, chalk-dusted blackboard with faint
countdown numbers, cream-colored walls with light blue trim, one open notebook on a desk,
a hint of distant sea horizon visible through window with subtle wavy shadow pattern on the
floor, quiet studious atmosphere with faint underlying unease, empty scene no people
```

---

## 3. 咖啡店 (coffee_shop)

| 主色 | 情绪 | 时段 | 核心物件 | 风险暗示 |
|---|---|---|---|---|
| 奶茶棕 + 暖黄 + 浅绿 | 温暖缓冲区 | 午后 | 吧台、窗边座位、小黑板菜单、糖罐 | 窗外阴天暗示 |

```text
Pixel art background of a cozy small-town coffee shop interior in the afternoon,
milky brown wooden bar counter, warm yellow pendant lights, a chalkboard menu on the wall,
one window seat with soft green cushion, sugar jar and empty cup on table, potted plant
in corner, overcast diffuse light coming from tall window showing muted grey street outside,
warm safe atmosphere with a hint of coming rain, empty scene no people
```

---

## 4. 海鲜店 (seafood_shop)

| 主色 | 情绪 | 时段 | 核心物件 | 风险暗示 |
|---|---|---|---|---|
| 冷蓝 + 灰白 + 旧红招牌 | 潮湿、疲惫、家庭压力 | 傍晚 | 水桶、鱼箱、账本、卷帘门 | 摔碎的碗、过暗灯泡 |

```text
Pixel art background of a small dim seafood shop at dusk, cool bluish tones, wet concrete
floor reflecting a single dim bulb, wooden fish crates and blue plastic buckets stacked
along wall, half-rolled metal shutter door showing the darkening street outside, faded red
signboard above, a ledger book open on a worn counter, one chipped bowl on the ground,
faint smell suggested by wet marks, weary domestic atmosphere, empty scene no people
```

---

## 5. 诊所 (clinic)

| 主色 | 情绪 | 时段 | 核心物件 | 风险暗示 |
|---|---|---|---|---|
| 白 + 浅绿 + 冷灰 | 表面可信，细节不安 | 上午 | 药柜、病历、听诊器、帘子 | 锁住的药柜、过整齐的工具 |

```text
Pixel art background of a private small-town clinic examination room, white walls with
pale mint-green trim, wooden desk with neatly stacked patient files and a stethoscope,
tall glass-front medicine cabinet with a small padlock, half-drawn curtain separating an
exam bed area, cool morning light through blinds, everything too clean and too tidy,
sterile reassuring surface hiding quiet unease, empty scene no people
```

---

## 6. 广场 (plaza)

| 主色 | 情绪 | 时段 | 核心物件 | 风险暗示 |
|---|---|---|---|---|
| 石板灰 + 旗帜红 + 海风蓝 | 公共、舆论、集体选择 | 正午 | 告示栏、庙会旗、长椅、临时台子 | 新信仰标语 |

```text
Pixel art background of a small town central stone-tile plaza at midday, weathered grey
flagstones, a wooden notice board with multiple layered posters on one side, red temple
festival banners strung between two poles, one long wooden bench, a small empty raised
platform in center, distant low houses framing the square, blue sea sky above, one poster
partially torn revealing an odd symbol underneath, communal but slightly tense atmosphere,
empty scene no people
```

---

## 7. 沙滩 (beach)

| 主色 | 情绪 | 时段 | 核心物件 | 风险暗示 |
|---|---|---|---|---|
| 浅金沙 + 海蓝 + 日落橘 | 青春承诺 + 涨潮不祥 | 黄昏 | 潮痕线、木栈道、贝壳、灯塔远景 | 黑色潮痕、退潮暴露的旧祭物 |

```text
Pixel art background of a quiet northern island beach at sunset, pale golden sand, teal
sea meeting orange horizon, a weathered wooden boardwalk leading toward the water,
scattered white shells and one piece of driftwood in foreground, a small distant lighthouse
on a rocky outcrop, a subtle dark streak in the wet tideline hinting at something ominous
left behind by the receding tide, nostalgic and slightly foreboding atmosphere,
empty scene no people
```

---

## 8. 港口 (port)

| 主色 | 情绪 | 时段 | 核心物件 | 风险暗示 |
|---|---|---|---|---|
| 深蓝 + 铁锈红 + 雾灰 | 外来、秘密、离岛诱惑 | 深夜 | 渔船、码头灯、货箱、夜船剪影 | 未登记船只、黑色潮痕 |

```text
Pixel art background of an old fishing port at deep night, deep navy sea and sky, thick
low fog, one rust-red iron dock lamp casting a pool of dim yellow light onto wet wooden
planks, weathered fishing boats moored along the pier, stacked cargo crates in mid-ground,
the silhouette of an unmarked larger boat farther out on the water, faint dark stains on
the dock, mysterious and slightly menacing atmosphere, empty scene no people
```

---

## 9. 酒屋 (wine_bar)

| 主色 | 情绪 | 时段 | 核心物件 | 风险暗示 |
|---|---|---|---|---|
| 暗红 + 暖棕 + 烟灰 | 成人秘密、疲惫 | 深夜 | 酒柜、吧台、小桌、昏黄灯 | 角落低语、空杯 |

```text
Pixel art background of a small back-alley tavern interior at late night, dark red walls,
warm brown wooden bar counter with a row of amber bottles behind it, one lit paper lantern
casting warm dim light, low wooden tables and stools, one empty glass on a corner table,
smoke-tinted air, cozy and secretive atmosphere with old worn upholstery, adult melancholy
mood, empty scene no people
```

---

## 10. 派出所 (police_station)

| 主色 | 情绪 | 时段 | 核心物件 | 风险暗示 |
|---|---|---|---|---|
| 警蓝 + 灰白 + 旧木黄 | 沉稳克制、规程下的紧张 | 上午 | 办公桌、档案柜、通缉板、值班台历 | 未归档的案件、失踪者照片 |

```text
Pixel art background of a small two-room town police station interior, muted police blue
wall trim over grey-white walls, one wooden desk with a rotary phone and a stack of paper
files, an open case file lying half-open on the desktop, a metal filing cabinet against
one wall, a cork board with several small photos and pinned notes including one photo
tilted at the edge suggesting a missing person, a wall calendar with a date circled,
morning window light, quiet procedural atmosphere with subtle unease, empty scene no people
```

---

## 11. 山林 (mountain_forest)

| 主色 | 情绪 | 时段 | 核心物件 | 风险暗示 |
|---|---|---|---|---|
| 深绿 + 黑紫 + 雾灰 | 隐蔽、危险、民俗恐怖 | 深夜 | 树影、石阶、破旧供台、布条 | 异常聚集痕迹、纸符 |

```text
Pixel art background of a damp mountain forest path at deep night, thick dark green
foliage tinged with black-purple shadows, low ground mist creeping between mossy stone
steps that climb into the trees, an abandoned small stone offering altar half-swallowed
by vines in mid-ground, one pale ribbon of paper talisman fluttering unnaturally where
there is no wind, subtle burnt marks on the stones, folk-horror atmosphere, no visible
light source other than a cold sliver of moonlight, empty scene no people
```

---

## 12. 生成与落地

批量生成脚本：`tools/generate_backgrounds.py`（参考 `tools/generate_portraits.py`）

- 输入：本文件解析 `## N. 地点 (id)` 小节 → 抓取代码块中的 prompt
- 参数：`--location temple` 或 `--all`；`--force` 覆盖
- 输出：`godot/assets/backgrounds/{location_id}.jpg`（Seedream 返回 JPEG，同 `portraits_full`）
- 尺寸：Seedream 支持的最接近 16:9 的规格（例如 1536×864 或 1280×720，若不支持则用 1024×576 后放大）
- 生成后需在 Godot 打开一次以完成 `.import`

前端接入（后续故事）：

- `DialogueEventScreen` 增加 `BackgroundImage: TextureRect`（在 `Background` 之上，非 `ColorRect`）
- `scripts/ui/dialogue_event_screen.gd` 新增 `LOCATION_BG_TEXTURE = { "temple": preload(...), ... }`
- 优先加载 `assets/backgrounds/{location_id}.jpg`；缺失时回落到当前 `LOCATION_BG` 纯色

---

## 13. 验收标准

- [ ] 11 张背景在 1280×720 全屏下无明显模糊、噪点或伪影。
- [ ] 每张风格统一（像素颗粒、色彩饱和度、笔触密度一致）。
- [ ] 无任何人物、UI、文字、水印。
- [ ] 三层（前中背）结构可辨。
- [ ] 危险地点（山林 / 港口 / 酒屋）氛围明显不同于日常地点（学校 / 咖啡店 / 广场）。
- [ ] 沙滩 / 港口 / 山林 的"风险暗示"物件可辨识但不喧宾夺主。
