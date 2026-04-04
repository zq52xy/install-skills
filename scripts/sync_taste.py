"""同步 Leonxlnx/taste-skill 仓库：删除远程已移除的，安装新增的，更新已有的"""
import os, sys, shutil, subprocess, tempfile, hashlib, json, stat, re
from datetime import datetime, timezone

REPO_URL = "https://github.com/Leonxlnx/taste-skill"
CLAUDE_SKILLS = os.path.expanduser('~/.claude/skills')
SYNC_TARGETS = [
    os.path.expanduser('~/.codex/skills'),
    os.path.expanduser('~/.gemini/antigravity/skills'),
    os.path.expanduser('~/.kiro/skills'),
    os.path.expanduser('~/.cursor/skills'),
    os.path.expanduser('~/.agents/skills'),
]

# 本地属于 taste-skill 的所有 skill（含远程已删除的）
LOCAL_TASTE_SKILLS = [
    'taste-skill', 'minimalist-skill', 'redesign-skill', 'soft-skill',
    'output-skill',
    # 远程已删除
    'design-taste-frontend', 'full-output-enforcement',
    'redesign-existing-projects', 'high-end-visual-design', 'minimalist-ui',
]

def _on_rm_error(func, path, exc_info):
    os.chmod(path, stat.S_IWRITE)
    func(path)

def force_remove(path):
    if not os.path.exists(path) and not os.path.islink(path):
        return
    if os.path.islink(path) or os.path.isjunction(path):
        try:
            os.remove(path)
        except OSError:
            os.rmdir(path)
        return
    for item in os.listdir(path):
        fp = os.path.join(path, item)
        if os.path.islink(fp) or os.path.isjunction(fp):
            try: os.remove(fp)
            except: os.rmdir(fp)
        elif os.path.isdir(fp):
            shutil.rmtree(fp, onerror=_on_rm_error)
        else:
            try: os.remove(fp)
            except: os.chmod(fp, stat.S_IWRITE); os.remove(fp)
    os.rmdir(path)

def sync_to_hosts(skill_name, delete=False):
    source = os.path.join(CLAUDE_SKILLS, skill_name)
    for t in SYNC_TARGETS:
        if not os.path.isdir(t): continue
        target = os.path.join(t, skill_name)
        force_remove(target)
        if not delete:
            try: os.symlink(source, target, target_is_directory=True)
            except: shutil.copytree(source, target)

def gen_origin(skill_name, clone_dir):
    sd = os.path.join(CLAUDE_SKILLS, skill_name)
    with open(os.path.join(sd, 'SKILL.md'), 'rb') as f:
        ch = 'sha256:' + hashlib.sha256(f.read()).hexdigest()[:16]
    try:
        r = subprocess.run(['git','-C',clone_dir,'rev-parse','HEAD'],
                           capture_output=True, text=True, timeout=10)
        commit = r.stdout.strip()[:7]
    except: commit = 'unknown'
    origin = {
        "name": skill_name,
        "source": {"type":"github","repo":REPO_URL,"author":"Leonxlnx"},
        "version": {
            "installed_at": datetime.now(timezone.utc).isoformat(),
            "commit_hash": commit, "content_hash": ch, "remote_ref": "main"
        },
        "checks": {
            "last_checked": datetime.now(timezone.utc).isoformat(),
            "last_result": "up-to-date"
        }
    }
    with open(os.path.join(sd, '.origin.json'), 'w') as f:
        json.dump(origin, f, indent=2, ensure_ascii=False)

def main():
    print("同步 Leonxlnx/taste-skill")
    print("=" * 50)

    # Clone
    tmp = tempfile.mkdtemp(prefix='taste-sync-')
    try:
        subprocess.run(['git','clone','--depth','1','--quiet',REPO_URL,tmp],
                       check=True, capture_output=True, timeout=60)
    except Exception as e:
        print(f"克隆失败: {e}"); return

    # 远程 skill 列表
    remote_skills = set()
    skills_dir = os.path.join(tmp, 'skills')
    if os.path.isdir(skills_dir):
        for d in os.listdir(skills_dir):
            if os.path.isfile(os.path.join(skills_dir, d, 'SKILL.md')):
                remote_skills.add(d)
    print(f"远程: {sorted(remote_skills)}")

    # 1. 删除远程已移除的
    to_delete = [s for s in LOCAL_TASTE_SKILLS if s not in remote_skills]
    for s in to_delete:
        p = os.path.join(CLAUDE_SKILLS, s)
        if os.path.exists(p):
            force_remove(p)
            sync_to_hosts(s, delete=True)
            print(f"  🗑 删除 {s}")
        else:
            print(f"  - {s} 已不存在")

    # 2. 安装/更新远程有的
    for s in sorted(remote_skills):
        remote_dir = os.path.join(skills_dir, s)
        local_dir = os.path.join(CLAUDE_SKILLS, s)

        # 检查是否需要更新
        action = "安装" if not os.path.exists(local_dir) else "更新"

        force_remove(local_dir)
        os.makedirs(local_dir, exist_ok=True)
        for item in os.listdir(remote_dir):
            if item == '.git': continue
            src = os.path.join(remote_dir, item)
            dst = os.path.join(local_dir, item)
            if os.path.isdir(src): shutil.copytree(src, dst)
            else: shutil.copy2(src, dst)

        gen_origin(s, tmp)
        sync_to_hosts(s)
        print(f"  ✓ {action} {s}")

    shutil.rmtree(tmp, ignore_errors=True)
    print("\n完成")

if __name__ == '__main__':
    main()
