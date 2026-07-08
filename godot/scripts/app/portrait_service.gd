extends Node

## 头像服务（Autoload：PortraitService）。
## 统一 npc_id → 头像纹理映射与缓存，供 CharacterPanel / NpcChatDialog / MapLocationTile 等复用。
## 缺图时给出确定性色块 + 名字首字兜底。
## 特殊：tudi_gong 头像走标准 PORTRAIT_FILES 映射（tu_di_gong.png），缺图时用程序化占位（金色圆 + "土" 字）。
## 立绘：tudi_gong 若 portraits_full/tudi_gong_pose{N}.jpg 存在则加载，缺图用程序化 3 姿态占位。

## npc_id → 头像文件名（拼音音节分开，与 design/art/head_portrait/ 对齐）
const PORTRAIT_FILES := {
	"lin_chaoyin": "lin_chao_yin.png",
	"chen_yuanzhou": "chen_yuan_zhou.png",
	"chen_haisheng": "chen_hai_sheng.png",
	"gu_chenzhou": "gu_chen_zhou.png",
	"huiyuan": "hui_yuan.png",
	"jiang_xueyi": "jiang_xue_yi.png",
	"xu_mingchuan": "xu_ming_chuan.png",
	"xu_qing": "xu_qing.png",
	"zhou_xingzhi": "zhou_xing_zhi.png",
	"su_wan": "su_wan.png",
	"ye_keke": "ye_keke.png",
	"lin_yueqin": "lin_yue_qin.png",
	"he_laosan": "he_lao_san.png",
	"zhao_shouzheng": "zhao_shou_zheng.png",
	"tudi_gong": "tu_di_gong.png",
}

## 全身立绘每 NPC 最大姿态数（越界回退 pose1）
const PORTRAIT_FULL_MAX_POSE := {
	"lin_chaoyin": 6, "chen_yuanzhou": 6, "chen_haisheng": 6,
	"gu_chenzhou": 6, "huiyuan": 6,
	"jiang_xueyi": 3, "xu_mingchuan": 3, "xu_qing": 3, "zhou_xingzhi": 3,
	"su_wan": 3, "ye_keke": 3, "lin_yueqin": 3, "he_laosan": 3, "zhao_shouzheng": 3,
	"tudi_gong": 3,
}

const PORTRAIT_DIR := "res://assets/portraits/"
const PORTRAIT_FULL_DIR := "res://assets/portraits_full/"
const BACKGROUND_DIR := "res://assets/backgrounds/"

## 头像纹理缓存
var _portrait_cache: Dictionary = {}
## 全身立绘缓存（key: "{id}_pose{N}"）
var _portrait_full_cache: Dictionary = {}
## 地点背景纹理缓存（key: location_id；null 记入避免反复尝试）
var _background_cache: Dictionary = {}

## 首字（用于色块兜底）
func get_initial(display_name: String) -> String:
	if display_name == null or display_name == "":
		return "?"
	return display_name.substr(0, 1)

## 确定性色（同一 npc_id 每次同色，兜底色块用）
func get_color(npc_id: String) -> Color:
	if npc_id == "" or npc_id == null:
		return Color(0.45, 0.45, 0.5, 1)
	var hash_val: int = npc_id.hash()
	var h: float = float(hash_val & 0xFFFF) / 65535.0
	return Color.from_hsv(h, 0.35, 0.75, 1.0)

## 加载头像。缺失/失败返回 null，UI 应回落到色块+首字。
func get_portrait(npc_id: String) -> Texture2D:
	if npc_id == "" or npc_id == null:
		return null
	if _portrait_cache.has(npc_id):
		return _portrait_cache[npc_id]
	if not PORTRAIT_FILES.has(npc_id):
		_portrait_cache[npc_id] = null
		return null
	var path: String = PORTRAIT_DIR + String(PORTRAIT_FILES[npc_id])
	if not ResourceLoader.exists(path):
		## 土地公真图缺失时使用程序化占位（金色圆 + "土"字），其他角色返回 null 走色块兜底
		if npc_id == "tudi_gong":
			var tex_fallback := _make_tudi_gong_portrait()
			_portrait_cache[npc_id] = tex_fallback
			return tex_fallback
		_portrait_cache[npc_id] = null
		return null
	var tex := load(path) as Texture2D
	## 若 PNG 存在但 .import sidecar 缺失（用户尚未打开编辑器导入），load() 返回 null
	if tex == null and npc_id == "tudi_gong":
		tex = _make_tudi_gong_portrait()
	_portrait_cache[npc_id] = tex
	return tex

## 加载全身立绘（含 pose 姿态号，越界回退 pose1）
func get_full_portrait(npc_id: String, pose: int = 1) -> Texture2D:
	if npc_id == "" or npc_id == null:
		return null
	var max_pose: int = int(PORTRAIT_FULL_MAX_POSE.get(npc_id, 1))
	var use_pose: int = pose if pose >= 1 and pose <= max_pose else 1
	var key: String = "%s_pose%d" % [npc_id, use_pose]
	if _portrait_full_cache.has(key):
		return _portrait_full_cache[key]
	var path: String = "%s%s.jpg" % [PORTRAIT_FULL_DIR, key]
	if not ResourceLoader.exists(path):
		## 土地公：真图缺失时按姿态生成程序化立绘（256×384，姿态可辨）
		if npc_id == "tudi_gong":
			var placeholder := _make_tudi_gong_full(use_pose)
			_portrait_full_cache[key] = placeholder
			return placeholder
		if use_pose != 1:
			return get_full_portrait(npc_id, 1)
		_portrait_full_cache[key] = null
		return null
	var tex := load(path) as Texture2D
	_portrait_full_cache[key] = tex
	return tex

## 生成土地公程序化头像：金色圆 + 深棕描边 + "土" 字。
## 尺寸可变，默认 96x96；一次生成，全局缓存。
func _make_tudi_gong_portrait(size: int = 96) -> ImageTexture:
	var img := Image.create(size, size, false, Image.FORMAT_RGBA8)
	img.fill(Color(0, 0, 0, 0))
	var cx: float = size * 0.5
	var cy: float = size * 0.5
	var r_outer: float = size * 0.48
	var r_border: float = size * 0.44
	var col_bg := Color(0.09, 0.11, 0.14, 1.0)   ## 深底
	var col_edge := Color(0.52, 0.36, 0.16, 1.0) ## 棕描边
	var col_gold := Color(0.95, 0.78, 0.35, 1.0) ## 金
	for y in range(size):
		for x in range(size):
			var dx: float = x - cx
			var dy: float = y - cy
			var d: float = sqrt(dx * dx + dy * dy)
			if d <= r_border:
				img.set_pixel(x, y, col_gold)
			elif d <= r_outer:
				img.set_pixel(x, y, col_edge)
			elif d <= r_outer + 1.0:
				img.set_pixel(x, y, col_bg)
	## 在中心用简易像素笔画写一个"土"字（三横一竖）
	var stroke_col := Color(0.15, 0.10, 0.05, 1.0)
	var s: float = size / 96.0  ## 缩放系数（以 96 为基线）
	var w_top: int = int(28 * s)
	var w_mid: int = int(20 * s)
	var w_bot: int = int(40 * s)
	var thick: int = max(1, int(4 * s))
	var vx: int = int(cx)
	var v_top_y: int = int(cy - 22 * s)
	var v_bot_y: int = int(cy + 22 * s)
	## 竖
	for y in range(v_top_y, v_bot_y):
		for xo in range(-thick / 2, thick - thick / 2):
			_set_safe(img, vx + xo, y, stroke_col, size)
	## 上横
	_h_bar(img, int(cx), v_top_y, w_top, thick, stroke_col, size)
	## 中横
	_h_bar(img, int(cx), int(cy), w_mid, thick, stroke_col, size)
	## 下横
	_h_bar(img, int(cx), v_bot_y, w_bot, thick, stroke_col, size)
	return ImageTexture.create_from_image(img)

func _h_bar(img: Image, cx: int, cy: int, width: int, thick: int, col: Color, canvas: int) -> void:
	var half: int = int(width / 2.0)
	for x in range(cx - half, cx + half):
		for yo in range(-thick / 2, thick - thick / 2):
			_set_safe(img, x, cy + yo, col, canvas)

func _set_safe(img: Image, x: int, y: int, col: Color, canvas: int) -> void:
	if x < 0 or y < 0 or x >= canvas or y >= canvas:
		return
	img.set_pixel(x, y, col)

## 清除缓存（例如美术热更新时）
func clear_cache() -> void:
	_portrait_cache.clear()
	_portrait_full_cache.clear()
	_background_cache.clear()

## 加载地点空镜背景 {location_id}.jpg。缺失返回 null。
func get_background(location_id: String) -> Texture2D:
	if location_id == "" or location_id == null:
		return null
	if _background_cache.has(location_id):
		return _background_cache[location_id]
	var path: String = "%s%s.jpg" % [BACKGROUND_DIR, location_id]
	if not ResourceLoader.exists(path):
		_background_cache[location_id] = null
		return null
	var tex := load(path) as Texture2D
	_background_cache[location_id] = tex
	return tex

## 生成土地公程序化全身立绘（256×384 像素画，3 姿态可辨）。
## POSE 1 慵懒守炉 / POSE 2 苦笑无奈 / POSE 3 显灵严肃。
## 银须 + 深赭红员外帽 + 赭黄袍 + 深棕短褂 + 木杖，各姿态在头倾/杖角度/光环上区分。
func _make_tudi_gong_full(pose: int = 1) -> ImageTexture:
	var w := 256
	var h := 384
	var img := Image.create(w, h, false, Image.FORMAT_RGBA8)
	img.fill(Color(0, 0, 0, 0))

	## 调色板
	var col_skin := Color(0.95, 0.82, 0.68, 1.0)
	var col_skin_shade := Color(0.82, 0.66, 0.52, 1.0)
	var col_cap := Color(0.52, 0.16, 0.13, 1.0)          ## 深赭红员外帽
	var col_cap_shade := Color(0.36, 0.09, 0.07, 1.0)
	var col_bead := Color(0.30, 0.18, 0.09, 1.0)         ## 帽顶木珠
	var col_brow := Color(0.94, 0.94, 0.94, 1.0)         ## 白眉
	var col_eye := Color(0.10, 0.08, 0.06, 1.0)
	var col_nose := Color(0.86, 0.48, 0.42, 1.0)
	var col_beard := Color(0.96, 0.96, 0.94, 1.0)        ## 银白胡须
	var col_beard_shade := Color(0.80, 0.80, 0.78, 1.0)
	var col_robe := Color(0.80, 0.66, 0.32, 1.0)         ## 赭黄长袍
	var col_robe_shade := Color(0.60, 0.48, 0.20, 1.0)
	var col_coat := Color(0.35, 0.22, 0.11, 1.0)         ## 深棕短褂
	var col_belt := Color(0.55, 0.55, 0.58, 1.0)         ## 灰腰带
	var col_cane := Color(0.36, 0.22, 0.11, 1.0)         ## 木杖
	var col_ring := Color(0.68, 0.52, 0.22, 1.0)         ## 铜环
	var col_shoe := Color(0.20, 0.13, 0.08, 1.0)
	var col_halo := Color(1.0, 0.82, 0.38, 0.35)         ## POSE3 金色光环

	## 姿态参数：head_tilt(度) / cane_angle(度,0=垂直) / halo / beard_lift(px)
	var head_tilt := 0.0
	var cane_angle := 8.0
	var draw_halo := false
	var beard_lift := 0
	var eye_open := 0.55
	var mouth := "neutral"
	match pose:
		1:
			head_tilt = -4.0
			cane_angle = 14.0
			eye_open = 0.55
			mouth = "smile_small"
		2:
			head_tilt = 8.0
			cane_angle = 22.0
			eye_open = 0.40
			mouth = "wry"
		3:
			head_tilt = 0.0
			cane_angle = 0.0
			draw_halo = true
			beard_lift = 6
			eye_open = 1.0
			mouth = "flat"

	var cx := 128

	## POSE 3 金色光环（画在最底层）
	if draw_halo:
		_fill_circle(img, cx, 100, 74, col_halo, w, h)
		_fill_circle(img, cx, 100, 60, Color(1.0, 0.88, 0.5, 0.15), w, h)

	## 长袍主体（梯形），y 140→330
	for y in range(140, 330):
		var t := float(y - 140) / float(330 - 140)
		var half_w := int(38 + t * 42)  ## 上窄下宽
		_fill_rect(img, cx - half_w, y, half_w * 2, 1, col_robe, w, h)
		## 袍下摆阴影
		if y > 300:
			_fill_rect(img, cx - half_w, y, half_w * 2, 1, col_robe_shade, w, h)
	## 袍中缝阴影
	for y in range(150, 320):
		img.set_pixel(cx, y, col_robe_shade)

	## 深棕短褂（覆盖肩胸，y 140→210）
	for y in range(140, 212):
		var t := float(y - 140) / 72.0
		var half_w := int(44 + t * 8)
		_fill_rect(img, cx - half_w, y, half_w * 2, 1, col_coat, w, h)
	## 短褂中缝（露出袍内里）
	for y in range(150, 210):
		_fill_rect(img, cx - 2, y, 4, 1, col_robe, w, h)

	## 灰布腰带 y 214→224
	_fill_rect(img, cx - 54, 214, 108, 10, col_belt, w, h)
	_fill_rect(img, cx - 54, 224, 108, 1, Color(0.35, 0.35, 0.38, 1.0), w, h)

	## 鞋（露出袍下）
	_fill_rect(img, cx - 26, 330, 20, 8, col_shoe, w, h)
	_fill_rect(img, cx + 6, 330, 20, 8, col_shoe, w, h)

	## 头部（圆形，中心 cx, 100）
	var head_cx := cx + int(head_tilt * 0.6)
	var head_cy := 100
	_fill_circle(img, head_cx, head_cy, 32, col_skin, w, h)
	_fill_circle_ring(img, head_cx, head_cy, 32, 33, col_skin_shade, w, h)

	## 员外帽（帽体：圆顶+帽檐）
	## 帽檐（宽扁）y 58→68
	_fill_rect(img, head_cx - 40, 68, 80, 6, col_cap_shade, w, h)
	_fill_rect(img, head_cx - 40, 60, 80, 8, col_cap, w, h)
	## 圆顶
	_fill_circle_half(img, head_cx, 62, 30, col_cap, w, h, true)
	_fill_circle_half(img, head_cx, 62, 30, col_cap_shade, w, h, false)  ## 下半描边不画
	## 帽顶木珠
	_fill_circle(img, head_cx, 34, 4, col_bead, w, h)

	## 白眉（两条，长而下垂）
	_fill_rect(img, head_cx - 22, 84, 16, 2, col_brow, w, h)
	img.set_pixel(head_cx - 6, 86, col_brow)
	img.set_pixel(head_cx - 7, 86, col_brow)
	_fill_rect(img, head_cx + 6, 84, 16, 2, col_brow, w, h)
	img.set_pixel(head_cx + 6, 86, col_brow)
	img.set_pixel(head_cx + 7, 86, col_brow)

	## 眼睛（缝眼/圆眼由 eye_open 控制）
	if eye_open >= 0.9:
		## 显灵姿态：睁大
		_fill_rect(img, head_cx - 14, 90, 4, 3, col_eye, w, h)
		_fill_rect(img, head_cx + 10, 90, 4, 3, col_eye, w, h)
	else:
		var eh: int = 1 if eye_open < 0.5 else 2
		_fill_rect(img, head_cx - 14, 91, 6, eh, col_eye, w, h)
		_fill_rect(img, head_cx + 8, 91, 6, eh, col_eye, w, h)

	## 鼻头（略红点）
	_fill_rect(img, head_cx - 2, 100, 4, 3, col_nose, w, h)

	## 嘴
	match mouth:
		"smile_small":
			_fill_rect(img, head_cx - 5, 110, 10, 1, col_eye, w, h)
			img.set_pixel(head_cx - 6, 109, col_eye)
			img.set_pixel(head_cx + 5, 109, col_eye)
		"wry":
			## 左边下垂，右边上翘
			_fill_rect(img, head_cx - 6, 111, 6, 1, col_eye, w, h)
			_fill_rect(img, head_cx, 109, 6, 1, col_eye, w, h)
		"flat":
			_fill_rect(img, head_cx - 6, 111, 12, 1, col_eye, w, h)

	## 银白长胡须（下巴 y=118 → 胸口 y=200-beard_lift）
	var beard_top := 118
	var beard_bot := 200 - beard_lift
	for y in range(beard_top, beard_bot):
		var t := float(y - beard_top) / float(beard_bot - beard_top)
		var half_w := int(22 - t * 8)  ## 顶宽底窄
		_fill_rect(img, head_cx - half_w, y, half_w * 2, 1, col_beard, w, h)
		## 边缘阴影
		img.set_pixel(clamp(head_cx - half_w, 0, w - 1), y, col_beard_shade)
		img.set_pixel(clamp(head_cx + half_w - 1, 0, w - 1), y, col_beard_shade)
	## POSE3：胡须尖端稍向左飘（面向 NPC 方向）
	if beard_lift > 0:
		_fill_rect(img, head_cx - 18, beard_bot, 14, 3, col_beard, w, h)

	## 手臂：左手袖（塞在袍内，简化为袍侧圆凸）
	_fill_rect(img, cx - 60, 200, 16, 30, col_robe, w, h)
	_fill_rect(img, cx - 60, 226, 20, 8, col_robe_shade, w, h)

	## 右手（握杖）——手部方块
	_fill_rect(img, cx + 40, 214, 14, 12, col_skin, w, h)

	## 木杖（右手握），角度由 cane_angle 控制
	var cane_grip_x := cx + 47
	var cane_grip_y := 220
	var cane_len := 150
	var ang_rad := deg_to_rad(cane_angle)
	var top_x := cane_grip_x + int(sin(ang_rad) * (cane_len * 0.55))
	var top_y := cane_grip_y - int(cos(ang_rad) * (cane_len * 0.55))
	var bot_x := cane_grip_x - int(sin(ang_rad) * (cane_len * 0.45))
	var bot_y := cane_grip_y + int(cos(ang_rad) * (cane_len * 0.45))
	_draw_thick_line(img, top_x, top_y, bot_x, bot_y, 3, col_cane, w, h)
	## 铜环（杖头）
	_fill_circle(img, top_x, top_y, 4, col_ring, w, h)

	return ImageTexture.create_from_image(img)

## ─── 像素画绘制辅助 ────────────────────────────────
func _fill_rect(img: Image, x: int, y: int, ww: int, hh: int, col: Color, canvas_w: int, canvas_h: int) -> void:
	for j in range(y, y + hh):
		for i in range(x, x + ww):
			if i >= 0 and j >= 0 and i < canvas_w and j < canvas_h:
				img.set_pixel(i, j, col)

func _fill_circle(img: Image, cx: int, cy: int, r: int, col: Color, canvas_w: int, canvas_h: int) -> void:
	for y in range(cy - r, cy + r + 1):
		for x in range(cx - r, cx + r + 1):
			if x < 0 or y < 0 or x >= canvas_w or y >= canvas_h:
				continue
			var dx := x - cx
			var dy := y - cy
			if dx * dx + dy * dy <= r * r:
				img.set_pixel(x, y, col)

func _fill_circle_ring(img: Image, cx: int, cy: int, r_in: int, r_out: int, col: Color, canvas_w: int, canvas_h: int) -> void:
	for y in range(cy - r_out, cy + r_out + 1):
		for x in range(cx - r_out, cx + r_out + 1):
			if x < 0 or y < 0 or x >= canvas_w or y >= canvas_h:
				continue
			var dx := x - cx
			var dy := y - cy
			var d2 := dx * dx + dy * dy
			if d2 <= r_out * r_out and d2 > r_in * r_in:
				img.set_pixel(x, y, col)

func _fill_circle_half(img: Image, cx: int, cy: int, r: int, col: Color, canvas_w: int, canvas_h: int, upper: bool) -> void:
	for y in range(cy - r, cy + r + 1):
		if upper and y > cy:
			continue
		if not upper and y < cy:
			continue
		for x in range(cx - r, cx + r + 1):
			if x < 0 or y < 0 or x >= canvas_w or y >= canvas_h:
				continue
			var dx := x - cx
			var dy := y - cy
			if dx * dx + dy * dy <= r * r:
				img.set_pixel(x, y, col)

func _draw_thick_line(img: Image, x0: int, y0: int, x1: int, y1: int, thick: int, col: Color, canvas_w: int, canvas_h: int) -> void:
	var dx: int = int(abs(x1 - x0))
	var dy: int = int(abs(y1 - y0))
	var sx: int = 1 if x0 < x1 else -1
	var sy: int = 1 if y0 < y1 else -1
	var err: int = dx - dy
	var cx: int = x0
	var cy: int = y0
	var steps: int = 0
	while steps < 512:
		for oy in range(-thick / 2, thick - thick / 2):
			for ox in range(-thick / 2, thick - thick / 2):
				var px: int = cx + ox
				var py: int = cy + oy
				if px >= 0 and py >= 0 and px < canvas_w and py < canvas_h:
					img.set_pixel(px, py, col)
		if cx == x1 and cy == y1:
			return
		var e2: int = 2 * err
		if e2 > -dy:
			err -= dy
			cx += sx
		if e2 < dx:
			err += dx
			cy += sy
		steps += 1
