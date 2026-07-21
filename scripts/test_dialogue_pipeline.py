"""对白管线端到端测试 — 打印每一步的输入/输出。

用法：
    cd H:\Game\threads-of-fate
    python scripts/test_dialogue_pipeline.py
"""

import sys, asyncio, json, os
sys.path.insert(0, ".")

os.environ.setdefault("EVENT_PROB_MULTIPLIER", "10.0")

from src.backend.server.state import init_session
from src.backend.engine.story import load_story_outline, load_event_templates
from src.backend.ai.screenwriter import screenwriter_think
from src.backend.ai.dialogue_designer.pipeline import run_dialogue_pipeline, dialogue_to_description
from src.backend.models.npc import Slot


async def main():
    session = init_session()
    day, slot, week = 1, Slot.NOON, 1
    phase_name = "旧神将熄"

    # ── Step 1: NPC think() ──
    print("=" * 70)
    print(f"  STEP 1: NPC think() — Day{day} {slot.value} Week{week}")
    print("=" * 70)

    npc_intentions = []
    for aid in session.agents.npc_ids:
        ag = session.agents.get(aid)
        if ag is None:
            continue
        if ag.static.tier.value in ("S", "A"):
            try:
                action = await ag.think(day, slot)
            except Exception as e:
                action = ag._default_action(day, slot)
                print(f"  {ag.name}: LLM失败→兜底 ({type(e).__name__})")
        else:
            action = ag._default_action(day, slot)
        npc_intentions.append((ag.npc_id, ag.name, action or "",
                               ag.dynamic.current.location.value))
        print(f"  {ag.name}({ag.npc_id}) @{ag.dynamic.current.location.value}: {(action or '?')[:60]}")

    # ── Step 2: Screenwriter ──
    print(f"\n{'=' * 70}")
    print(f"  STEP 2: 编剧编排")
    print("=" * 70)

    outline = load_story_outline()
    templates = load_event_templates()
    screenwriter_llm = None
    for aid in session.agents.npc_ids:
        ag = session.agents.get(aid)
        if ag and ag.static.tier.value == "S":
            screenwriter_llm = ag.llm
            break

    print(f"  outline={outline is not None}  templates={templates is not None}  llm={screenwriter_llm is not None}")

    if outline and screenwriter_llm:
        ok, events = await screenwriter_think(
            session=session, story_outline=outline,
            day=day, slot=slot, week=week, phase_name=phase_name,
            npc_intentions=npc_intentions, llm=screenwriter_llm, templates=templates,
        )
        print(f"  screenwriter ok={ok}  events={len(events)}")
    else:
        print(f"  SKIP: outline={outline is not None} llm={screenwriter_llm is not None}")
        return

    if not ok or not events:
        print("  无事件产出，结束。")
        return

    # ── Step 3: 筛选有骨架的事件 ──
    print(f"\n{'=' * 70}")
    print(f"  STEP 3: 对白管线")
    print("=" * 70)

    for i, (evt, outcome) in enumerate(events):
        skeleton = getattr(evt, "dialogue_skeleton", None)
        print(f"\n  ┌─ 事件 [{i}]: {evt.name} ({evt.id})")
        print(f"  │  participants: {evt.participants}  location: {evt.location}")
        print(f"  │  has skeleton: {skeleton is not None}")

        if not skeleton:
            print(f"  │  → 无骨架，用 description: {(evt.description or '?')[:80]}")
            continue

        # 打印骨架
        print(f"  │  【对话骨架】")
        print(f"  │    goal: {skeleton.get('goal', '?')}")
        print(f"  │    tone: {skeleton.get('tone', '?')}")
        for step in skeleton.get("line_steps", []):
            print(f"  │    [{step.get('step_id','?')}] {step.get('actor','?')}: "
                  f"intent={step.get('intent','?')[:40]}")
        print(f"  │")

        # ── Step 3a: fill_scene ──
        print(f"  │  【NPC fill_scene 输入/输出】")
        filled = []
        for pid in evt.participants:
            ag = session.agents.get(pid)
            if ag is None:
                print(f"  │    {pid}: agent=None")
                continue
            if ag.static.tier.value not in ("S", "A"):
                print(f"  │    {pid}({ag.name}): B/C级 跳过")
                continue

            try:
                result = await ag.fill_scene(skeleton, day, slot)
                filled.append(result)
                print(f"  │    {pid}({ag.name}):")
                for line in result.get("lines", []):
                    print(f"  │      [{line.get('type','?')}] {line.get('text','?')[:60]}")
            except Exception as e:
                print(f"  │    {pid}({ag.name}): FAIL {type(e).__name__}: {e}")

        if not filled:
            print(f"  │    → 无 fill_scene 成功，跳过润色")
            continue

        # ── Step 3b: polish ──
        print(f"  │")
        print(f"  │  【对白设计师润色】")
        try:
            dialogue = await run_dialogue_pipeline(evt, session, day, slot, screenwriter_llm)
            if dialogue:
                print(f"  │    定稿 location: {dialogue.get('location','?')}")
                for line in dialogue.get("lines", []):
                    print(f"  │    [{line.get('actor','?')}] ({line.get('type','?')}) "
                          f"{line.get('text','?')[:70]}")
                desc = dialogue_to_description(dialogue)
                print(f"  │")
                print(f"  │    description: {desc[:120]}")
            else:
                print(f"  │    → 润色失败，返回 None")
        except Exception as e:
            print(f"  │    → 润色异常: {type(e).__name__}: {e}")

    print(f"\n{'=' * 70}")
    print(f"  DONE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
