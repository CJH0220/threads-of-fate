# 《命运的织线》—— 团队协作操作指南

> 最后更新：2026-06-04

---

## 目录

- [1. 项目信息](#1-项目信息)
- [2. 环境准备](#2-环境准备)
- [3. Git 工作流总览](#3-git-工作流总览)
- [4. 分支管理规范](#4-分支管理规范)
- [5. Commit Message 规范](#5-commit-message-规范)
- [6. Pull Request 规范](#6-pull-request-规范)
- [7. Push & 合并规则](#7-push--合并规则)
- [8. 完整实操流程](#8-完整实操流程)
- [9. Unity 特定操作](#9-unity-特定操作)
- [10. 常见问题](#10-常见问题)

---

## 1. 项目信息

| 项目 | 说明 |
|------|------|
| **项目名称** | 命运的织线 (Threads of Fate) |
| **Unity 版本** | 6000.0.75f1 |
| **协作方式** | Git + Git LFS |
| **远程仓库** | GitHub |
| **团队人数** | 2 人 |
| **开发环境** | Unity Editor + Claude Code (WSL) |

---

## 2. 环境准备

### 2.1 必需工具

- **Git**：版本控制
- **Git LFS**：大文件管理（图片、模型、音频、Unity 资源文件）
- **GitHub 账号**：远程协作

### 2.2 初次设置

```bash
# 1. 安装 Git LFS
sudo apt install git-lfs

# 2. 初始化 Git LFS（每台机器只需执行一次）
git lfs install

# 3. 配置用户信息
git config user.name "你的名字"
git config user.email "你的邮箱"

# 4. 克隆项目
git clone <GitHub 仓库地址>
cd threads-of-fate
```

> **💡 Git 小知识：`git config` 的三个层级**
>
> | 层级 | 命令 | 配置文件位置 |
> |------|------|-------------|
> | 系统级（所有用户） | `git config --system` | `/etc/gitconfig` |
> | 用户级（当前用户） | `git config --global` | `~/.gitconfig` |
> | 项目级（当前仓库）| `git config`（不带参数）| `.git/config` |
>
> 我们的 `user.name` 和 `user.email` 一般用 `--global` 设置一次即可：
> ```bash
> git config --global user.name "你的名字"
> git config --global user.email "你的邮箱"
> ```

---

## 3. Git 工作流总览

> **💡 什么是工作流（Workflow）？**
>
> Git 本身只是一个版本控制工具，它不管你怎么用。**工作流** 是团队自己约定的一套规则——什么时候开分支、怎么命名、谁来合并、怎么合并。好的工作流让协作有条不紊，坏的工作流让人每天都在救火。
>
> 常见的工作流模型有：
> - **GitHub Flow**：最简单的模型，只有一个主分支 + 功能分支，适合小团队
> - **Git Flow**：经典的 `main / develop / feature / release / hotfix` 五分支模型，适合有固定发布周期的项目
> - **Trunk-Based Development**：极简模型，所有人直接往主干提交，靠频繁集成来避免冲突
>
> 我们采用 **简化版 GitHub Flow**：`main`（受保护） + `feature/` / `fix/` 分支，所有变更通过 Pull Request 合入。

### 3.1 一张图看懂

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         《命运的织线》Git 工作流                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ① 接到需求                                                                  │
│       │                                                                      │
│       ▼                                                                      │
│  ② git checkout main && git pull          ← 从最新的 main 出发              │
│       │                                                                      │
│       ▼                                                                      │
│  ③ git checkout -b feature/xxx            ← 创建功能分支                    │
│       │                                                                      │
│       ▼                                                                      │
│  ④ 在 Unity 中开发 + 多次 commit           ← 小步提交，频繁保存              │
│       │                                                                      │
│       ▼                                                                      │
│  ⑤ git push -u origin feature/xxx         ← 推送到 GitHub                   │
│       │                                                                      │
│       ▼                                                                      │
│  ⑥ 在 GitHub 上创建 Pull Request           ← 请求合并                       │
│       │                                                                      │
│       ▼                                                                      │
│  ⑦ 另一人 Review 代码                      ← 互相审查                       │
│       │                                                                      │
│       ├── 需要修改 → 提交新 commit → git push → 回到 ⑦                      │
│       │                                                                      │
│       ▼                                                                      │
│  ⑧ Review 通过 → 在 GitHub 上点击 Merge    ← 使用 Merge Commit              │
│       │                                                                      │
│       ▼                                                                      │
│  ⑨ 删除远程分支 + 本地切回 main + pull     ← 清理干净                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 核心理念：为什么要这样？

| 原则 | 解释 |
|------|------|
| **永远不从 main 直接开发** | main 是"真理之源"，只能通过 PR 合入，保证 main 上的每行代码都经过审查 |
| **一个分支只做一件事** | 一个功能、一个修复、一个改动 = 一个分支，不要在一个分支里混多个需求 |
| **小步提交，频繁 commit** | 不要把一整个功能写完才 commit，每完成一个小步骤就提交一次 |
| **合并前必须 Review** | 两个人互相检查代码，既是质量保障，也是互相学习的机会 |
| **合并后清理分支** | 已合并的分支及时删除，避免仓库里堆积几十个僵尸分支 |

---

## 4. 分支管理规范

> **💡 分支的本质是什么？**
>
> 分支在 Git 中只是一个**指向某个 commit 的指针**，它轻量到创建只需要一瞬间。Git 的分支和 SVN 等老式版本控制不同——SVN 的分支相当于复制一份代码，而 Git 的分支只是一个 41 字节的文件，里面写了一个 commit 的 SHA-1 哈希值。
>
> 理解这一点很重要：**切换分支 = 把工作目录的内容换成那个 commit 指向的快照**。这也是为什么切换分支前要先把当前改动 commit 或 stash 的原因——未保存的改动不属于任何 commit，切换时就可能丢失。

### 4.1 分支命名规则

| 前缀 | 用途 | 示例 |
|------|------|------|
| `feature/` | 新功能开发 | `feature/织线交互系统`、`feature/对话框UI` |
| `fix/` | Bug 修复（非紧急） | `fix/存档加载崩溃`、`fix/角色穿模` |
| `refactor/` | 代码重构（不改功能） | `refactor/战斗计算模块` |
| `docs/` | 文档更新 | `docs/团队协作指南` |
| `chore/` | 构建、工具、配置 | `chore/更新Unity版本` |

### 4.2 分支生命周期

```
创建 ────→ 开发中 ────→ 发起 PR ────→ 合并 ────→ 删除
  │                                    │
  └──────────────── 废弃 ──────────────┘
```

1. **创建**：从最新的 `main` 上创建
2. **开发中**：在分支上自由 commit、push
3. **发起 PR**：功能完成（或阶段性完成），在 GitHub 创建 Pull Request
4. **合并**：Review 通过后在 GitHub 上点击 "Create a merge commit"
5. **删除**：合并完成后，删除远程分支，本地也清理掉

> **💡 `git stash` —— 临时保存工作现场**
>
> 如果你正在一个分支上开发，突然需要切到别的分支处理事情，但手头的代码还没写完、不值得 commit，怎么办？
>
> ```bash
> git stash          # 把当前所有未提交的改动"储藏"起来，工作区恢复干净
> git checkout 其他分支
> # ... 处理完事情 ...
> git checkout 原分支
> git stash pop      # 把之前储藏的改动恢复回来
> ```
>
> `stash` 就像一个"草稿箱"，把没写完的代码暂存起来。你可以多次 stash，用 `git stash list` 查看所有储藏。

### 4.3 main 分支保护规则

在 GitHub 仓库的 **Settings → Branches → Branch protection rules** 中配置：

| 规则 | 设置 | 目的 |
|------|------|------|
| 禁止直接 push 到 main | ✅ 开启 | 所有改动必须走 PR |
| PR 合并前必须 Review | ✅ 开启，至少 1 个 approve | 互相审查代码 |
| 合并前 CI 必须通过 | 暂不开启（后续看需求） | 自动化检查 |
| 合并前必须解决冲突 | ✅ 开启 | 保证能干净合并 |
| 合并前分支必须是最新的 | ✅ 开启 | 避免合并过时代码 |

> **💡 为什么要保护 main 分支？**
>
> `main` 分支是你项目永远"处于可运行状态"的版本。如果你允许直接 `push` 到 `main`，任何人都可以在没被检查的情况下改代码，一旦出错，整个项目就崩了——而且很难定位是谁改的、为什么改。
>
> 分支保护相当于给 `main` 加了一把锁：**只有通过 Pull Request、经过另一个人确认的代码才能进来**。在 GitHub 上，即使你是仓库管理员，保护规则开启后你也无法绕过——这条规则对所有人平等生效。

---

## 5. Commit Message 规范

> **💡 为什么要写规范的 commit message？**
>
> 想象三个月后你发现一个 bug，用 `git blame` 追溯到了某一行代码，看到了对应的 commit。commit message 写的是 **"改了一下"** —— 你完全不知道当时为什么要改，改了什么东西，有没有副作用。
>
> 再想象你看到的是 **"fix: 修复存档加载时空指针崩溃（issue: #42）"** —— 你立刻明白了上下文。
>
> 好的 commit message 是写给**未来的自己和同事**的情书。

### 5.1 格式

```
类型: 简短描述（50 字以内，中文）

详细说明（可选，需要时写）
- 为什么要做这个改动
- 做了什么
- 影响范围

关联 issue（如果有）
```

### 5.2 类型速查表

| 类型 | 含义 | 示例 |
|------|------|------|
| `feat` | 新功能 | `feat: 添加存档/读档功能` |
| `fix` | Bug 修复 | `fix: 修复场景切换时音效丢失` |
| `refactor` | 重构（不改功能） | `refactor: 提取角色状态机为独立模块` |
| `docs` | 文档 | `docs: 更新团队协作指南` |
| `style` | 格式调整（空格、缩进等） | `style: 统一代码缩进风格` |
| `test` | 测试相关 | `test: 添加战斗伤害计算单元测试` |
| `chore` | 构建、工具 | `chore: Git LFS 配置更新` |
| `perf` | 性能优化 | `perf: 优化场景加载中的纹理预加载` |

### 5.3 一个好习惯：原子化提交

- **一个 commit 只做一件事**：不要在一个 commit 里同时"修 bug + 加新功能 + 改格式"
- **能独立运行**：每个 commit 之后，项目应该能正常编译运行
- **写清楚为什么**：不是"做了什么"（代码本身就能看出来），而是"为什么这么做"

> **💡 `git add -p` —— 精确控制每次提交**
>
> 有时候你改了好几个地方，但想把它们拆成多个 commit，每个 commit 专注一件事。`git add -p` 可以让你**交互式地选择每一处改动是否加入暂存区**：
>
> ```bash
> git add -p
> # Git 会展示每一块改动（hunk），询问你：
> # y = 加入暂存区
> # n = 跳过
> # s = 把这块再拆小
> # q = 退出
> ```
>
> 使用方法：先改完所有代码 → 用 `git add -p` 逐块挑选 → 把挑好的 commit → 再 `git add -p` 挑剩下的 → 再 commit。这样就能把一堆改动分门别类地、干净地提交。

---

## 6. Pull Request 规范

> **💡 Pull Request 的本质**
>
> Pull Request（PR）不是 Git 原生功能，而是 GitHub（以及 GitLab、Gitee 等平台）提供的**协作机制**。它的核心作用就一句话：
>
> > **"我改完了，请求你把我的改动拉取（pull）到你的分支里。"**
>
> PR 提供了三个关键价值：
> 1. **可视化 diff**：可以在页面上逐行看到改了什么
> 2. **讨论区**：可以在具体某一行代码上发表评论
> 3. **门禁**：可以设置"必须有人 approve 才能合并"

### 6.1 PR 标题格式

和 commit message 保持一致：

```
类型: 简短描述
```

示例：
- `feat: 存档/读档功能`
- `fix: 修复 NPC 对话跳句问题`

### 6.2 PR 描述模板

创建 PR 时，描述部分填写以下内容：

```markdown
## 改了什么
<!-- 简要描述这个 PR 做了什么改动 -->

## 为什么要这样改
<!-- 说明设计思路，方便 Reviewer 理解你的意图 -->

## 测试方法
<!-- Reviewer 应该如何测试这个改动 -->
1. 打开场景：XXX
2. 操作步骤：XXX
3. 预期结果：XXX

## 截图 / 录屏
<!-- UI 改动请贴上截图或 GIF -->
```

### 6.3 Review 规则

| 规则 | 说明 |
|------|------|
| **谁 Review？** | 另一个人，两人互为 Review 方 |
| **Review 看什么？** | 代码逻辑是否正确、有无明显 bug、是否遵循项目规范、Unity 场景能否正常运行 |
| **如何提修改意见？** | 在 GitHub PR 页面的具体代码行上写评论，不要笼统地说"改一下那个文件" |
| **修改后怎么做？** | 在原分支上 commit → push，PR 会自动更新，不需要重新创建 PR |
| **Approve 条件** | 无阻塞性问题即可 approve，小问题可以 approve 后让作者自己决定是否修 |

### 6.4 合并按钮选择

在 GitHub PR 页面底部，有三种合并方式。**我们选择 "Create a merge commit"**：

| 按钮 | GitHub 名称 | 效果 | 是否采用 |
|------|------------|------|---------|
| **Merge commit** | Create a merge commit | 保留所有 commit 历史，创建一个合并提交 | ✅ **就用这个** |
| Squash and merge | Squash and merge | 把所有 commit 压成一个 | ❌ 暂不用 |
| Rebase and merge | Rebase and merge | 线性历史，改写 commit | ❌ 暂不用 |

> **💡 为什么选择 Merge Commit（`--no-ff`）？**
>
> 我们用 `git merge --no-ff`（no fast-forward）策略，它的效果是**总是创建一个合并提交（merge commit）**，即使可以快进合并。
>
> 对比一下：
>
> **Fast-Forward Merge（快进合并）**：
> ```
> main: A---B
> feat: A---B---C---D
> 合并后 main: A---B---C---D    ← 看不出来 C、D 曾经是一个分支
> ```
>
> **No-Fast-Forward Merge（我们用的）**：
> ```
> main: A---B-------M
>        \         /
> feat:   C---D---E
> 合并后能清楚看到：C、D、E 是一个功能分支，M 是合并点
> ```
>
> 选择 `--no-ff` 的理由：
> 1. **保留功能边界**：一眼就能看出哪些 commit 是哪个功能"团伙"的
> 2. **方便回滚**：要撤销整个功能？`git revert -m 1 M` 一步搞定
> 3. **对 Git LFS 友好**：不会改写二进制文件的引用链
> 4. **历史最诚实**：发生了什么就是什么，不篡改

---

## 7. Push & 合并规则

> **💡 `push` 和 `pull` 到底发生了什么？**
>
> ```
> 本地仓库                          远程仓库 (GitHub)
> ┌──────────┐                     ┌──────────┐
> │ 工作目录  │                     │          │
> │ 暂存区   │  ← git push →      │  main    │
> │ 本地分支  │  ← git fetch ←     │  feat/X  │
> │ 远程追踪  │  ← git pull  ←     │          │
> └──────────┘                     └──────────┘
> ```
>
> - `git push`：把本地 commit **发送**到远程，别人才能看到你的代码
> - `git fetch`：把远程的最新信息**下载**下来，但不会动你的工作区
> - `git pull`：`fetch` + `merge` 的合体，下载远程更新并合并到你当前分支
> - `远程追踪分支`（如 `origin/main`）：Git 在本地保存的一份"远程分支快照"，`git fetch` 会更新它
>
> 理解这些以后你会发现：**`git pull` = `git fetch` + `git merge`**，拆开做更安全，可以先看看远程有啥变化再决定合不合并。

### 7.1 硬性规则

| 规则 | 说明 |
|------|------|
| 🚫 **禁止直接 push 到 main** | main 分支受到 GitHub 分支保护，直接 push 会被拒绝 |
| ✅ **所有改动必须走 PR** | 新功能、Bug 修复、重构、文档，全部通过 PR 合入 main |
| ✅ **PR 必须获得 Approve** | 另一个人必须在 GitHub 上点击 "Approve" 后才能合并 |
| ✅ **合并前先同步 main** | 如果 PR 和 main 有冲突，先在本地解决冲突后再合并 |

### 7.2 合并前检查清单

在点击 "Merge" 按钮之前，确认以下事项：

- [ ] PR 标题和描述完整，清楚说明了改动内容和原因
- [ ] 至少 1 个人 Approve（就是另一位队友）
- [ ] 所有 Review 意见已处理（有修改意见的对话已 resolve）
- [ ] GitHub 页面上显示 **"This branch has no conflicts with the base branch"**
- [ ] 你本人在 Unity 中拉取了最新代码并测试过主流程正常（如果改动涉及核心系统的话）

### 7.3 解决合并冲突

冲突是不可避免的，不需要害怕。它只是表示：**两个人改了同一个文件的同一处地方，Git 不知道该听谁的，需要你做决策**。

> **💡 冲突是怎么产生的？**
>
> Git 的合并本质上是比较三个版本：
> - **Base**：两个分支分叉时的"共同祖先"
> - **Ours**：你当前分支的版本
> - **Theirs**：你要合并进来的版本
>
> 如果两个人改了**不同的地方**（不同文件、或同一文件的不同行），Git 自动合并，没冲突。
> 如果改了**同一个地方**，Git 就举手投降：**"我不知道谁是对的，你自己看吧"** —— 这就是冲突。
>
> Unity 场景文件（`.unity`）和预制体（`.prefab`）特别容易冲突，因为它们内部使用的是 Unity 的 YAML 序列化格式，即使你只移动了一个 GameObject，文件里可能有几十行坐标数据发生变化。**两个人在同一个场景里工作时要多沟通。**

**标准处理流程：**

```bash
# 1. 确保你在 feature 分支上
git checkout feature/你的分支

# 2. 拉取最新 main
git fetch origin main

# 3. 把 main 合并到你的分支（如果有冲突会在这里出现）
git merge origin/main

# 4. 查看哪些文件冲突了
git status

# 5. 打开冲突文件，找到冲突标记：
#    <<<<<<< HEAD
#    你的改动
#    =======
#    main 上的改动
#    >>>>>>> origin/main
#
#    手动编辑，决定保留哪些内容，删除冲突标记

# 6. 标记冲突已解决
git add 冲突文件

# 7. 完成合并
git commit -m "fix: 解决与 main 的合并冲突"

# 8. 推送到 GitHub
git push origin feature/你的分支
```

> **💡 冲突标记速记**
>
> ```
> <<<<<<< HEAD          ← 你当前所在分支的内容（ours）
> int health = 100;
> =======              ← 分界线
> int hp = 100;
> >>>>>>> origin/main   ← 你要合并进来的内容（theirs）
> ```
>
> 你需要决定：保留哪边的？还是两个都要（把代码整合一下）？决定后删掉 `<<<` `===` `>>>` 这三行标记，留下最终的代码。

对于 **Unity 场景/预制体冲突**（`.unity`、`.prefab`），如果冲突复杂到无法在文本编辑器中判断，优先使用以下策略：

```bash
# 策略：选择其中一方的版本，然后在 Unity 中重新做另一方的改动
git checkout --ours Assets/Scenes/场景名.unity    # 保留你的版本
# 或
git checkout --theirs Assets/Scenes/场景名.unity  # 保留 main 的版本
```

---

## 8. 完整实操流程

> 本章是前面所有规范的落地版本。跟着走一遍，你就掌握了完整的协作流程。

### 8.1 从拿到需求到合并的完整步骤

假设你现在拿到一个需求：**"给角色添加生命值系统"**。

#### Step 1：同步最新代码

```bash
# 切换到 main
git checkout main

# 拉取最新
git pull origin main
```

> 为什么从这里开始？因为你要基于**最新的 main** 创建分支。如果你基于几天前的 main 创建分支，到时候合并的时候冲突会更多。

#### Step 2：创建功能分支

```bash
# 从 main 创建并切换到新分支
git checkout -b feature/生命值系统
```

> `git checkout -b 分支名` 等价于：
> ```bash
> git branch 分支名          # 创建分支
> git checkout 分支名        # 切换到分支
> ```

#### Step 3：开发 + 小步提交

在 Unity 中开发，每完成一个小步骤就提交一次：

```bash
# 做完第一步：添加 Health 组件脚本
git add Assets/Scripts/Health.cs
git commit -m "feat: 添加 Health 组件，定义生命值基础属性"

# 做完第二步：UI 显示血条
git add Assets/Scripts/HealthBarUI.cs Assets/Prefabs/HealthBar.prefab
git commit -m "feat: 添加血条 UI，绑定到 Health 组件"

# 做完第三步：受伤逻辑
git add Assets/Scripts/Health.cs Assets/Scripts/DamageSystem.cs
git commit -m "feat: 实现受伤扣血和死亡判定逻辑"
```

> **工作习惯提醒**：每次开始工作前先 `git pull origin main` 看看 main 有没有新东西，有的话及时 `git merge origin/main` 到你的分支，避免分支离 main 越来越远，最后合并时冲突一大堆。

#### Step 4：推送到 GitHub

```bash
# 第一次推送，需要设置上游分支
git push -u origin feature/生命值系统

# 之后在这个分支上再提交，直接 push 就行
git push
```

> `-u` 参数（`--set-upstream`）的作用：让你的本地分支"记住"它对应的远程分支是谁，之后直接用 `git push` / `git pull` 不用再指定远程和分支名。

#### Step 5：在 GitHub 上创建 Pull Request

1. 打开 GitHub 仓库页面
2. 你会看到一个黄色的提示条：**"feature/生命值系统 had recent pushes"**，点击 **"Compare & pull request"**
3. 确保 **base 是 `main`**，**compare 是你的分支**
4. 填写 PR 标题和描述（按[第 6 章](#6-pull-request-规范)的模板）
5. 点击 **"Create pull request"**

#### Step 6：队友 Review

1. 队友在 GitHub 上看到 PR 通知
2. 队友进入 PR 页面，切换到 **"Files changed"** 标签，逐行查看改动
3. 如有疑问，在具体代码行上留言讨论
4. 如有修改意见：
   - 你在本地继续改 → commit → push
   - PR 会自动更新，队友重新检查
5. 队友确认没问题后，点击 **"Review changes" → "Approve"**

#### Step 7：合并到 main

1. 确认满足[合并前检查清单](#72-合并前检查清单)
2. 在 PR 页面点击 **"Merge pull request"**
3. 合并方式选择 **"Create a merge commit"**（默认）
4. 点击 **"Confirm merge"**

#### Step 8：清理工作

合并完成后，GitHub 会提示"是否删除分支"，点击删除。然后回到本地：

```bash
# 切回 main
git checkout main

# 拉取最新（包含刚才合并的内容）
git pull origin main

# 删除本地分支
git branch -d feature/生命值系统

# 清理本地对远程已删除分支的引用
git remote prune origin
```

> `git branch -d` vs `git branch -D`：小写 `-d` 是安全删除，如果分支还没合并到 main，Git 会拒绝删除并提示你；大写 `-D` 是强制删除，无论如何都会删。

### 8.2 日常开发速查卡

```bash
# ====== 开始新功能 ======
git checkout main
git pull origin main
git checkout -b feature/功能名

# ====== 日常提交 ======
git status                          # 看改了啥
git add 文件名                       # 添加到暂存区
git commit -m "类型: 描述"           # 提交
git push                            # 推送到 GitHub

# ====== 同步 main 最新代码 ======
git fetch origin main               # 下载 main 最新
git merge origin/main               # 合并到当前分支

# ====== 查看历史 ======
git log --oneline --graph --all     # 美化版提交历史
git log -p 文件名                    # 查看某个文件的改动历史
git blame 文件名                     # 查看每行代码是谁写的

# ====== 撤销操作 ======
git reset HEAD 文件名                # 取消暂存（unstage）
git checkout -- 文件名               # 撤销文件的未提交改动（危险！）
git revert <commit-id>              # 撤销某个 commit（安全，创建新 commit）
```

> **💡 `git reset` vs `git revert` —— 撤销的两个思路**
>
> - `git reset`：**"时光倒流"**——把 HEAD 指针往回移动，后面的 commit 直接被丢弃。适合还没 push 的本地 commit。**已经 push 过的别用，会让别人崩溃。**
> - `git revert`：**"否定补丁"**——创建一个新的 commit，内容恰好是某个旧 commit 的反操作。安全，因为历史不会被改写，别人 pull 一下就好。
>
> 口诀：**push 之前用 reset，push 之后用 revert。**

### 8.3 分支关系示意图

```
main ───o──────────o──────────o──────────o──────────o  (稳定的真理之源)
         \           \          \          \
          \           \          \          \
feature/A  o──o──o───M          \          \          (A 功能开发完成，合并)
                           \     \          \
feature/B                   o──o──M          \       (B 功能合并)
                                     \        \
feature/C                             o──o──o──M      (C 功能还在开发中)

M = merge commit（合并提交，由 PR 合并产生）
o = 普通 commit
```

---

## 9. Unity 特定操作

### 9.1 在 Unity 中打开项目

1. 启动 Unity Hub
2. 选择 "Add project from disk"
3. 导航到项目目录
4. 确认 Unity 版本选择 **6000.0.75f1**
5. 打开项目

### 9.2 Git LFS 管理

我们在 [`.gitattributes`](.gitattributes) 中配置了 LFS 跟踪规则。以下文件类型走 LFS：

- **图片**：`.png` `.jpg` `.psd` `.tga` 等
- **3D 模型**：`.fbx` `.obj` `.blend` 等
- **音频**：`.wav` `.mp3` `.ogg` 等
- **Unity 资源**：`.unity` `.prefab` `.asset` `.anim` `.mat` 等
- **代码文件**：`.cs` `.json` `.md` 等仍走普通 Git，不走 LFS

> **💡 为什么 Unity 场景和预制体也要用 LFS？**
>
> Unity 的 `.unity` 和 `.prefab` 文件虽然本质是文本（YAML），但它们通常非常大（一个场景几十 MB 很常见），而且多人协作时非常容易产生冲突。用 LFS 管理可以：
> 1. 减少仓库体积，clone 更快
> 2. 配合 Unity 的 **Smart Merge** 工具（UnityYAMLMerge）可以在一定程度上自动解决冲突
>
> 注意：LFS **不能解决冲突问题**，它只是减少仓库体积。冲突还是一样会产生，遵循我们的[冲突处理流程](#73-解决合并冲突)来应对。

### 9.3 Unity 文件注意事项

- **场景文件 (.unity)** 和 **预制体 (.prefab)** 使用 LFS 跟踪
- **两个人尽量不同时修改同一个场景**。如果必须同时改，在修改之前先沟通各自改哪个区域
- 脚本文件 (`.cs`) 普通提交即可
- `Library/`、`Temp/`、`obj/` 等目录已在 `.gitignore` 中，不会被提交

### 9.4 添加新的 LFS 规则

如果后续要添加新类型的资源文件：

```bash
# 跟踪新文件类型
git lfs track "*.新扩展名"

# 提交更新的 .gitattributes
git add .gitattributes
git commit -m "chore: LFS 新增跟踪 *.新扩展名"
```

---

## 10. 常见问题

### 10.1 我把 commit 写到错误的分支了怎么办？

```bash
# 1. 记下你想保留的 commit 的 ID（用 git log 查看）
git log --oneline

# 2. 切到正确的分支
git checkout 正确的分支

# 3. 把那个 commit 摘过来
git cherry-pick <commit-id>

# 4. 回到错误的分支，撤销那个 commit
git checkout 错误的分支
git reset HEAD~1
```

> **💡 `cherry-pick`**：可以"摘取"任意一个 commit 到当前分支，就像摘樱桃一样。它不要求两个分支有共同祖先，非常灵活。

### 10.2 Git LFS 文件没有正确上传

```bash
# 检查 LFS 跟踪状态
git lfs ls-files

# 确认 .gitattributes 配置正确
cat .gitattributes

# 重新推送 LFS 文件
git lfs push origin main --all
```

### 10.3 我 pull 的时候出现 "Please commit your changes or stash them"

这表示你本地有未提交的改动，Git 不敢覆盖你的工作。有两种处理方式：

```bash
# 方案 A：提交改动
git add .
git commit -m "临时保存"
git pull

# 方案 B：暂存改动（详见第 4 章的 git stash 知识）
git stash
git pull
git stash pop
```

### 10.4 我想放弃所有本地改动，回到和远程一样的状态

```bash
git fetch origin
git reset --hard origin/main
```

⚠️ **这是不可逆的操作**，所有本地未 push 的改动会永久丢失。

### 10.5 我 push 被拒绝了（rejected）

通常是因为远程分支有你本地没有的新 commit：

```bash
# 先拉取远程更新
git pull origin 你的分支

# 如果有冲突，解决后：
git add 冲突文件
git commit -m "fix: 解决合并冲突"

# 再 push
git push origin 你的分支
```

### 10.6 Unity 场景合并后打不开了

这是 Unity 场景文件（`.unity`）冲突处理不当导致的。如果你不确定怎么手动解冲突：

```bash
# 回到合并前的状态
git merge --abort

# 和队友沟通：谁改了这个场景的哪个部分
# 选择其中一个人的版本作为基础：
git checkout --ours Assets/Scenes/场景.unity     # 你的版本
# 或
git checkout --theirs Assets/Scenes/场景.unity   # 别人的版本

# 在 Unity 中重新做另一方的改动
```

---

## 附录：Git 命令速查表

| 命令 | 作用 |
|------|------|
| `git status` | 查看当前状态（改了哪些文件、在哪个分支） |
| `git log --oneline --graph --all` | 查看所有分支的提交历史图 |
| `git diff` | 查看未暂存的改动内容 |
| `git diff --staged` | 查看已暂存但未提交的改动内容 |
| `git branch` | 列出本地分支 |
| `git branch -a` | 列出本地 + 远程所有分支 |
| `git checkout -b 分支名` | 创建新分支并切换过去 |
| `git add 文件` | 将文件加入暂存区 |
| `git add -p` | 交互式选择改动加入暂存区 |
| `git commit -m "消息"` | 提交暂存区内容 |
| `git push` | 推送到远程 |
| `git push -u origin 分支名` | 首次推送并设置上游 |
| `git fetch origin` | 下载远程更新，不合并 |
| `git pull origin main` | 下载 main 更新并合并 |
| `git merge 分支名` | 将指定分支合并到当前分支 |
| `git branch -d 分支名` | 安全删除本地分支 |
| `git stash` | 暂存未提交的改动 |
| `git stash pop` | 恢复最近一次 stash |
| `git revert <id>` | 撤销某个 commit（安全） |
| `git reset HEAD 文件` | 取消暂存 |
| `git cherry-pick <id>` | 将某个 commit 摘到当前分支 |
| `git blame 文件` | 查看文件每行的修改记录 |
| `git reflog` | 查看所有 HEAD 移动记录（救命用） |

> **💡 `git reflog` —— 你的后悔药**
>
> 如果你不小心执行了 `git reset --hard` 或 `git rebase`，导致一些 commit "消失"了，别慌。Git 几乎不会真正删除数据（至少 30 天内），`git reflog` 记录了 HEAD 的每一次移动。
>
> ```bash
> git reflog
> # 输出类似：
> # abc1234 HEAD@{0}: commit: feat: 添加血条
> # def5678 HEAD@{1}: reset: moving to HEAD~1
> # ...
>
> # 找到你想恢复的那个 commit，然后：
> git checkout -b 恢复分支 abc1234
> ```
>
> 只要你知道 commit 的哈希值，它就还在，只是可能"看不到"而已。`git reflog` 让你重新找到它。

---

> **最后的话**
>
> 这份文档会随着项目的推进不断迭代。如果你在使用过程中发现任何不合理的地方、或者想到了更好的做法，随时修改它——文档和代码一样，也需要持续维护。
>
> Git 是一个很深但很值得学的工具。一开始不熟悉是正常的，多用、多犯错、多查文档，慢慢就会变成肌肉记忆。**最重要的是：不要害怕，有 `git reflog` 在，你几乎永远丢不了代码。** 🎮
