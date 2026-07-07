extends Node

## 头像服务（Autoload：PortraitService）。
## 统一 npc_id → 头像纹理映射与缓存，供 CharacterPanel / NpcChatDialog / MapLocationTile 等复用。
## 缺图时给出确定性色块 + 名字首字兜底。
## 特殊：tudi_gong 无静态图，用运行时程序化占位（金色圆 + "土" 字）。

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
}

## 全身立绘每 NPC 最大姿态数（越界回退 pose1）
const PORTRAIT_FULL_MAX_POSE := {
	"lin_chaoyin": 6, "chen_yuanzhou": 6, "chen_haisheng": 6,
	"gu_chenzhou": 6, "huiyuan": 6,
	"jiang_xueyi": 3, "xu_mingchuan": 3, "xu_qing": 3, "zhou_xingzhi": 3,
	"su_wan": 3, "ye_keke": 3, "lin_yueqin": 3, "he_laosan": 3, "zhao_shouzheng": 3,
	"tudi_gong": 1,
}

const PORTRAIT_DIR := "res://assets/portraits/"
const PORTRAIT_FULL_DIR := "res://assets/portraits_full/"

## 头像纹理缓存
var _portrait_cache: Dictionary = {}
## 全身立绘缓存（key: "{id}_pose{N}"）
var _portrait_full_cache: Dictionary = {}

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
	## 土地公：程序化占位
	if npc_id == "tudi_gong":
		var tex := _make_tudi_gong_portrait()
		_portrait_cache[npc_id] = tex
		return tex
	if not PORTRAIT_FILES.has(npc_id):
		_portrait_cache[npc_id] = null
		return null
	var path: String = PORTRAIT_DIR + String(PORTRAIT_FILES[npc_id])
	if not ResourceLoader.exists(path):
		_portrait_cache[npc_id] = null
		return null
	var tex := load(path) as Texture2D
	_portrait_cache[npc_id] = tex
	return tex

## 加载全身立绘（含 pose 姿态号，越界回退 pose1）
func get_full_portrait(npc_id: String, pose: int = 1) -> Texture2D:
	if npc_id == "" or npc_id == null:
		return null
	if npc_id == "tudi_gong":
		## 土地公暂无全身立绘，退回大号头像占位
		return _make_tudi_gong_portrait(256)
	var max_pose: int = int(PORTRAIT_FULL_MAX_POSE.get(npc_id, 1))
	var use_pose: int = pose if pose >= 1 and pose <= max_pose else 1
	var key: String = "%s_pose%d" % [npc_id, use_pose]
	if _portrait_full_cache.has(key):
		return _portrait_full_cache[key]
	var path: String = "%s%s.jpg" % [PORTRAIT_FULL_DIR, key]
	if not ResourceLoader.exists(path):
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
