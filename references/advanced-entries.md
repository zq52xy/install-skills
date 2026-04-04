# 高级入口（E/F/G/H）

本文件包含 install-skills 的低频入口详细步骤。由 SKILL.md 按需引用。

---

## 入口 E：溯源排查（调查来路不明的 skill）

当用户说"溯源"、"排查来源"、"查来路"、"trace origin"、"find source"、"这些 skill 哪来的"时走此流程。也可由入口 B/D 末尾的溯源提示触发。

### 0. 扫描未归属技能

从 SKILLS-CATALOG.md 和实际 skill 目录中识别需要排查的技能：

```bash
CLAUDE_SKILLS="$HOME/.claude/skills"

# 方法 1: 找溯源表中「来源未明」章节下的技能
grep -A 100 '### 来源未明' ~/.claude/skills/SKILLS-CATALOG.md | grep '^\`' | sed 's/`//g'

# 方法 2: 找不在溯源表中的技能（CATALOG 中无来源链接）
for skill_dir in "$CLAUDE_SKILLS"/*/; do
  skill_name=$(basename "$skill_dir")
  [ -f "$skill_dir/SKILL.md" ] || continue
  if ! grep -q "\`$skill_name\`.*\[.*\](https://github.com" ~/.claude/skills/SKILLS-CATALOG.md 2>/dev/null; then
    echo "UNKNOWN: $skill_name"
  fi
done
```

汇报发现的未归属技能列表，确认后开始逐个排查。

### 1. 三级搜索（按优先级依次执行）

#### 1a. GitHub 搜索（优先级最高）

搜索策略：
```
1. "<skill-name>" SKILL.md filename:SKILL.md
2. "<skill-name>" "claude" skill
3. "<skill-name>" site:github.com skill
```

**匹配验证**：找到候选仓库后，用 WebFetch 读取其 SKILL.md，对比 `name` 字段完全匹配、`description` 语义相似、目录结构一致。

#### 1b. Marketplace 搜索（优先级中）

通过 `npx skills search <skill-name>` 或 WebSearch 搜索 skillsmp.com / skills.sh。

#### 1c. find-skills 搜索（优先级低）

如果用户安装了 `find-skills` skill，触发 `find <skill-name>` 搜索。

#### 1d. 搜索穷尽

三级搜索都未找到来源，标记为「用户自建」。

### 2. 更新 SKILLS-CATALOG.md

**找到来源的 skill：**
1. 从「来源未明」移除
2. 插入正确位置（已有作者 → 追加；新作者 1-3 skill → 社区独立作者表；新作者 4+ → 新建子章节）
3. 更新分类表来源列

**确认为用户自建的 skill：**
1. 添加到「用户自建」章节
2. 分类表来源列标记为 `自建`

### 3. 生成/更新 INSTALLED.md

溯源完成后运行 `python ~/.claude/skills/install-skills/scripts/gen_installed.py`

### 4. 汇报排查结果

输出溯源报告：排查总数、找到来源数、确认自建数。

---

## 入口 F：版本检查（检测已安装 skill 是否有新版）

当用户说"检查更新"、"check updates"、"哪些 skill 过时了"、"skill 有新版吗"时走此流程。

### 0. 构建来源映射

**来源地址优先从 SKILLS-CATALOG.md 的溯源表（而非分类表）提取**。溯源表中每个来源块包含 GitHub URL 和对应的 skill 列表。

**注意：分类表的来源列可能为空或不完整。溯源表才是来源地址的 Single Source of Truth。**

`.origin.json` 仅提供版本锚点（commit_hash、content_hash）作为精确对比的增强。

**设计原则：SKILLS-CATALOG.md 是来源地址的 Single Source of Truth，`.origin.json` 是版本状态的 Single Source of Truth。两者各司其职，互不替代。**

### 1. 远程版本检查

**性能关键**：同一仓库的多个 skill 按仓库分组。4+ skill 的仓库用 `git clone --depth 1` 一次批量对比，3 个以下用 HTTP 逐个检查。

**对比策略：**

| 有 .origin.json | 对比方式 | 精度 |
|-----------------|---------|------|
| 有 commit_hash | 远程 commit vs 本地 commit → 不同则比 content_hash | 最高 |
| 仅 content_hash | 远程 vs 本地 content_hash | 高 |
| 无 .origin.json | 远程 vs 本地 SKILL.md 直接 diff | 可用但无法判断方向 |

**判定逻辑：**

| 本地 hash | 远程 hash | .origin.json | 结论 |
|-----------|-----------|--------------|------|
| 相同 | 相同 | — | ✅ 已是最新 |
| 不同 | — | 本地 = 安装时 | ⬆️ 远程有新版 |
| 不同 | — | 本地 ≠ 安装时 | ⚠️ 双向变更 |
| — | — | 无 | 🔍 有差异待确认 |

### 2. 更新 .origin.json

检查完成后更新 `checks` 字段：`last_checked`、`last_result`（up-to-date / update-available / local-modified / check-failed）。

### 3. 汇报 + 用户决策

输出版本检查报告，对「有新版可用」的 skill 提供：更新 / 跳过 / 查看变更 / 全部更新。

对本地有修改的 skill 额外警告"更新会覆盖本地修改"。

---

## 入口 G：批量更新（基于入口 F 结果）

当用户选择"全部更新"或说"批量更新"、"update all"时走此流程。

### 0. 前置条件

需要入口 F 的检查结果。如果没有，先运行入口 F。

### 1. 按仓库分组

将待更新的 skill 按 GitHub 仓库 URL 分组。同一仓库只 clone 一次。

### 2. 逐仓库执行更新

```
for each repo_url, skills in grouped_updates:
    1. git clone --depth 1 repo_url → tmp_dir
    2. for each skill:
        a. find_skill_md(tmp_dir, skill_name)  # 仓库结构自动检测
        b. force_remove_dir(local_skill_dir)    # 跨平台兼容删除
        c. cp -r remote → local（跳过 .git）
        d. generate .origin.json
        e. sync_to_hosts(skill_name)
    3. rm -rf tmp_dir
```

### 3. 排除自身

`install-skills` 自身在更新列表中时跳过——更新会删除正在执行的脚本。用户应通过 `git pull` 手动更新。

### 4. 汇报

成功数、失败数、已同步到哪些 host。

---

## 入口 H：清理冗余（检测并删除过时 skill）

当用户说"清理"、"清理冗余"、"删除重复"、"clean up"时走此流程。

### 0. 扫描冗余类型

| 类型 | 检测方法 | 示例 |
|------|---------|------|
| **前缀版副本** | 同一仓库的 `prefix-name` 和 `name` 都存在 | `gstack-qa` + `qa` |
| **内容完全相同的副本** | 不同名字但 content_hash 一致 | `gstack-2` = `gstack-upgrade` |
| **远程已删除** | 溯源表有来源但远程仓库中已不存在 | 仓库重构后删除的旧 skill |

### 1. 前缀版清理

1. 检查仓库的 skill 调度机制（如 gstack 的 `skill_prefix` 配置）
2. 确定用户实际使用的版本
3. 如果前缀版有独有 skill，先从远程安装无前缀版，再删前缀版

### 2. 执行清理

对每个待删除的 skill，用 `force_remove_dir` 从所有 host 删除，更新 CATALOG。

### 3. 汇报

列出删除了什么、保留了什么、CATALOG 更新了哪些条目。
