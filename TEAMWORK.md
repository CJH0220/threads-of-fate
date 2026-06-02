# 《命运的织线》—— 团队协作操作指南

> 最后更新：2026-06-02

---

## 项目信息

- **项目名称**：命运的织线 (Threads of Fate)
- **项目位置**：`C:\dev\game1`
- **Unity 版本**：6000.0.75f1
- **协作方式**：Git + Git LFS
- **开发环境**：Unity Editor + Claude Code (WSL)

---

## 快速开始

### 初次设置

```bash
# 1. 在 WSL 中进入项目目录
cd /mnt/c/dev/game1

# 2. 初始化 Git 仓库（如果还未初始化）
git init

# 3. 安装 Git LFS（如果未安装）
# Windows：从 https://git-lfs.github.com/ 下载安装
# WSL：
sudo apt install git-lfs

# 4. 初始化 Git LFS
git lfs install

# 5. 配置 LFS 跟踪 Unity 特定文件
git lfs track "*.png"
git lfs track "*.jpg"
git lfs track "*.jpeg"
git lfs track "*.gif"
git lfs track "*.psd"
git lfs track "*.fbx"
git lfs track "*.wav"
git lfs track "*.mp3"
git lfs track "*.ogg"
git lfs track "*.unity"
git lfs track "*.prefab"
git lfs track "*.asset"
git lfs track "*.anim"
git lfs track "*.controller"
git lfs track "*.mat"

# 6. 保存 LFS 配置
git add .gitattributes

# 7. 配置用户信息（如果未配置）
git config user.name "你的名字"
git config user.email "你的邮箱"
```

---

## 日常工作流程

### 上传/同步代码

```bash
# 1. 拉取最新更改
git pull origin main

# 2. 查看状态
git status

# 3. 添加更改的文件
# 添加所有更改（谨慎使用）
git add .

# 或选择性添加
git add file1.cs file2.cs

# 4. 提交
git commit -m "feat: 实现命运的织线界面"

# 5. 推送到远程仓库
git push origin main
```

### 从远程同步

```bash
# 拉取并合并最新更改
git pull origin main

# 或先 fetch 再 merge（更安全）
git fetch origin
git merge origin/main
```

---

## Unity 特定操作

### 在 Unity 中打开项目

1. 启动 Unity Hub
2. 选择 "Add project from disk"
3. 导航到 `C:\dev\game1`
4. 确认 Unity 版本选择 6000.0.75f1
5. 打开项目

### Unity 文件注意事项

- **场景文件 (.unity)** 和 **预制体 (.prefab)** 使用 LFS 跟踪
- 大型资源文件（贴图、模型、音频）务必使用 LFS
- 脚本文件 (.cs) 普通提交即可
- `Library/`、`Temp/`、`obj/` 等目录已在 `.gitignore` 中

---

## 分支策略

```bash
# 创建新功能分支
git checkout -b feature/织线交互系统

# 完成功能后合并回主分支
git checkout main
git merge feature/织线交互系统

# 删除已合并的分支
git branch -d feature/织线交互系统
```

---

## 常见问题

### Git LFS 文件未上传

```bash
# 检查 LFS 状态
git lfs ls-files

# 强制上传所有 LFS 文件
git lfs push origin main --all
```

### 冲突解决

```bash
# 发生冲突时
git status  # 查看冲突文件
# 手动编辑解决冲突标记 <<<<< >>>>>
git add 冲突文件
git commit
```

### Unity 场景损坏

```bash
# 从 Git 恢复
git checkout HEAD -- Assets/Scenes/场景文件.unity
```

---

## 远程仓库设置

```bash
# 添加远程仓库（示例：GitHub）
git remote add origin https://github.com/用户名/threads-of-fate.git

# 或使用 SSH
git remote add origin git@github.com:用户名/threads-of-fate.git

# 查看远程仓库
git remote -v
```

---

## 项目约定

### 提交消息格式

```
类型: 简短描述

详细说明（可选）

类型包括：
- feat: 新功能
- fix: 修复
- docs: 文档
- refactor: 重构
- test: 测试
- chore: 构建/工具
```

### 代码规范

- C# 类名使用 PascalCase
- 私有字段使用 _camelCase
- 公共字段/属性使用 PascalCase
- 文件名与类名匹配

---

## Claude Code 使用

```bash
# 在 WSL 中使用 Claude Code
cd /mnt/c/dev/game1
# 直接运行 Claude Code 命令
```

---

## 下一步

- [ ] 初始化 Git 仓库
- [ ] 配置 Git LFS
- [ ] 创建远程仓库（GitHub/GitLab）
- [ ] 添加团队成员
- [ ] 开始游戏开发

---

## 联系信息

- 项目负责人：[待填写]
- 团队成员：[待填写]
- 通讯方式：[待填写]