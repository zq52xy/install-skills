# .origin.json Schema

> 每个 skill 目录下的版本状态文件。记录版本锚点（commit hash、content hash）和检查历史。
> 来源地址（GitHub URL、作者）的权威来源是 SKILLS-CATALOG.md 溯源表，`.origin.json` 不重复存储来源地址，仅在 CATALOG 无记录时作为回退。
> 由入口 A/B/C 安装时自动生成，入口 E 溯源成功时补写，入口 F 检查更新时刷新。

## 与 SKILLS-CATALOG.md 的职责分工

| 维度 | SKILLS-CATALOG.md | .origin.json |
|------|-------------------|--------------|
| 来源地址（GitHub URL） | ✅ 权威来源 | 回退（CATALOG 无记录时） |
| 作者信息 | ✅ 权威来源 | 回退 |
| 版本锚点（commit/content hash） | ❌ 不存储 | ✅ 权威来源 |
| 检查历史（last_checked/result） | ❌ 不存储 | ✅ 权威来源 |
| 分类归属 | ✅ 权威来源 | ❌ 不存储 |

**设计原则**：CATALOG 是给人读的全局地图，`.origin.json` 是给机器读的版本状态。两者各司其职，互不替代。没有 `.origin.json` 的 skill，只要 CATALOG 有 URL，照样能检查更新（退化为 content_hash 对比）。

---

## Schema

```json
{
  "name": "skill-name",
  "source": {
    "type": "github | marketplace | local | user-created",
    "repo": "https://github.com/author/repo",
    "author": "author-name",
    "marketplace": "skillsmp.com | skills.sh | null"
  },
  "version": {
    "installed_at": "2025-06-15T10:30:00Z",
    "commit_hash": "a1b2c3d",
    "content_hash": "sha256:abcdef1234567890",
    "remote_ref": "main"
  },
  "checks": {
    "last_checked": "2025-07-01T08:00:00Z",
    "last_result": "up-to-date | update-available | check-failed",
    "remote_commit": "d4e5f6g",
    "remote_content_hash": "sha256:fedcba0987654321"
  }
}
```

---

## 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `name` | ✅ | skill 目录名 |
| `source.type` | ✅ | 来源类型：`github`（仓库克隆）、`marketplace`（官方渠道）、`local`（本地路径）、`user-created`（溯源排查后确认自建） |
| `source.repo` | 条件 | GitHub 仓库 URL（type 为 github/marketplace 时必填） |
| `source.author` | 条件 | 作者名（有来源时必填） |
| `source.marketplace` | 可选 | marketplace 平台名（type 为 marketplace 时填写） |
| `version.installed_at` | ✅ | 安装时间（ISO 8601） |
| `version.commit_hash` | 条件 | 安装时的 Git commit hash（从 GitHub 安装时必填） |
| `version.content_hash` | ✅ | SKILL.md 内容的 SHA-256 hash（所有来源都生成，用于检测本地修改） |
| `version.remote_ref` | 可选 | 远程分支名，默认 `main` |
| `checks.last_checked` | 可选 | 上次检查更新的时间 |
| `checks.last_result` | 可选 | 上次检查结果 |
| `checks.remote_commit` | 可选 | 远程最新 commit hash |
| `checks.remote_content_hash` | 可选 | 远程 SKILL.md 的 content hash |

---

## 生成时机

| 入口 | 动作 |
|------|------|
| A（GitHub 安装） | 克隆后立即生成，commit_hash 从 `git rev-parse HEAD` 获取 |
| B（Claude 同步） | 符号链接的 host 自动继承 Claude 目录的 `.origin.json`；Kiro 用 `cp -r` 时一并复制；如果没有则补写（type=`local`） |
| C（本地安装） | 生成 type=`local`，无 commit_hash，仅 content_hash |
| E（溯源成功） | 补写/更新 source 字段，添加 commit_hash |
| F（版本检查） | 更新 checks 字段 |

---

## content_hash 生成方法

```python
import hashlib

def content_hash(skill_dir):
    """对 SKILL.md 内容生成 SHA-256 hash"""
    skill_md = os.path.join(skill_dir, 'SKILL.md')
    with open(skill_md, 'rb') as f:
        return 'sha256:' + hashlib.sha256(f.read()).hexdigest()[:16]
```

取前 16 位十六进制（64 bit）足够检测变更，保持 JSON 简洁。

---

## 设计约束

| 维度 | 约束 |
|------|------|
| 位置 | `~/.claude/skills/<skill-name>/.origin.json` |
| 可见性 | 不写入 SKILLS-CATALOG（避免污染人类可读文档） |
| 继承 | 符号链接的 host 自动继承 Claude 目录的 `.origin.json`；Kiro 通过 `cp -r` 获得独立副本 |
| 冲突 | 覆盖安装时，旧 `.origin.json` 被新的替换 |
| 用户自建 | type=`user-created`，无 repo/commit，仅 content_hash |

[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
