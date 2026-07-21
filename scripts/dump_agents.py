"""打印所有 NPC Agent 状态，并模拟时间推进观察事件和 NPC 决策。

用法：
    cd H:\Game\threads-of-fate
    python scripts/dump_agents.py
"""

import sys, asyncio, os
sys.path.insert(0, ".")

os.environ.setdefault("EVENT_PROB_MULTIPLIER", "10.0")  # 测试模式：事件高概率触发

from src.backend.server.state import init_session
from src.backend.engine.event import load_events, match_events, execute_events
from src.backend.models.npc import Slot


def print_compact(session):
    """紧凑打印所有 Agent 当前状态。"""
    print(f"{'='*70}")
    print(f"  Day{session.time.day} {session.time.slot.value} Week{session.time.week} | 香火={session.resource.incense} 神力={session.resource.divine_power}/{session.resource.divine_power_max}")
    print(f"{'='*70}")
    print(f"  {'名称':6s} | {'位置':16s} | {'情绪':8s} | 幸福 精力 | 记忆 | 业线")
    print(f"  {'-'*66}")
    for aid in session.agents.npc_ids:
        ag = session.agents.get(aid)
        if ag:
            d = ag.dynamic.current
            m = ag.memory
            print(f"  {ag.name:6s} | {d.location.value:16s} | {d.emotion.value:8s} | {d.happiness:3d}  {d.energy:3d}  | {m.event_count:2d}条 | {d.karma_main_progress:3.0f}%")
    print()


def advance_one_slot(session):
    """推进一个时段并打印发生的事件和 NPC 决策。"""
    events = load_events()

    # 推进时间
    if not session.time.can_advance():
        print(f"[终局] 已到达第60天！")
        return False

    result = session.time.advance()
    print(f"\n>>> 推进到 Day{result.day} {result.slot.value} Week{result.week} <<<")

    if result.is_new_day:
        session.resource.apply_daily()

    # 收集 NPC 位置
    locs = {}
    for aid in session.agents.npc_ids:
        ag = session.agents.get(aid)
        if ag:
            locs[aid] = ag.dynamic.current.location.value
    locs.update({
        "heaven_messenger": "temple", "tudi_gong": "temple",
        "underworld_messenger": "temple", "town_representative": "plaza",
    })

    # 事件匹配
    matched = match_events(events, day=result.day, slot=result.slot,
                           week=result.week, participant_locations=locs)
    if matched:
        settlement = execute_events(matched, session.resource, session.agents,
                                    day=result.day, slot=result.slot)
        for (evt, _outcome), r in zip(matched, settlement):
            print(f"  [事件] {evt.name}({evt.id}) → {r.outcome_name}")
            print(f"         参与: {evt.participants}  地点: {evt.location}")
            if r.resource_changes:
                print(f"         资源变化: {r.resource_changes}")
            if r.bond_changes:
                print(f"         缘线变化: {r.bond_changes}")
            if r.karma_changes:
                print(f"         业线变化: {r.karma_changes}")

            # 应用缘线/业线
            if r.bond_changes:
                delta_parts = [f"bond_{k}:{v:+d}" for k, v in r.bond_changes.items()]
                session.bonds.apply_delta(";".join(delta_parts))
            if r.karma_changes:
                delta_parts = [f"{k}:{v:+d}" for k, v in r.karma_changes.items()]
                session.karma.apply_delta(";".join(delta_parts))
    else:
        print(f"  [事件] 无")

    # NPC 思考
    async def _think_all():
        tasks = []
        for aid in session.agents.npc_ids:
            ag = session.agents.get(aid)
            if ag and ag.static.tier.value in ("S", "A"):
                tasks.append(ag.think(result.day, result.slot))
        return await asyncio.gather(*tasks, return_exceptions=True)

    actions = asyncio.run(_think_all())
    print(f"  [NPC决策]")
    for aid, action in zip(
        [aid for aid in session.agents.npc_ids
         if session.agents.get(aid) and session.agents.get(aid).static.tier.value in ("S", "A")],
        actions
    ):
        ag = session.agents.get(aid)
        name = ag.name if ag else "?"
        if isinstance(action, Exception):
            print(f"    {name}: ERROR - {action}")
        else:
            print(f"    {name}: {action}")

    return True


# ── 主流程 ──

session = init_session()
print("\n" + "█" * 70)
print("  初始状态")
print_compact(session)

# 推进 4 个时段 (Morning→Noon→Night→Day2 Morning)
for i in range(4):
    if not advance_one_slot(session):
        break
    print_compact(session)
