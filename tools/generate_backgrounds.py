"""批量调用火山方舟 Doubao Seedream 4.0 生成地点背景空镜。

- 提示词来源：design/art/location-background-prompts.md
  每个地点用 "## N. 中文名 (location_id)" 作为小节标题；
  正向 prompt 是小节内第一个 ```code``` 块。
  通用正向前缀 / 通用负向 prompt 从 "## 0. 通用规格" 里两个代码块抓取。
- 输出：godot/assets/backgrounds/{location_id}.jpg（Seedream 返回 JPEG）
- 断点续跑：目标文件已存在则跳过
- 环境变量：ARK_API_KEY

用法：
    export ARK_API_KEY=xxx
    python tools/generate_backgrounds.py --all
    python tools/generate_backgrounds.py --location temple
    python tools/generate_backgrounds.py --location temple,beach --force
    python tools/generate_backgrounds.py --all --dry-run
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
PROMPT_DOC = ROOT / "design" / "art" / "location-background-prompts.md"
OUTPUT_DIR = ROOT / "godot" / "assets" / "backgrounds"

MODEL = "doubao-seedream-4-0-250828"
ENDPOINT = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
# 16:9 尽量贴近 1280x720；Seedream 4.0 需要 >= 921600 像素，因此上采到 1536x864。
IMAGE_SIZE = "1536x864"


@dataclass
class BgPrompt:
    location_id: str
    display_name: str
    prompt: str


# --- 解析 markdown -----------------------------------------------------------

_SECTION_RE = re.compile(
    r"^##\s+\d+\.\s+([^\(]+?)\s+\(([a-z_]+)\)\s*$",
    re.MULTILINE,
)
_CODEBLOCK_RE = re.compile(r"```[a-zA-Z0-9]*\s*\n(.*?)\n```", re.DOTALL)


def _extract_common_blocks(text: str) -> tuple[str, str]:
    """返回 (通用正向前缀, 通用负向 prompt)。若解析不到则抛异常。"""
    m = re.search(r"^##\s+0\.\s+通用规格.*?(?=^##\s+1\.\s)", text, re.MULTILINE | re.DOTALL)
    if not m:
        raise ValueError("找不到 '## 0. 通用规格' 章节")
    blob = m.group(0)
    blocks = _CODEBLOCK_RE.findall(blob)
    if len(blocks) < 2:
        raise ValueError("§0 至少需要两个代码块：通用负向、通用正向")
    # 文档顺序：先负向，后正向
    neg = blocks[0].strip()
    pos = blocks[1].strip()
    return pos, neg


def parse_prompts() -> tuple[list[BgPrompt], str, str]:
    text = PROMPT_DOC.read_text(encoding="utf-8")
    positive_prefix, negative = _extract_common_blocks(text)

    matches = list(_SECTION_RE.finditer(text))
    if not matches:
        raise ValueError("没抓到任何 '## N. 名称 (id)' 小节")

    prompts: list[BgPrompt] = []
    for i, m in enumerate(matches):
        display_name = m.group(1).strip()
        loc_id = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end]
        block_m = _CODEBLOCK_RE.search(body)
        if not block_m:
            # §0 通用规格自身也匹配了 SECTION_RE？其实不会，因为 §0 没有 (id) 后缀。
            # 但 §12/§13 也不会被 SECTION_RE 匹配（因为没有 (xxx) 形式），可以放心跳过缺代码块的。
            continue
        prompt = block_m.group(1).strip()
        prompts.append(BgPrompt(loc_id, display_name, prompt))
    return prompts, positive_prefix, negative


# --- 调 Seedream -------------------------------------------------------------


def call_seedream(api_key: str, prompt: str) -> bytes:
    body = {
        "model": MODEL,
        "prompt": prompt,
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
        with urllib.request.urlopen(req, timeout=180) as resp:
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
        with urllib.request.urlopen(first["url"], timeout=180) as r:
            return r.read()
    raise RuntimeError(f"响应无法解析：{first}")


# --- 主流程 -----------------------------------------------------------------


def main(argv: Iterable[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--all", action="store_true", help="生成全部地点")
    grp.add_argument("--location", default="", help="逗号分隔的 location_id 列表")
    ap.add_argument("--force", action="store_true", help="覆盖已存在文件")
    ap.add_argument("--dry-run", action="store_true", help="只解析和打印，不调 API")
    args = ap.parse_args(argv)

    prompts, positive_prefix, negative = parse_prompts()

    if args.location:
        wanted = {x.strip() for x in args.location.split(",") if x.strip()}
        unknown = wanted - {p.location_id for p in prompts}
        if unknown:
            print(f"[错误] 未知 location_id: {sorted(unknown)}", file=sys.stderr)
            return 1
        prompts = [p for p in prompts if p.location_id in wanted]

    if not prompts:
        print("[错误] 没有可生成的地点。", file=sys.stderr)
        return 1

    api_key = os.environ.get("ARK_API_KEY", "").strip()
    if not api_key and not args.dry_run:
        print("[错误] 未设置 ARK_API_KEY 环境变量。", file=sys.stderr)
        return 2

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(
        f"[任务] 共 {len(prompts)} 个地点 → {OUTPUT_DIR}\n"
        f"       正向前缀 {len(positive_prefix)} 字符 · 负向 {len(negative)} 字符"
    )

    for p in prompts:
        out = OUTPUT_DIR / f"{p.location_id}.jpg"
        if out.exists() and not args.force:
            print(f"  [跳过] {out.name}（已存在，加 --force 覆盖）")
            continue
        full_prompt = f"{positive_prefix}\n\n{p.prompt}\n\nAvoid: {negative}"
        header = f"  [生成] {p.location_id} · {p.display_name}"
        if args.dry_run:
            print(f"{header} (dry-run · prompt {len(full_prompt)} 字符)")
            continue
        print(f"{header} …", end="", flush=True)
        start = time.time()
        try:
            img = call_seedream(api_key, full_prompt)
        except Exception as e:
            print(f" 失败：{e}")
            continue
        out.write_bytes(img)
        print(f" 完成 ({len(img)//1024}KB, {time.time()-start:.1f}s) → {out.name}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
