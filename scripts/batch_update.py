"""
* [INPUT]: 待更新 skill 列表 + 远程 GitHub 仓库
* [OUTPUT]: 更新本地 skill 文件，同步到所有 host
* [POS]: install-skills/scripts 的批量更新执行器
* [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""
import json, os, sys, shutil, subprocess, tempfile, hashlib, re
from datetime import datetime, timezone

CLAUDE_SKILLS = os.path.expanduser('~/.claude/skills')
SYNC_TARGETS = [
    os.path.expanduser('~/.codex/skills'),
    os.path.expanduser('~/.gemini/antigravity/skills'),
    os.path.expanduser('~/.kiro/skills'),
    os.path.expanduser('~/.cursor/skills'),
    os.path.expanduser('~/.agents/skills'),
]

# 剩余待更新的 skill（硬编码，排除 install-skills 自身）
REMAINING = [
    ("wireframe-prototyping", "https://github.com/aj-geddes/useful-ai-prompts"),
    ("pptx", "https://github.com/anthropics/skills"),
    ("email-sequence", "https://github.com/coreyhaines31/marketingskills"),
    ("launch-strategy", "https://github.com/coreyhaines31/marketingskills"),
    ("marketing-psychology", "https://github.com/coreyhaines31/marketingskills"),
    ("referral-program", "https://github.com/coreyhaines31/marketingskills"),
    ("seo-audit", "https://github.com/coreyhaines31/marketingskills"),
    ("skill-creator", "https://github.com/daymade/claude-code-skills"),
    ("skill-from-masters", "https://github.com/gbsoss/skill-from-masters"),
    ("dan-koe", "https://github.com/kluless13/claude-skills"),
    ("pptx-generator", "https://github.com/minimax-ai/skills"),
    ("ui-ux-pro-max", "https://github.com/nextlevelbuilder/ui-ux-pro-max-skill"),
    ("brainstorming", "https://github.com/obra/superpowers"),
    ("youtube-clipper", "https://github.com/op7418/youtube-clipper-skill"),
    ("adapt", "https://github.com/pbakaus/impeccable"),
    ("animate", "https://github.com/pbakaus/impeccable"),
    ("audit", "https://github.com/pbakaus/impeccable"),
    ("bolder", "https://github.com/pbakaus/impeccable"),
    ("clarify", "https://github.com/pbakaus/impeccable"),
    ("colorize", "https://github.com/pbakaus/impeccable"),
    ("critique", "https://github.com/pbakaus/impeccable"),
    ("delight", "https://github.com/pbakaus/impeccable"),
    ("distill", "https://github.com/pbakaus/impeccable"),
    ("extract", "https://github.com/pbakaus/impeccable"),
    ("harden", "https://github.com/pbakaus/impeccable"),
    ("normalize", "https://github.com/pbakaus/impeccable"),
    ("onboard", "https://github.com/pbakaus/impeccable"),
    ("optimize", "https://github.com/pbakaus/impeccable"),
    ("polish", "https://github.com/pbakaus/impeccable"),
    ("quieter", "https://github.com/pbakaus/impeccable"),
    ("teach-impeccable", "https://github.com/pbakaus/impeccable"),
    ("find-skills", "https://github.com/vercel-labs/skills"),
    ("jobs-to-be-done", "https://github.com/wondelai/skills"),
]


def clone_repo(url, dest):
    try:
        subprocess.run(
            ['git', 'clone', '--depth', '1', '--quiet', url, dest],
            capture_output=True, timeout=120, check=True
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def find_skill_md(clone_dir, skill_name):
    stripped = skill_name
    for prefix in ['ce-', 'gstack-']:
        if skill_name.startswith(prefix) and len(skill_name) > len(prefix):
            stripped = skill_name[len(prefix):]
            break
    candidates = [
        os.path.join(clone_dir, skill_name, 'SKILL.md'),
        os.path.join(clone_dir, 'skills', skill_name, 'SKILL.md'),
        os.path.join(clone_dir, stripped, 'SKILL.md'),
        os.path.join(clone_dir, 'skills', stripped, 'SKILL.md'),
        os.path.join(clone_dir, '.agents', 'skills', skill_name, 'SKILL.md'),
        os.path.join(clone_dir, '.agents', 'skills', stripped, 'SKILL.md'),
        os.path.join(clone_dir, '.claude', 'skills', skill_name, 'SKILL.md'),
        os.path.join(clone_dir, '.claude', 'skills', stripped, 'SKILL.md'),
        os.path.join(clone_dir, 'SKILL.md'),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return os.path.dirname(c)
    for name_variant in [skill_name, stripped]:
        for root, dirs, files in os.walk(clone_dir):
            dirs[:] = [d for d in dirs if d != '.git']
            candidate = os.path.join(root, 'skills', name_variant, 'SKILL.md')
            if os.path.isfile(candidate):
                return os.path.join(root, 'skills', name_variant)
    return None


def _on_rm_error(func, path, exc_info):
    """rmtree onerror: 去掉只读属性后重试"""
    import stat
    os.chmod(path, stat.S_IWRITE)
    func(path)


def force_remove_dir(path):
    """强制删除目录，兼容 Windows 符号链接/junction/reparse point"""
    if not os.path.exists(path) and not os.path.islink(path):
        return
    # 如果是符号链接或 junction，直接删链接本身
    if os.path.islink(path) or os.path.isjunction(path):
        try:
            os.remove(path)
        except OSError:
            os.rmdir(path)
        return
    # 实体目录：先递归处理子项中的链接
    try:
        for item in os.listdir(path):
            fp = os.path.join(path, item)
            if os.path.islink(fp) or (hasattr(os.path, 'isjunction') and os.path.isjunction(fp)):
                try:
                    os.remove(fp)
                except OSError:
                    os.rmdir(fp)
            elif os.path.isdir(fp):
                shutil.rmtree(fp, onerror=_on_rm_error)
            else:
                try:
                    os.remove(fp)
                except OSError:
                    import stat
                    os.chmod(fp, stat.S_IWRITE)
                    os.remove(fp)
        os.rmdir(path)
    except OSError:
        # 最后手段
        shutil.rmtree(path, onerror=_on_rm_error)


def update_skill(skill_name, remote_skill_dir):
    local_dir = os.path.join(CLAUDE_SKILLS, skill_name)
    force_remove_dir(local_dir)
    os.makedirs(local_dir, exist_ok=True)
    for item in os.listdir(remote_skill_dir):
        if item == '.git':
            continue
        src = os.path.join(remote_skill_dir, item)
        dst = os.path.join(local_dir, item)
        if os.path.isdir(src):
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
    return True


def sync_to_hosts(skill_name):
    source = os.path.join(CLAUDE_SKILLS, skill_name)
    for target_base in SYNC_TARGETS:
        if not os.path.isdir(target_base):
            continue
        target = os.path.join(target_base, skill_name)
        force_remove_dir(target)
        try:
            os.symlink(source, target, target_is_directory=True)
        except OSError:
            shutil.copytree(source, target)


def generate_origin(skill_name, repo_url, clone_dir):
    skill_dir = os.path.join(CLAUDE_SKILLS, skill_name)
    skill_md = os.path.join(skill_dir, 'SKILL.md')
    with open(skill_md, 'rb') as f:
        ch = 'sha256:' + hashlib.sha256(f.read()).hexdigest()[:16]
    try:
        result = subprocess.run(
            ['git', '-C', clone_dir, 'rev-parse', 'HEAD'],
            capture_output=True, text=True, timeout=10
        )
        commit = result.stdout.strip()[:7]
    except Exception:
        commit = 'unknown'
    m = re.match(r'https://github\.com/([^/]+)/', repo_url)
    author = m.group(1) if m else 'unknown'
    origin = {
        "name": skill_name,
        "source": {"type": "github", "repo": repo_url, "author": author},
        "version": {
            "installed_at": datetime.now(timezone.utc).isoformat(),
            "commit_hash": commit,
            "content_hash": ch,
            "remote_ref": "main"
        },
        "checks": {
            "last_checked": datetime.now(timezone.utc).isoformat(),
            "last_result": "up-to-date"
        }
    }
    with open(os.path.join(skill_dir, '.origin.json'), 'w') as f:
        json.dump(origin, f, indent=2, ensure_ascii=False)


def main():
    print("=" * 60)
    print("install-skills 批量更新（第二轮）")
    print("=" * 60)

    repo_groups = {}
    for name, url in REMAINING:
        repo_groups.setdefault(url, []).append(name)

    total = len(REMAINING)
    print(f"\n待更新: {total} 个 skill，涉及 {len(repo_groups)} 个仓库\n")

    ok_count, fail_count = 0, 0
    idx = 0

    for repo_url, skills in sorted(repo_groups.items()):
        idx += 1
        short = repo_url.replace('https://github.com/', '')
        print(f"[{idx}/{len(repo_groups)}] {short} ({len(skills)} skill)")

        tmp = tempfile.mkdtemp(prefix='skill-update-')
        try:
            if not clone_repo(repo_url, tmp):
                print(f"    克隆失败")
                fail_count += len(skills)
                continue

            for skill_name in skills:
                remote_dir = find_skill_md(tmp, skill_name)
                if not remote_dir:
                    print(f"    ✗ {skill_name} — 远程路径未找到")
                    fail_count += 1
                    continue
                try:
                    update_skill(skill_name, remote_dir)
                    generate_origin(skill_name, repo_url, tmp)
                    sync_to_hosts(skill_name)
                    print(f"    ✓ {skill_name}")
                    ok_count += 1
                except Exception as e:
                    print(f"    ✗ {skill_name} — {e}")
                    fail_count += 1
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n{'='*60}")
    print(f"✅ 成功: {ok_count} | ✗ 失败: {fail_count}")


if __name__ == '__main__':
    main()
