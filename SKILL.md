---
name: install-skills
description: Install agent skill packs into all 5 agent hosts (Claude, Codex, Gemini, Kiro, .agents) from eight entry points — GitHub repos, local paths, post-install sync, standalone catalog refresh, provenance investigation, version check, batch update, or cleanup. Trigger when the user provides a GitHub URL or local path and says "install this", "add this skill", "装这个", "把这个装上", "把这个仓库的 skill 都装上", or "add these skills". Also trigger when the user says "我下载了一个 skill 包", "装一下这个目录", "这个文件夹里有 skill", provides a local folder/ZIP path, or mentions they downloaded skills from GitHub manually. Also trigger AFTER `npx skills add` or `find-skills` installs a skill into Claude only — detect new skills and sync to other hosts. Also trigger when the user says "更新目录", "刷新 catalog", "生成 installed", "refresh catalog", "update catalog", or wants to regenerate SKILLS-CATALOG.md and INSTALLED.md without installing new skills. Also trigger when the user says "溯源", "排查来源", "查来路", "trace origin", "find source", "这些 skill 哪来的", "哪些 skill 没有来源", or wants to investigate unknown/unattributed skills. Also trigger when the user says "检查更新", "check updates", "哪些 skill 过时了", "skill 有新版吗", "update check", or wants to check if installed skills have newer versions available. Also trigger when the user says "批量更新", "全部更新", "update all", or wants to update all outdated skills at once. Also trigger when the user says "清理", "清理冗余", "删除重复", "clean up", "remove duplicates", or wants to detect and remove redundant/obsolete skills. Handles conflict resolution, prefix naming, multi-host sync, marketplace detection, provenance investigation, version tracking via .origin.json, batch update, redundancy cleanup, SKILLS-CATALOG.md updates, and per-host INSTALLED.md generation.
allowed-tools:
  - Bash
  - Read
  - Write
  - WebSearch
  - WebFetch
---

# 从 GitHub 安装技能包

将任意 GitHub 仓库中的技能批量安装到全部 5 个 agent host。

## Agent Host 目录

| Host | 路径 |
|------|------|
| Claude | `~/.claude/skills/` |
| Codex | `~/.codex/skills/` |
| Gemini | `~/.gemini/antigravity/skills/` |
| Kiro | `~/.kiro/skills/` |
| .agents | `~/.agents/skills/` |

## 工作流

本 skill 有八种入口。根据触发场景自动选择：

| 入口 | 触发场景 | 流程概述 |
|------|---------|---------|
| **A. GitHub 安装** | 用户给 GitHub URL 或说"装这个" | marketplace 检测 → clone → 冲突检查 → 安装 → .origin.json → 更新目录 |
| **B. Claude 同步** | `npx skills add` 后同步到其他 host | 检测新 skill → Kiro 用 `cp -r`，其余符号链接到 3 host → 更新目录 |
| **C. 本地安装** | 用户给本地路径或 ZIP | 定位 SKILL.md → 复用入口 A 流程 |
| **D. 刷新目录** | "更新目录"、"refresh catalog" | 扫描 → 重建 CATALOG + INSTALLED.md |
| **E. 溯源排查** | "溯源"、"trace origin" | 三级搜索 → 归类来源 → 更新 CATALOG。详见 [references/advanced-entries.md](references/advanced-entries.md) |
| **F. 版本检查** | "检查更新"、"check updates" | 从溯源表提取 URL → 对比 content hash → 汇报。详见 [references/advanced-entries.md](references/advanced-entries.md) |
| **G. 批量更新** | "全部更新"、"update all" | 按仓库分组 clone → 覆盖 → .origin.json → 同步。详见 [references/advanced-entries.md](references/advanced-entries.md) |
| **H. 清理冗余** | "清理"、"clean up" | 检测前缀副本/重复/远程已删 → 确认 → 删除。详见 [references/advanced-entries.md](references/advanced-entries.md) |

跨平台兼容、仓库结构检测、常见踩坑见 [references/shared-platform.md](references/shared-platform.md)。

---

### 入口 A：从 GitHub 仓库安装（完整流程）

#### 0. Marketplace 检测

克隆之前，用 WebFetch 读取仓库 README，搜索 `/plugin marketplace add`、`npx skills add` 等模式。

找到 → Claude 走官方 marketplace，其他 4 host 用 `cp -r` 独立副本（Kiro 始终用 `cp -r`），跳到步骤 5。
未找到 → 继续常规流程。

#### 1. 克隆并发现技能

```bash
git clone --depth 1 <repo-url> /tmp/<repo-name>
find /tmp/<repo-name> -name "SKILL.md" -exec dirname {} \; | xargs -I{} basename {} | sort
```

汇报技能数量、目录结构。克隆失败则建议用入口 C。无 SKILL.md 则停止。

#### 2. 冲突检查

扫描**所有 host 目录**，对比技能名。有冲突则询问：覆盖 / 跳过 / 共存（加前缀）。

#### 3. 命名策略

询问是否加前缀（如 `pm-`）。前缀统一应用到所有 host。

#### 4. 安装到全部 5 个 host

Claude 用 `cp -r` 实体复制，Kiro 用 `cp -r` 实体复制（不支持 symlink），其他 3 host 用符号链接指向 Claude。

**Windows 注意**：用 Python `os.symlink(source, target, target_is_directory=True)` 替代 `ln -s`。

仓库结构检测详见 [references/shared-platform.md](references/shared-platform.md)。

#### 4a. 生成 .origin.json

为每个新 skill 生成版本身份文件。Schema 详见 [references/origin-schema.md](references/origin-schema.md)。

```python
origin = {
    "name": skill_name,
    "source": {"type": "github", "repo": repo_url, "author": author},
    "version": {
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "commit_hash": commit[:7],
        "content_hash": "sha256:" + sha256(skill_md)[:16],
        "remote_ref": "main"
    },
    "checks": {}
}
```

#### 5. 更新技能目录

**关键环节。每个新技能必须写入 CATALOG，否则 INSTALLED.md 回退到低质量英文描述。**

**⚠️ 强制约束：CATALOG 必须严格遵循 [references/catalog-skeleton.md](references/catalog-skeleton.md) 骨架模板。以下结构元素缺一不可：**

1. **头部元信息**：`最后更新` 日期、`总计` 技能数、`调用方式`
2. **目录索引**：所有分类章节 + 溯源表的锚点链接
3. **技能来源总览表**：五列（阵营 | 作者/组织 | 技能数 | 许可证 | 说明）
4. **分类章节**：每个章节必须是四列表（技能 | 用途 | 来源 | 触发场景），禁止两列
5. **溯源表**：按作者分组 + 社区独立作者 + 来源未明 + 用户自建，四个子章节齐全
6. **标记说明**：标记含义表
7. **快速选择指南**：决策树格式
8. **维护说明**：末尾维护仪式提醒

**新建 CATALOG 时**：按骨架模板完整初始化所有结构元素。
**更新 CATALOG 时**：检查上述 8 项是否齐全，缺失的立即补全。

具体更新步骤：

1. **读取 CATALOG 结构**：头部总计、分类章节、溯源表
2. **生成四列中文条目**：`| 技能名 | 用途（≤30字中文） | [作者](URL) | 触发场景 |`
3. **插入正确分类章节**（匹配不上则放「工具与基础设施」）
4. **更新溯源表**（独立作者 → 社区表；技能包 4+ → 新建子章节）
5. **更新头部总计**
6. **运行 gen_installed.py**（必须先更新 CATALOG 再运行）
7. **验证**：检查 CATALOG 中有新技能、INSTALLED.md 描述为中文、总计数一致、分类表为四列、骨架结构完整（8 项必备元素齐全）

骨架模板见 [references/catalog-skeleton.md](references/catalog-skeleton.md)。

#### 6. 汇报

新增数、覆盖数、跳过数、每个 host 状态、来源 URL。

#### 7. 清理

`rm -rf /tmp/<repo-name>`

---

### 入口 B：从 Claude 同步到其他 host

1. **检测新技能**：从 `npx skills add` 输出或用户指定的技能名
2. **同步**：对 Kiro 用 `cp -r` 实体复制，对其他 host 创建符号链接指向 Claude 目录
3. **更新目录**：同入口 A 步骤 5
4. **溯源提示**（可选）：如有来源未明的 skill，提示跳转入口 E

---

### 入口 C：从本地目录/ZIP 安装

1. **定位**：ZIP 先解压；搜索 SKILL.md
2. **后续**：走入口 A 步骤 2-7。清理时只删解压临时目录，不删用户原始目录。

---

### 入口 D：刷新技能目录

1. **生成 INSTALLED.md**：`python ~/.claude/skills/install-skills/scripts/gen_installed.py`
2. **更新 CATALOG**：同入口 A 步骤 5 的更新逻辑
3. **版本检查提示**（可选）：有远程来源的 skill 超过 7 天未检查 → 提示入口 F
4. **汇报**：host 数、skill 数、更新了哪些章节
5. **溯源提示**（可选）：有来源未明的 skill → 提示入口 E

---

### 入口 E/F/G/H：高级入口

详细步骤见 [references/advanced-entries.md](references/advanced-entries.md)。

**入口 E 溯源排查**：三级搜索（GitHub → Marketplace → find-skills）追踪来路不明的 skill。

**入口 F 版本检查**：从 CATALOG 溯源表提取 URL（非分类表），按仓库分组对比 content hash。大仓库 clone 批量对比，小仓库 HTTP 逐个检查。

**入口 G 批量更新**：基于入口 F 结果，按仓库分组 clone → 覆盖 → 生成 .origin.json → 同步。排除 install-skills 自身。

**入口 H 清理冗余**：检测前缀副本、内容重复、远程已删除的 skill。检查仓库调度配置后确认删除。

---

## 关键模式

### 冲突处理

| 场景 | 默认动作 |
|------|---------|
| 同名不同仓库 | 询问用户 |
| 同名同仓库（更新） | 覆盖 |
| 新技能无冲突 | 直接安装 |
