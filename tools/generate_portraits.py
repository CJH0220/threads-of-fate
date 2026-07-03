"""批量调用火山方舟 Doubao Seedream 4.0 生成角色大立绘。

- 参考图：godot/assets/portraits/{pinyin_split}.png（头像作为角色一致性参考）
- 提示词来源：design/art/character-pixel-portrait-prompts.md（按 npc + POSE 号解析）
- 输出：godot/assets/portraits_full/{npc_id}_pose{N}.jpg（豆包 Seedream 返回 JPEG）
- 断点续跑：目标文件已存在则跳过
- 环境变量：ARK_API_KEY

用法：
    export ARK_API_KEY=xxx
    python tools/generate_portraits.py --npc lin_chaoyin
    python tools/generate_portraits.py --npc lin_chaoyin --poses 1,3    # 只重跑指定姿态
    python tools/generate_portraits.py --npc lin_chaoyin --force        # 覆盖已存在
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import urllib.request
import urllib.error


ROOT = Path(__file__).resolve().parents[1]
PROMPT_DOC = ROOT / "design" / "art" / "character-pixel-portrait-prompts.md"
PORTRAIT_DIR = ROOT / "godot" / "assets" / "portraits"
OUTPUT_DIR = ROOT / "godot" / "assets" / "portraits_full"

MODEL = "doubao-seedream-4-0-250828"
ENDPOINT = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
# Seedream 4.0 要求 >= 921600 像素；保持 2:3 比例，与原规格 256x384/512x768 同比。
# 生成 1024x1536，游戏内运行时用 Godot TextureRect 缩放。
IMAGE_SIZE = "1024x1536"

# npc_id → 参考头像文件名（拼音音节分开）
PORTRAIT_FILES = {
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

# npc_id → 提示词文档里的中文小节标题（对应 "### 中文名 - 描述 - 全套6姿态"）
NPC_SECTIONS = {
    "lin_chaoyin": "林潮音",
    "chen_yuanzhou": "陈远舟",
    "chen_haisheng": "陈海生",
    "gu_chenzhou": "顾沉舟",
    "huiyuan": "慧圆",
    "jiang_xueyi": "江雪仪",
    "xu_mingchuan": "许明川",
    "xu_qing": "许晴",
    "zhou_xingzhi": "周行知",
    "su_wan": "苏婉",
    "ye_keke": "叶可可",
    "lin_yueqin": "林月琴",
    "he_laosan": "何老三",
    "zhao_shouzheng": "赵守正",
}

NEGATIVE_PROMPT = (
    "3D, realistic, photorealistic, blurry, anti-alias, smooth, gradient, "
    "complex background, multiple people, extra limbs, ugly, deformed, text, "
    "watermark, signature, high contrast, oversaturated, anime, manga, cropped, "
    "bad anatomy, shadows on background, colored background, scenery, "
    "environmental details, anything behind character"
)


@dataclass
class PosePrompt:
    npc_id: str
    pose_index: int  # 1-based
    title: str
    prompt: str


def parse_poses(npc_id: str) -> list[PosePrompt]:
    """从 prompt 文档中抓取 npc 的全部 POSE 段。"""
    if npc_id not in NPC_SECTIONS:
        raise KeyError(f"未知 npc_id: {npc_id}")
    section_name = NPC_SECTIONS[npc_id]
    text = PROMPT_DOC.read_text(encoding="utf-8")

    # 定位角色小节起点：以 "### {中文名} - " 开头
    section_re = re.compile(
        rf"^###\s+{re.escape(section_name)}\s+-\s+.+?$", re.MULTILINE
    )
    m = section_re.search(text)
    if not m:
        raise ValueError(f"未在文档中找到 {section_name} 的小节标题")
    section_start = m.end()

    # 小节终点：下一个 "### " 标题或分部分割线 "## 第"
    tail = text[section_start:]
    next_section = re.search(r"^(###\s|##\s第)", tail, re.MULTILINE)
    section_body = tail if not next_section else tail[: next_section.start()]

    # 抓取每个 POSE：#### POSE N - 标题 \n ``` prompt ```
    pose_re = re.compile(
        r"####\s+POSE\s+(\d+)\s+-\s+([^\n]+?)\n```\s*\n(.*?)\n```",
        re.DOTALL,
    )
    poses: list[PosePrompt] = []
    for match in pose_re.finditer(section_body):
        idx = int(match.group(1))
        title = match.group(2).strip()
        prompt = match.group(3).strip()
        poses.append(PosePrompt(npc_id, idx, title, prompt))
    poses.sort(key=lambda p: p.pose_index)
    return poses


def load_reference(npc_id: str) -> str:
    fname = PORTRAIT_FILES[npc_id]
    fpath = PORTRAIT_DIR / fname
    if not fpath.exists():
        raise FileNotFoundError(f"参考头像缺失：{fpath}")
    data = base64.b64encode(fpath.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{data}"


def call_seedream(api_key: str, prompt: str, ref_image_data_url: str) -> bytes:
    """调用 Seedream 4.0，返回图片二进制。失败会抛异常。"""
    body = {
        "model": MODEL,
        "prompt": prompt,
        "image": ref_image_data_url,
        "size": IMAGE_SIZE,
        "response_format": "b64_json",
        "watermark": False,
    }
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body_txt = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {body_txt}") from e

    if not payload.get("data"):
        raise RuntimeError(f"响应缺少 data 字段：{payload}")
    first = payload["data"][0]
    if "b64_json" in first:
        return base64.b64decode(first["b64_json"])
    if "url" in first:
        with urllib.request.urlopen(first["url"], timeout=120) as r:
            return r.read()
    raise RuntimeError(f"响应无法解析：{first}")


def main(argv: Iterable[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--npc", required=True, help="npc_id，例如 lin_chaoyin")
    ap.add_argument(
        "--poses",
        default="",
        help="逗号分隔的 pose 序号；留空=全部",
    )
    ap.add_argument("--force", action="store_true", help="覆盖已存在文件")
    ap.add_argument("--dry-run", action="store_true", help="只打印，不调用 API")
    args = ap.parse_args(argv)

    api_key = os.environ.get("ARK_API_KEY", "").strip()
    if not api_key and not args.dry_run:
        print("[错误] 未设置 ARK_API_KEY 环境变量。", file=sys.stderr)
        return 2

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    poses = parse_poses(args.npc)
    if not poses:
        print(f"[错误] {args.npc} 没有任何 POSE 提示词。", file=sys.stderr)
        return 1

    if args.poses:
        wanted = {int(x) for x in args.poses.split(",") if x.strip()}
        poses = [p for p in poses if p.pose_index in wanted]

    ref = None if args.dry_run else load_reference(args.npc)

    print(f"[任务] npc={args.npc} 姿态={[p.pose_index for p in poses]} 输出={OUTPUT_DIR}")
    for p in poses:
        out = OUTPUT_DIR / f"{args.npc}_pose{p.pose_index}.jpg"
        if out.exists() and not args.force:
            print(f"  [跳过] {out.name}（已存在，加 --force 覆盖）")
            continue
        # prompt 追加负向指令作为文本尾巴（Ark 图像接口未单列 negative_prompt 字段）
        full_prompt = f"{p.prompt}\n\nAvoid: {NEGATIVE_PROMPT}"
        print(f"  [生成] pose{p.pose_index} · {p.title} …", end="", flush=True)
        if args.dry_run:
            print(" (dry-run)")
            continue
        start = time.time()
        try:
            img = call_seedream(api_key, full_prompt, ref)
        except Exception as e:
            print(f" 失败：{e}")
            continue
        out.write_bytes(img)
        print(f" 完成 ({len(img)//1024}KB, {time.time()-start:.1f}s) → {out.name}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
