---
name: install-skills
description: Install agent skill packs into all 6 agent hosts (Claude, Codex, Gemini, Kiro, Cursor, .agents) from six entry points — GitHub repos, local paths, post-install sync, standalone catalog refresh, provenance investigation, or version check. Trigger when the user provides a GitHub URL or local path and says "install this", "add this skill", "装这个", "把这个装上", "把这个仓库的 skill 都装上", or "add these skills". Also trigger when the user says "我下载了一个 skill 包", "装一下这个目录", "这个文件夹里有 skill", provides a local folder/ZIP path, or mentions they downloaded skills from GitHub manually. Also trigger AFTER `npx skills add` or `find-skills` installs a skill into Claude only — detect new skills and sync to other hosts. Also trigger when the user says "更新目录", "刷新 catalog", "生成 installed", "refresh catalog", "update catalog", or wants to regenerate SKILLS-CATALOG.md and INSTALLED.md without installing new skills. Also trigger when the user says "溯源", "排查来源", "查来路", "trace origin", "find source", "这些 skill 哪来的", "哪些 skill 没有来源", or wants to investigate unknown/unattributed skills. Also trigger when the user says "检查更新", "check updates", "哪些 skill 过时了", "skill 有新版吗", "update check", or wants to check if installed skills have newer versions available. Handles conflict resolution, prefix naming, multi-host sync, marketplace detection, provenance investigation, version tracking via .origin.json, SKILLS-CATALOG.md updates, and per-host INSTALLED.md generation.
---

# 从 GitHub 安装技能包

将任意 GitHub 仓库中的技能批量安装到全部 6 个 agent host。

## Agent Host 目录

| Host | 路径 |
|------|------|
| Claude | `~/.claude/skills/` |
| Codex | `~/.codex/skills/` |
| Gemini | `~/.gemini/antigravity/skills/` |
| Kiro | `~/.kiro/skills/` |
| Cursor | `~/.cursor/skills/` |
| .agents | `~/.agents/skills/` |

## 工作流

本 skill 有六种入口：**A. 从 GitHub 仓库安装**（完整流程）、**B. 从 Claude 同步到其他 host**（轻量流程）、**C. 从本地目录/ZIP 安装**（手动下载场景）、**D. 刷新技能目录**（独立生成 SKILLS-CATALOG 和 INSTALLED.md）、**E. 溯源排查**（调查来路不明的 skill 并归类）、**F. 版本检查**（检测已安装 skill 是否有新版）。根据触发场景自动选择。

---

### 入口 A：从 GitHub 仓库安装（完整流程）

当用户提供 GitHub URL 或说"装这个"时走此流程。

#### 0. Marketplace 检测（前置步骤）

**在克隆之前**，先检查该仓库是否支持 Claude Code marketplace 一键安装。

检测方法：用 WebFetch 或 `gh api` 读取仓库 README，搜索以下模式：

```
/plugin marketplace add <author>/<repo>
npx @anthropic-ai/claude-code-skill install <url>
npx skills add <skill-name>
```

**如果找到 marketplace 安装命令：**
1. 告知用户"该仓库支持 marketplace 安装，Claude 优先使用官方渠道"
2. **Claude**：执行检测到的 marketplace 命令（如 `/plugin marketplace add author/repo`）
3. **其他 5 host**：正常 `git clone --depth 1` + `cp -r` 安装独立副本（不用符号链接）
4. 跳到步骤 5（更新技能目录）

这样 Claude 走官方渠道（可获取更新），其他 host 走文件副本（独立稳定）。两边互不干扰。

**如果未找到：** 继续入口 A 的常规流程（克隆 → 符号链接安装全部 6 host）。

#### 1. 克隆并发现技能

```bash
git clone --depth 1 <repo-url> /tmp/<repo-name>
find /tmp/<repo-name> -name "SKILL.md" -exec dirname {} \; | xargs -I{} basename {} | sort
```

汇报：技能数量、目录结构、是否有 `references/` 或 `scripts/` 子目录。

**如果克隆失败**（网络问题、仓库不存在、需要认证），报告错误并建议用户手动克隆后提供本地路径。

**如果仓库中没有 SKILL.md**，停止并告知用户"这不是一个 skills 仓库"。

#### 2. 冲突检查

扫描**所有存在的 host 目录**（不仅是 Claude），对比发现的技能名。

如果有冲突，询问用户：
- **覆盖**：用新版替换现有版本
- **跳过**：保留现有版本，跳过冲突的
- **共存**：给新技能加前缀

#### 3. 命名策略

询问用户是否需要加前缀（如 `pm-` 代表产品经理类技能）。以下情况建议加前缀：
- 仓库中有通用名称可能冲突（如 `pricing-strategy`）
- 用户希望按领域分组方便 tab 补全

**前缀统一应用到所有 host** — 绝不只改一个 host。

#### 4. 安装到全部 6 个 host

以 Claude 为源，先 `cp -r` 安装到 Claude，其他 5 个 host 用**符号链接**指向 Claude 目录。这样改一处全局生效，不产生冗余副本。

```bash
PREFIX=""  # 不加前缀留空，加前缀填值如 "pm-"
CLAUDE_SKILLS="$HOME/.claude/skills"

SYNC_TARGETS=(
  "$HOME/.codex/skills"
  "$HOME/.gemini/antigravity/skills"
  "$HOME/.kiro/skills"
  "$HOME/.cursor/skills"
  "$HOME/.agents/skills"
)

# 第一步：安装到 Claude（实体复制）
for skill_dir in /tmp/<repo-name>/skills/*/; do
  skill_name=$(basename "$skill_dir")
  cp -r "$skill_dir" "$CLAUDE_SKILLS/${PREFIX}${skill_name}"
done

# 第二步：其他 host 创建符号链接指向 Claude
for skill_dir in /tmp/<repo-name>/skills/*/; do
  skill_name=$(basename "$skill_dir")
  target_name="${PREFIX}${skill_name}"
  for host in "${SYNC_TARGETS[@]}"; do
    [ -d "$host" ] || continue
    # 删除旧的（无论是副本还是旧链接）
    rm -rf "$host/$target_name"
    # 创建符号链接
    ln -s "$CLAUDE_SKILLS/$target_name" "$host/$target_name"
  done
done
```

**设计原则：Claude 目录是唯一源（Single Source of Truth），其他 host 是符号链接消费者。**

**Windows 注意：** Git Bash 的 `ln -s` 在 Windows 上实际创建的是副本而非真正的符号链接。用 Python 替代：

```python
import os, shutil
os.symlink(source_path, target_path, target_is_directory=True)
```

根据仓库结构调整源路径——有些用 `skills/`，有些用 `category/skills/` 嵌套。

#### 4a. 生成 .origin.json（版本身份文件）

安装完成后，为每个新 skill 在 Claude 目录下生成 `.origin.json`，记录来源和版本锚点。

```python
import json, hashlib, os
from datetime import datetime, timezone

def generate_origin(skill_dir, repo_url, author, clone_dir):
    """为单个 skill 生成 .origin.json"""
    skill_md = os.path.join(skill_dir, 'SKILL.md')

    # content hash: SKILL.md 的 SHA-256 前 16 位
    with open(skill_md, 'rb') as f:
        content_hash = 'sha256:' + hashlib.sha256(f.read()).hexdigest()[:16]

    # commit hash: 从克隆目录获取
    commit_hash = os.popen(f'git -C {clone_dir} rev-parse HEAD').read().strip()[:7]

    origin = {
        "name": os.path.basename(skill_dir),
        "source": {
            "type": "github",
            "repo": repo_url,
            "author": author
        },
        "version": {
            "installed_at": datetime.now(timezone.utc).isoformat(),
            "commit_hash": commit_hash,
            "content_hash": content_hash,
            "remote_ref": "main"
        },
        "checks": {}
    }

    with open(os.path.join(skill_dir, '.origin.json'), 'w') as f:
        json.dump(origin, f, indent=2, ensure_ascii=False)
```

**对于 marketplace 安装的 skill**：`source.type` 设为 `"marketplace"`，`source.marketplace` 填写平台名。

**对于本地安装（入口 C）**：`source.type` 设为 `"local"`，无 `commit_hash`。

Schema 详见 [references/origin-schema.md](references/origin-schema.md)。

#### 5. 更新技能目录（精确算法）

**此步骤是安装流程中最关键的环节。每一个新技能都必须被写入 CATALOG，否则 INSTALLED.md 会回退到低质量的英文截断描述。**

##### 5a. 读取 SKILLS-CATALOG.md 现有结构

```bash
# 读取 Claude 的 CATALOG
cat ~/.claude/skills/SKILLS-CATALOG.md
```

识别以下结构元素：
- **头部总计行**：`> **总计**: N 技能` — 记住当前数字 N
- **分类章节列表**：所有 `## N. 章节名` 标题
- **来源总览表**：`## 技能来源总览` 下的表格
- **溯源表**：`## N. 技能来源溯源表` 下的内容

##### 5b. 为每个新技能生成中文条目

**对每个新安装的技能，读取其 SKILL.md，生成以下格式的表格行：**

```markdown
| `技能名` | 中文一句话用途（≤30字） | [作者](GitHub URL) | 中文触发场景 |
```

**关键要求：**
- **用途列**必须是**中文**，不超过 30 字，说清技能干什么
- **来源列**必须带 GitHub 链接
- **触发场景列**用中文描述何时使用
- 从 SKILL.md 的 `description` 字段和正文摘取信息，翻译为中文

**示例：**
```markdown
| `autoresearch` | 自主改进引擎：反复修改→验证→保留/丢弃 | [uditgoenka](https://github.com/uditgoenka/autoresearch) | "improve this", "iterate until done" |
| `autoresearch-skill` | 自主优化 skill prompt（二元评估+变异循环） | [olelehmann](https://github.com/olelehmann100kMRR/autoresearch-skill) | "optimize this skill", "run autoresearch on" |
```

##### 5c. 插入到正确的分类章节

**匹配算法：**

1. 读取所有现有章节标题（如"设计与 UI/UX"、"调试与排错"、"工具与基础设施"）
2. 根据新技能的功能领域，选择最匹配的章节
3. 在该章节的表格末尾（`---` 分隔线之前）插入新行
4. 如果没有匹配的章节，插入到「工具与基础设施」章节

**匹配参考：**
| 技能领域 | 应插入章节 |
|----------|-----------|
| 自动化/迭代/优化 | 工具与基础设施 |
| 安全/审计 | 安全与防护 |
| 调试/修复 | 调试与排错 |
| 文档/学习 | 文档与内容 |
| 设计/UI | 设计与 UI/UX |
| 部署/发布 | DevOps 与部署 |

##### 5d. 更新溯源表

在 `## N. 技能来源溯源表` 章节中，按以下格式添加新来源：

**如果是独立作者（1-3 个技能）：**
在「社区独立作者」表格中添加行：
```markdown
| `技能名` | **作者名** | [GitHub URL](URL) |
```

**如果是技能包（4+ 个技能）：**
新建一个子章节：
```markdown
### 来源名 (N 技能)

许可证：MIT | 来源：[repo](GitHub URL)

```
skill-a, skill-b, skill-c
```
```

##### 5e. 更新头部总计

找到 `> **总计**: N 技能` 行，将 N 替换为新的总数（原数 + 新增数）。

##### 5f. 生成/更新 INSTALLED.md

**在更新完 SKILLS-CATALOG.md 之后**（这样新技能的中文描述会被 gen_installed.py 自动采用），运行：

```bash
python ~/.claude/skills/install-skills/scripts/gen_installed.py
```

**执行顺序至关重要：必须先更新 CATALOG，再运行 gen_installed.py。**

##### 5g. 安装后验证（必须执行）

运行以下检查，确认更新质量：

```bash
# 检查 1: 新技能是否在 CATALOG 中
for skill in <新技能列表>; do
  grep -q "\`$skill\`" ~/.claude/skills/SKILLS-CATALOG.md && echo "PASS: $skill in CATALOG" || echo "FAIL: $skill missing from CATALOG"
done

# 检查 2: INSTALLED.md 描述是否为中文（非截断英文）
for skill in <新技能列表>; do
  desc=$(grep "\`$skill\`" ~/.claude/skills/INSTALLED.md | head -1)
  echo "CHECK: $desc"
done

# 检查 3: 总计数是否一致
CATALOG_TOTAL=$(grep -oP '总计.*?\K\d+' ~/.claude/skills/SKILLS-CATALOG.md | head -1)
ACTUAL=$(find ~/.claude/skills -maxdepth 2 -name "SKILL.md" | wc -l)
echo "CATALOG says: $CATALOG_TOTAL | Actual: $ACTUAL"
```

**如果任何检查 FAIL，立即修复后再继续。**

骨架模板和设计约束见 [references/catalog-skeleton.md](references/catalog-skeleton.md)。

#### 6. 汇报安装结果

安装完成后，输出一份简要汇报：
- 新增了多少个技能
- 覆盖了几个旧版
- 跳过了几个冲突
- 每个 host 的安装状态（成功/跳过/不存在）
- 来源仓库的 GitHub URL

#### 7. 清理

```bash
rm -rf /tmp/<repo-name>
```

---

### 入口 B：从 Claude 同步到其他 host（轻量流程）

当 `npx skills add` 或 `find-skills` 安装了技能到 Claude 目录后，需要同步到其他 5 个 host。

#### 1. 检测新技能

识别刚安装到 `~/.claude/skills/` 的技能名称。来源线索：
- 上一轮对话中 `npx skills add` 的输出
- `find-skills` 的安装记录
- 用户明确指出的技能名

#### 2. 同步到其他 host

```bash
SKILL_NAME="<刚安装的技能名>"
SOURCE="$HOME/.claude/skills/$SKILL_NAME"

TARGETS=(
  "$HOME/.codex/skills"
  "$HOME/.gemini/antigravity/skills"
  "$HOME/.kiro/skills"
  "$HOME/.cursor/skills"
  "$HOME/.agents/skills"
)

for target in "${TARGETS[@]}"; do
  [ -d "$target" ] || continue
  rm -rf "$target/$SKILL_NAME"
  ln -s "$SOURCE" "$target/$SKILL_NAME"
done
```

#### 3. 更新目录和汇报

- 更新 Claude 的 SKILLS-CATALOG.md（同入口 A 步骤 5）
- 更新所有 host 的 INSTALLED.md
- 汇报同步结果

#### 4. 溯源提示（可选）

同步完成后，检查 SKILLS-CATALOG.md 溯源表中是否存在「来源未明」或「用户自建」分类下的 skill。如果有，询问用户：

> "检测到 N 个来源未明的技能，是否需要进行溯源排查？（入口 E）"

用户确认后跳转入口 E。

---

### 入口 C：从本地目录/ZIP 安装（手动下载场景）

当用户手动下载了 skill 仓库（ZIP 或 git clone）到本地某个路径时走此流程。

#### 1. 定位并发现技能

用户提供本地路径后，先判断是 ZIP 还是目录：

```bash
SOURCE="<用户提供的路径>"

# 如果是 ZIP 文件，先解压
if [[ "$SOURCE" == *.zip ]]; then
  EXTRACT_DIR="/tmp/skill-extract-$(date +%s)"
  unzip -q "$SOURCE" -d "$EXTRACT_DIR"
  SOURCE="$EXTRACT_DIR"
fi

# 搜索 SKILL.md
find "$SOURCE" -name "SKILL.md" -exec dirname {} \; | xargs -I{} basename {} | sort
```

如果用户没给路径，主动搜索常见下载位置：

```bash
for dir in "$HOME/Downloads" "$HOME/Desktop" "/tmp"; do
  find "$dir" -maxdepth 3 -name "SKILL.md" -newer "$dir" -mtime -1 2>/dev/null
done
```

汇报发现的技能，确认后继续。

#### 2. 后续流程

确认技能列表后，走入口 A 的步骤 2-7（冲突检查 → 命名 → 安装到 6 host → 更新目录 → 汇报 → 清理）。

唯一区别：清理步骤只在解压了 ZIP 时删除 `$EXTRACT_DIR`，不删除用户的原始下载目录。

---

### 入口 D：刷新技能目录（独立生成）

不安装新技能，只扫描现有 host 目录并重新生成 SKILLS-CATALOG 和 INSTALLED.md。

触发场景：
- 用户说"更新目录"、"刷新 catalog"、"生成 installed"、"refresh catalog"
- 手动增删了 skill 文件后需要同步目录
- 首次使用 install-skills，已有技能但没有目录文件

#### 1. 生成/更新 INSTALLED.md

```bash
python ~/.claude/skills/install-skills/scripts/gen_installed.py
```

为每个存在的 host 目录独立生成安装清单。

#### 2. 生成/更新 SKILLS-CATALOG.md

扫描 Claude 的 skills 目录，按现有 SKILLS-CATALOG 结构动态更新。如果不存在则按骨架模板新建（见 [references/catalog-skeleton.md](references/catalog-skeleton.md)）。

更新点同入口 A 步骤 5：头部总计、来源总览、分类表、溯源表、快速指南。

#### 3. 版本检查提示（可选）

刷新完成后，扫描 SKILLS-CATALOG.md 中有 GitHub URL 的 skill，检查其 `.origin.json`（如果有）的 `checks.last_checked` 是否超过 7 天，或者从未检查过。如果有，询问用户：

> "检测到 N 个有远程来源的技能可以检查更新，是否需要检查新版？（入口 F）"

用户确认后跳转入口 F。

#### 4. 汇报

输出：
- 扫描了多少个 host
- 每个 host 有多少个 skill
- SKILLS-CATALOG 更新了哪些章节
- INSTALLED.md 生成状态

#### 4. 溯源提示（可选）

刷新完成后，扫描 SKILLS-CATALOG.md 溯源表中「来源未明」和「用户自建」分类。如果存在条目，询问用户：

> "检测到 N 个来源未明的技能，是否需要进行溯源排查？（入口 E）"

用户确认后跳转入口 E。

---

### 入口 E：溯源排查（调查来路不明的 skill）

当用户说"溯源"、"排查来源"、"查来路"、"trace origin"、"find source"、"这些 skill 哪来的"时走此流程。也可由入口 B/D 末尾的溯源提示触发。

#### 0. 扫描未归属技能

从 SKILLS-CATALOG.md 和实际 skill 目录中识别需要排查的技能：

```bash
CLAUDE_SKILLS="$HOME/.claude/skills"

# 方法 1: 找溯源表中「来源未明」章节下的技能
grep -A 100 '### 来源未明' ~/.claude/skills/SKILLS-CATALOG.md | grep '^\`' | sed 's/`//g'

# 方法 2: 找不在溯源表中的技能（CATALOG 中无来源链接）
for skill_dir in "$CLAUDE_SKILLS"/*/; do
  skill_name=$(basename "$skill_dir")
  [ -f "$skill_dir/SKILL.md" ] || continue
  # 检查溯源表中是否有该技能的 GitHub 链接
  if ! grep -q "\`$skill_name\`.*\[.*\](https://github.com" ~/.claude/skills/SKILLS-CATALOG.md 2>/dev/null; then
    echo "UNKNOWN: $skill_name"
  fi
done
```

汇报发现的未归属技能列表，确认后开始逐个排查。

#### 1. 三级搜索（按优先级依次执行）

对每个未归属的 skill，按以下顺序搜索其来源：

##### 1a. GitHub 搜索（优先级最高）

使用 WebSearch 在 GitHub 上搜索该 skill 的来源仓库。搜索策略：

```
搜索关键词组合（按命中率排序）：
1. "<skill-name>" SKILL.md filename:SKILL.md
2. "<skill-name>" "claude" skill
3. "<skill-name>" site:github.com skill
```

**匹配验证**：找到候选仓库后，用 WebFetch 读取其 SKILL.md，对比以下字段确认是同一个 skill：
- `name` 字段完全匹配
- `description` 字段语义相似（允许版本差异）
- 目录结构一致

**如果找到匹配**：记录 GitHub URL 和作者，跳到步骤 2。

##### 1b. Marketplace 搜索（优先级中）

通过 `npx skills add --search` 或访问 skillsmp.com / skills.sh 搜索：

```bash
# 方法 1: npx skills 搜索（如果可用）
npx skills search <skill-name>

# 方法 2: WebSearch 搜索 marketplace
# 搜索: "<skill-name>" site:skillsmp.com
# 搜索: "<skill-name>" site:skills.sh
```

**如果找到匹配**：记录 marketplace 来源和作者信息，跳到步骤 2。

##### 1c. find-skills 搜索（优先级低）

如果用户安装了 `find-skills` skill，可以利用它的搜索能力：

```
触发 find-skills 搜索: "find <skill-name>"
```

**如果找到匹配**：记录来源信息，跳到步骤 2。

##### 1d. 搜索穷尽

如果三级搜索都未找到来源，将该 skill 标记为「用户自建」。

#### 2. 更新 SKILLS-CATALOG.md

根据搜索结果更新溯源表：

##### 找到来源的 skill

1. **从「来源未明」移除**：删除溯源表「来源未明」章节中该 skill 的条目
2. **插入正确位置**：
   - 如果作者已在溯源表中有条目 → 追加到该作者的技能列表
   - 如果是新作者（1-3 个技能）→ 添加到「社区独立作者」表格
   - 如果是新作者（4+ 个技能）→ 新建独立子章节
3. **更新分类表**：在对应分类章节中，补充来源列的 GitHub 链接

```markdown
# 更新前（来源缺失）
| `some-skill` | 某功能描述 | — | 触发场景 |

# 更新后（来源已知）
| `some-skill` | 某功能描述 | [author](https://github.com/author/repo) | 触发场景 |
```

##### 确认为用户自建的 skill

1. **从「来源未明」移除**（如果在那里）
2. **添加到「用户自建」章节**：

在溯源表中维护一个「用户自建」子章节：

```markdown
### 用户自建 (N 技能)

以下技能经三级搜索（GitHub / Marketplace / find-skills）排查后未找到公开来源，归类为用户自建。

```
skill-a, skill-b, skill-c
```

> 最后排查时间：YYYY-MM-DD
```

3. **更新分类表**：来源列标记为 `自建`

```markdown
| `my-custom-skill` | 自定义功能描述 | 自建 | 触发场景 |
```

#### 3. 生成/更新 INSTALLED.md

溯源完成后重新运行：

```bash
python ~/.claude/skills/install-skills/scripts/gen_installed.py
```

#### 4. 汇报排查结果

输出一份溯源报告：

```
溯源排查完成
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
排查总数：N 个技能
✅ 找到来源：M 个
  - skill-a → github.com/author/repo (GitHub 搜索)
  - skill-b → skillsmp.com/skill-b (Marketplace)
🏠 确认自建：K 个
  - skill-c, skill-d
❓ 仍未确定：0 个
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SKILLS-CATALOG.md 已更新
INSTALLED.md 已重新生成
```

---

### 入口 F：版本检查（检测已安装 skill 是否有新版）

当用户说"检查更新"、"check updates"、"哪些 skill 过时了"、"skill 有新版吗"时走此流程。也可由入口 D 的版本检查提示触发。

#### 0. 构建来源映射（CATALOG 优先 + .origin.json 增强）

**来源地址优先从 SKILLS-CATALOG.md 溯源表提取**，不依赖 `.origin.json` 的存在。`.origin.json` 仅提供版本锚点（commit_hash、content_hash）作为精确对比的增强。

```python
import json, os, re, hashlib

CLAUDE_SKILLS = os.path.expanduser('~/.claude/skills')
CATALOG = os.path.expanduser('~/.claude/skills/SKILLS-CATALOG.md')

# ---------------------------------------------------------------
# Step 1: 从 SKILLS-CATALOG.md 提取 skill → GitHub URL 映射
# ---------------------------------------------------------------
catalog_urls = {}
if os.path.isfile(CATALOG):
    with open(CATALOG, 'r', encoding='utf-8') as f:
        for line in f:
            # 匹配: | `skill-name` | ... | [author](https://github.com/...) | ... |
            m = re.match(
                r'^\|\s*`([^`]+)`\s*\|.*?\[.*?\]\((https://github\.com/[^)]+)\)',
                line
            )
            if m:
                catalog_urls[m.group(1)] = m.group(2)

# ---------------------------------------------------------------
# Step 2: 合并 .origin.json 信息，分类所有 skill
# ---------------------------------------------------------------
checkable = []     # 有远程 URL，可检查更新
user_created = []  # 溯源表标记为「自建」或 .origin.json type=user-created
no_source = []     # CATALOG 无 URL 且无 .origin.json，建议先溯源

for name in sorted(os.listdir(CLAUDE_SKILLS)):
    skill_dir = os.path.join(CLAUDE_SKILLS, name)
    if not os.path.isfile(os.path.join(skill_dir, 'SKILL.md')):
        continue

    # 读取 .origin.json（如果有）
    origin = None
    origin_file = os.path.join(skill_dir, '.origin.json')
    if os.path.isfile(origin_file):
        with open(origin_file) as f:
            origin = json.load(f)

    # 来源 URL: CATALOG 优先，.origin.json 回退
    url = catalog_urls.get(name)
    if not url and origin:
        url = origin.get('source', {}).get('repo')

    if url and 'github.com' in url:
        checkable.append((name, url, origin))
    elif origin and origin.get('source', {}).get('type') == 'user-created':
        user_created.append((name, origin))
    elif not url:
        # CATALOG 中来源列为「自建」的也归入 user_created
        no_source.append(name)
    else:
        checkable.append((name, url, origin))
```

**设计原则：SKILLS-CATALOG.md 是来源地址的 Single Source of Truth，`.origin.json` 是版本状态的 Single Source of Truth。两者各司其职，互不替代。**

汇报分类结果后开始检查。

#### 1. 远程版本检查（有 URL 的 skill）

对每个可检查的 skill，获取远程最新状态并与本地对比：

##### 1a. GitHub 来源

```bash
# 从 CATALOG URL 解析 author/repo
# 例: https://github.com/author/repo → author/repo

# 获取远程最新 commit hash（不克隆，仅查询）
REMOTE_COMMIT=$(git ls-remote <repo-url> HEAD | cut -f1 | head -c7)

# 获取远程 SKILL.md 内容（通过 GitHub raw URL）
# https://raw.githubusercontent.com/<author>/<repo>/main/<skill-path>/SKILL.md
```

用 WebFetch 读取远程 SKILL.md，计算 content_hash，与本地对比。

**对比策略（按 .origin.json 可用性分级）：**

| 有 .origin.json | 对比方式 | 精度 |
|-----------------|---------|------|
| ✅ 有 commit_hash | 远程 commit vs 本地 commit → 不同则比 content_hash | 最高：能区分"仓库变了但 skill 没变" |
| ✅ 仅 content_hash | 远程 content_hash vs 本地 content_hash | 高：能检测 skill 内容变更 |
| ❌ 无 .origin.json | 远程 SKILL.md vs 本地 SKILL.md 直接 diff | 可用：能发现差异，但无法判断是远程更新还是本地修改 |

**判定逻辑：**

| 本地 content_hash | 远程 content_hash | .origin.json 记录 | 结论 |
|-------------------|-------------------|--------------------|------|
| 相同 | 相同 | — | ✅ 已是最新 |
| 不同 | — | 本地 hash = 安装时 hash | ⬆️ 远程有新版（本地未改） |
| 不同 | — | 本地 hash ≠ 安装时 hash | ⚠️ 双向变更（本地改过 + 远程也更新了） |
| — | — | 无 .origin.json | 🔍 有差异但无法判断方向，展示 diff 让用户决定 |

##### 1b. Marketplace 来源

通过 WebSearch 或 `npx skills` 查询 marketplace 上该 skill 的最新版本信息，与本地 content_hash 对比。

#### 2. 本地修改检查（用户自建 / local 来源）

对用户自建的 skill 或无远程 URL 的 skill，检查本地修改状态：

```python
import hashlib

def check_local_modification(skill_dir, origin=None):
    """检查 skill 是否有本地修改"""
    skill_md = os.path.join(skill_dir, 'SKILL.md')
    with open(skill_md, 'rb') as f:
        current_hash = 'sha256:' + hashlib.sha256(f.read()).hexdigest()[:16]

    if origin:
        # 有 .origin.json: 与安装时的 hash 对比
        recorded_hash = origin.get('version', {}).get('content_hash', '')
        if current_hash != recorded_hash:
            return 'modified'
        return 'unchanged'
    else:
        # 无 .origin.json: 无法判断是否修改过，仅记录当前 hash
        return 'unknown'
```

#### 3. 更新 .origin.json

检查完成后，更新每个 skill 的 `.origin.json` 中的 `checks` 字段：

```python
from datetime import datetime, timezone

def update_check_result(origin_file, result, remote_commit=None, remote_hash=None):
    with open(origin_file) as f:
        origin = json.load(f)

    origin['checks'] = {
        'last_checked': datetime.now(timezone.utc).isoformat(),
        'last_result': result,  # up-to-date | update-available | local-modified | check-failed
    }
    if remote_commit:
        origin['checks']['remote_commit'] = remote_commit
    if remote_hash:
        origin['checks']['remote_content_hash'] = remote_hash

    with open(origin_file, 'w') as f:
        json.dump(origin, f, indent=2, ensure_ascii=False)
```

#### 4. 汇报检查结果

输出版本检查报告：

```
版本检查完成
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
检查总数：N 个技能
来源：SKILLS-CATALOG.md 溯源表 + .origin.json

✅ 已是最新：M 个
  skill-a, skill-b, skill-c

⬆️ 有新版可用：K 个
  - skill-d → 远程 SKILL.md 已变更 (github.com/author/repo，来自 CATALOG)
  - skill-e → 远程 content 已变更 (skillsmp.com)

✏️ 本地有修改：J 个（用户自建或已定制）
  - skill-f → SKILL.md 自安装后有修改

🔍 有差异待确认：P 个（无 .origin.json，无法判断方向）
  - skill-i → 本地与远程不同，需人工确认

⚠️ 无来源：L 个（CATALOG 无 URL 且无 .origin.json）
  - skill-g → 建议先运行溯源排查（入口 E）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

#### 5. 用户决策：是否更新

对于「有新版可用」的 skill，逐个或批量询问用户：

> "以下 K 个技能有新版可用，是否更新？"
> - `skill-d`：更新 / 跳过 / 查看变更
> - `skill-e`：更新 / 跳过 / 查看变更
> - 全部更新 / 全部跳过

**"查看变更"**：用 WebFetch 获取远程 SKILL.md，与本地做 diff 展示给用户。

**"更新"**：走入口 A 的步骤 4-7（重新安装该 skill → 生成新 .origin.json → 更新目录 → 同步到其他 host）。

**对于本地有修改的 skill**：额外警告"本地有定制修改，更新会覆盖"，让用户明确确认。

---

## 跨平台注意事项

**所有入口**创建符号链接时统一遵守以下规则：

- **macOS / Linux**：`ln -s` 正常工作
- **Windows**：Git Bash 的 `ln -s` 实际创建的是**副本而非符号链接**，导致修改 Claude 目录后其他 host 不会同步更新。必须用 Python 替代：

```python
import os
os.symlink(source_path, target_path, target_is_directory=True)
```

检测当前平台后自动选择方案，而不是假设 `ln -s` 一定有效。

---

## 常见踩坑（实战经验）

以下是真实安装过程中遇到的问题，已验证的解法：

| ✅ 这样做 | ❌ 不要这样做 | 为什么 |
|-----------|--------------|--------|
| `git clone --depth 1` 浅克隆 | 完整克隆整个仓库 | skill 仓库可能有大量历史，浪费时间和空间 |
| 先检查**所有 host** 的冲突再安装 | 只检查 Claude 目录 | 其他 host 可能有独立安装的同名 skill |
| 用 Python `os.symlink` 创建符号链接 | 用 bash `ln -s`（Windows） | Windows 上 bash ln -s 创建的是副本，改 Claude 不会同步 |
| INSTALLED.md 描述从 SKILLS-CATALOG 摘取 | 从 SKILL.md frontmatter 截取 | frontmatter description 是给 LLM 触发用的，太技术化不适合人读 |
| 生成 Python 脚本后 `python script.py` 执行 | 用 `bash -c "python -c '...'"` 内嵌 | backtick 在 bash 内嵌 Python f-string 中会被 bash 吃掉 |
| SKILLS-CATALOG 符号链接共享到所有 host | 每个 host 独立维护 CATALOG | 知识地图是全局的，不应碎片化 |
| INSTALLED.md 每个 host 独立生成 | 所有 host 共享一份 INSTALLED | 各 host 安装的 skill 可能不同，状态是局部的 |
| `npx skills add` 后触发入口 B 同步 | 装完 Claude 就结束 | find-skills 只往 Claude 装，其他 5 个 host 不会自动同步 |
| 安装时立即生成 `.origin.json` | 装完不记录来源 | 没有 `.origin.json` 的 skill 无法检查更新，变成版本孤儿 |
| content_hash 用 SKILL.md 内容 | 用文件修改时间 | 文件时间在复制/链接时会变，内容 hash 才是可靠锚点 |
| `git ls-remote` 查远程版本 | `git clone` 再比较 | ls-remote 只查 ref，不下载任何内容，快几个数量级 |

---

## 错误处理

### 入口 A 特有

- **克隆失败**（网络/认证）：报告错误，建议用户手动克隆后用入口 C 提供本地路径
- **无 SKILL.md**：停止并告知"这不是一个 skills 仓库"

### 入口 B 特有

- **Claude 目录中 skill 不存在**：报告缺失，建议用户确认技能名或重新安装
- **符号链接创建失败**（权限）：报告哪个 host 失败，建议检查目录权限

### 入口 C 特有

- **ZIP 解压失败**：报告错误，建议检查文件是否损坏或路径是否正确
- **路径歧义**（多层嵌套有多个 SKILL.md）：列出所有候选，让用户确认

### 入口 E 特有

- **GitHub 搜索无结果或被限流**：等待后重试，或跳过该 skill 进入下一级搜索
- **`npx skills search` 不可用**：跳过 marketplace 搜索，继续 find-skills 搜索
- **find-skills 未安装**：跳过该搜索级别，直接进入"搜索穷尽"判定
- **SKILL.md 内容过于通用**（如 name 是 `utils`）：搜索结果可能有大量误匹配，列出 top 3 候选让用户手动确认
- **网络不可用**：报告无法执行在线搜索，建议用户联网后重试

### 入口 F 特有

- **`git ls-remote` 失败**（仓库已删除/改名/私有化）：标记 `check-failed`，建议用户确认仓库状态或更新 CATALOG 中的 URL
- **CATALOG URL 指向仓库根目录但 skill 在子目录**：尝试常见路径模式（`skills/<name>/SKILL.md`、`<name>/SKILL.md`），找不到则标记 `check-failed`
- **`.origin.json` 格式损坏**：不影响检查（来源从 CATALOG 读），但跳过精确 commit 对比，退化为 content_hash 对比
- **大量 skill 需要检查**（50+）：分批执行，每批 10 个，避免 GitHub API 限流
- **本地修改 + 远程更新同时存在**：明确警告用户"更新会覆盖本地修改"，建议先备份
- **CATALOG 中 URL 格式异常**（非 GitHub URL）：跳过该 skill，报告"来源 URL 不支持自动检查"

### 通用

- **符号链接在 Windows 上静默降级为副本**：检测 `sys.platform == 'win32'`，用 Python `os.symlink` 替代
- **host 目录不存在**：静默跳过，不报错。在汇报中标注"不存在"

---

## 关键模式

### 仓库结构自动检测

| 结构 | 示例 |
|------|------|
| `skills/<name>/SKILL.md` | vercel-labs/skills, greensock/gsap-skills |
| `<category>/skills/<name>/SKILL.md` | phuryn/pm-skills（按类别嵌套） |
| `<name>/SKILL.md` | 扁平仓库 |

### 冲突处理

| 场景 | 默认动作 |
|------|---------|
| 同名不同仓库 | 询问用户 |
| 同名同仓库（更新） | 覆盖 |
| 新技能无冲突 | 直接安装 |
