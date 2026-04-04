# 共享知识：跨平台兼容 + 仓库结构 + 常见踩坑

本文件包含所有入口共享的技术知识。由 SKILL.md 按需引用。

---

## 跨平台注意事项

### 符号链接

- **macOS / Linux**：`ln -s` 正常工作
- **Windows**：Git Bash 的 `ln -s` 创建的是副本而非符号链接。必须用 Python：

```python
import os
os.symlink(source_path, target_path, target_is_directory=True)
```

### Windows 上删除目录（force_remove_dir）

Python 3.12+ 的 `shutil.rmtree` 拒绝删除符号链接目录。必须用以下兼容方案：

```python
import os, shutil, stat

def _on_rm_error(func, path, exc_info):
    os.chmod(path, stat.S_IWRITE)
    func(path)

def force_remove_dir(path):
    """强制删除目录，兼容 Windows 符号链接/junction/reparse point"""
    if not os.path.exists(path) and not os.path.islink(path):
        return
    if os.path.islink(path) or os.path.isjunction(path):
        try: os.remove(path)
        except OSError: os.rmdir(path)
        return
    try:
        for item in os.listdir(path):
            fp = os.path.join(path, item)
            if os.path.islink(fp) or os.path.isjunction(fp):
                try: os.remove(fp)
                except OSError: os.rmdir(fp)
            elif os.path.isdir(fp):
                shutil.rmtree(fp, onerror=_on_rm_error)
            else:
                try: os.remove(fp)
                except OSError:
                    os.chmod(fp, stat.S_IWRITE); os.remove(fp)
        os.rmdir(path)
    except OSError:
        shutil.rmtree(path, onerror=_on_rm_error)
```

关键点：`os.path.isjunction()` 是 Python 3.12+ 新增；`onerror` 处理 `.git/objects/` 只读文件。

---

## 仓库结构自动检测

静态候选路径按优先级逐一尝试，全部未命中时用 `os.walk` 动态搜索。

| 结构 | 示例 |
|------|------|
| `skills/<name>/SKILL.md` | vercel-labs/skills, greensock/gsap-skills |
| `<name>/SKILL.md` | 扁平仓库 |
| `plugins/<category>/skills/<name>/SKILL.md` | EveryInc/compound-engineering-plugin, wshobson/agents |
| `.agents/skills/<name>/SKILL.md` | pbakaus/impeccable |
| `.claude/skills/<name>/SKILL.md` | uditgoenka/autoresearch |
| `<category>/skills/<name>/SKILL.md` | 0xdesign/design-plugin |
| `SKILL.md`（仓库根目录） | 单 skill 仓库 |

**前缀处理**：本地 `ce-brainstorm` 对应远程 `brainstorm`。搜索时同时尝试原名和去掉已知前缀后的名字。

**动态回退**：递归遍历克隆目录（跳过 `.git`），查找 `skills/<name>/SKILL.md`。


---

## 常见踩坑（实战经验）

| ✅ 这样做 | ❌ 不要这样做 | 为什么 |
|-----------|--------------|--------|
| `git clone --depth 1` 浅克隆 | 完整克隆整个仓库 | skill 仓库可能有大量历史 |
| 先检查**所有 host** 的冲突再安装 | 只检查 Claude 目录 | 其他 host 可能有同名 skill |
| 用 Python `os.symlink` 创建符号链接 | 用 bash `ln -s`（Windows） | Windows 上 bash ln -s 创建副本 |
| 用 `force_remove_dir` 删目录 | 直接 `shutil.rmtree` | Python 3.12+ rmtree 拒绝删符号链接目录 |
| 复制 skill 时跳过 `.git` 子目录 | 连 `.git` 一起复制 | `.git/objects/` 只读锁导致删除失败 |
| 大仓库（4+ skill）clone 批量对比 | 逐个 HTTP 请求 | 40+ HTTP 请求会超时 |
| 静态候选 + `os.walk` 动态回退 | 只硬编码 3 种路径 | 实际仓库结构至少 7 种 |
| 前缀版和无前缀版只保留一套 | 两套并存 | 冗余副本更新时容易漏掉一套 |
| 从 SKILLS-CATALOG 摘取人类描述 | 截断 frontmatter | frontmatter 适合 LLM 触发，不适合人读 |
| 每个 host 独立生成 INSTALLED.md | 共用一份 | 各 host 安装状态可能不同 |
| 安装时立即生成 `.origin.json` | 装完不记录 | 无 .origin.json 的 skill 无法检查更新 |
| `git ls-remote` 查远程版本 | clone 再比较 | ls-remote 只查 ref，快几个数量级 |
| 从溯源表提取来源 URL | 从分类表提取 | 分类表来源列可能为空 |
| 批量更新时排除 install-skills 自身 | 更新自身 | 更新会删除正在执行的脚本 |
| CATALOG 新建/更新后检查骨架 8 项齐全 | 只更新分类表不管其他结构 | 缺少溯源表/总览表/快速指南会导致后续入口 E/F 无法正常工作 |

---

## 错误处理

### 入口 A/B/C 特有
- **克隆失败**：建议用户手动克隆后用入口 C
- **无 SKILL.md**：停止，告知"不是 skills 仓库"
- **ZIP 解压失败**：检查文件是否损坏
- **符号链接创建失败**：报告哪个 host 失败

### 入口 E 特有
- **GitHub 搜索限流**：等待后重试或跳过
- **SKILL.md 内容过于通用**：列出 top 3 候选让用户确认

### 入口 F/G 特有
- **`git ls-remote` 失败**：标记 `check-failed`，建议确认仓库状态
- **CATALOG URL 指向仓库根但 skill 在子目录**：尝试常见路径模式
- **大量 skill（50+）**：分批执行，每批 10 个
- **本地修改 + 远程更新同时存在**：警告"更新会覆盖本地修改"

### 通用
- **Windows 符号链接静默降级为副本**：用 Python `os.symlink`
- **host 目录不存在**：静默跳过，汇报中标注
