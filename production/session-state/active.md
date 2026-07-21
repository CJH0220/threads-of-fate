# 会话状态

> 最后更新：2026-07-21
> 当前分支：7_14-screenwriter

---

## 项目名称

命运的织线 (Threads of Fate)

---

## 最新提交

| 提交 | 说明 |
|------|------|
| c8f160a | chore: 创建项目级 CLAUDE.md |
| 82e099c | docs: 更新策划索引，确立事件表权威，归档旧稿 |
| 2338f76 | fix: 修正托梦消耗值 2→3，迁移剧情大纲 v3.0 |
| a621d0c | docs: 新增 NPC 多代理人架构设计文档 |
| 2ae7143 | feat: 即兴日常事件 — LLM 真实验证通过 + prompt 精简 + semaphore 调优 |

---

## 本次会话完成内容：项目整合

1. **P0 数据修复**：托梦消耗全局统一为 3 神力（5 处修复），剧情大纲迁移 v3.0（72 beats）
2. **事件表权威**：确立三层层级（中文主表 → 英文导出 → Mock 子集）
3. **索引同步**：design/README.md 新增 4 个章节，项目现状梳理升至 v1.3
4. **死链修复**：ui-spec.md 中 3 处 work.md 引用改为 _archive/work_v1.8.md
5. **归档旧稿**：3 份过时文档移至 _archive/，Game1/ Unity 项目添加 DEPRECATED.md
6. **Claude 配置**：创建 game1/CLAUDE.md，建立 4 个游戏专属记忆文件
7. **CCGS 适配**：引擎默认值改为 Godot 4.4（待 CCGS 仓库 git config 设置后提交）

---

## 技术栈

- **前端**：Godot 4.4，像素风，1280×720，gl_compatibility 渲染器
- **后端**：FastAPI + Uvicorn + Pydantic v2 + httpx（异步）
- **AI 层**：LLM 双模式（Llama / Anthropic），NPC 记忆系统 + 编剧 Agent 叙事编排

---

## 当前状态

- 策划文档整合完成，权威层级已确立
- 前端：30+ 场景/脚本，双模式适配器，可独立跑通
- 后端：编剧 Agent 系统已实现，LLM 日常事件生成验证通过
- 已知：后端有 4 个玩法 bug 待修复（B1-B4），契约与实现数值对齐待完成
- 待办：CCGS 仓库提交引擎配置变更