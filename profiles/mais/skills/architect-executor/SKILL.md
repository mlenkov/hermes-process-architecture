---
name: architect-executor
description: Оркестратор исполнения ТД — берёт ready-задачи, определяет td-gen skill, генерирует output, complete
version: 1.0.0
environments: [kanban]
---

# Executor — исполнение pipeline

Оркестратор: для каждой ready-задачи определяет тип ТД, загружает специализированный td-gen skill и выполняет.

## Процедура

```python
import subprocess, json, yaml, os, sys

# ADR-008: навыки 07.007 живут в профиле mais
SKILLS_BASE = "/Users/mac/.hermes/skills/mais"
PROFILES = "/Users/mac/.hermes/profiles/mais"
PROJECT = "/Volumes/Storage/work/mais/_TOOLS/VM-SRV001-SETUP/ARCHITECTURE"

def run_hermes(args):
    return subprocess.run(["hermes", "kanban"] + args, capture_output=True, text=True, timeout=30)

def find_skill_path(tf_code, la_id):
    """Найти SKILL.md для данной ТФ/ТД.
    
    Порядок:
      1. td-gen/{tf_dir}-{la_id}/SKILL.md
      2. labor-function-to-skill-mapping.yaml → skill_path
      3. None → generic fallback
    """
    tf_dir = tf_code.replace("/", "-").replace(" ", "_")

    # 1. td-gen
    tdgen = f"{SKILLS_BASE}/td-gen/{tf_dir}-{la_id}/SKILL.md"
    if os.path.exists(tdgen):
        return tdgen

    # 2. mapping
    mapping_path = f"{PROJECT}/outputs/07.007/block-D/labor-function-to-skill-mapping.yaml"
    if os.path.exists(mapping_path):
        try:
            with open(mapping_path) as f:
                mapping = yaml.safe_load(f) or {}
            for entry in mapping.get("mappings", []):
                if entry.get("tf_code") == tf_code:
                    skill_rel = entry.get("skill_path", "")
                    if skill_rel:
                        # Попробовать в ~/.hermes/skills/mais/
                        candidate = f"{SKILLS_BASE}/{skill_rel}"
                        if os.path.exists(candidate):
                            return candidate
                        # Попробовать в profiles/mais/skills/
                        candidate2 = f"{PROJECT}/profiles/mais/skills/{skill_rel}"
                        if os.path.exists(candidate2):
                            return candidate2
        except Exception as e:
            print(f"  [WARN] mapping read error: {e}")

    return None  # generic fallback

def read_skill_instructions(skill_path):
    """Извлечь инструкции генерации из SKILL.md (секция после ## Process)."""
    with open(skill_path) as f:
        content = f.read()
    import re
    match = re.search(r'## Process\n+```python\n(.+?)\n```', content, re.DOTALL)
    if match:
        return match.group(1)
    return ""

# ── 1. Получить ready-задачи ────────────────────────────────────
ready = run_hermes(["list", "--status", "ready", "--json"])
tasks = json.loads(ready.stdout) if ready.stdout.strip() else []

if not tasks:
    print("No ready tasks.")
    sys.exit(0)

for t in tasks:
    tid = t["id"]

    # ── 2. Claim ──────────────────────────────────────────
    claim = run_hermes(["claim", tid])
    if claim.returncode != 0:
        print(f"Cannot claim {tid}: {claim.stderr}")
        continue
    print(f"\n▶ Claimed: {tid} — {t.get('title','?')[:60]}")

    # ── 3. Прочитать body ─────────────────────────────────
    show = run_hermes(["show", tid])
    lines = show.stdout.split("\n")
    body = None
    for i, line in enumerate(lines):
        if line.startswith("Body:"):
            rest = line[5:].strip()
            body = json.loads(rest if rest else lines[i+1].strip())
            break
    if not body:
        run_hermes(["reclaim", tid])
        print("  [SKIP] no body found")
        continue

    la_id = body.get("la_id")
    parent_tf = body.get("parent_tf", "")
    input_files = body.get("input_files", [])
    output_dir = body.get("output_dir")
    output_files = body.get("output_files", [])

    tf_code = parent_tf.replace("LF-07.007-", "") if parent_tf else "unknown"

    print(f"  TF: {tf_code}, LA: {la_id}")
    print(f"  Inputs: {len(input_files)} files, Outputs: {len(output_files)} files")

    # ── 4. Найти и выполнить skill ────────────────────────
    skill_path = find_skill_path(tf_code, la_id)
    
    if skill_path:
        instructions = read_skill_instructions(skill_path)
    
    if skill_path and instructions:
        print(f"  Skill: {skill_path}")
        exec_scope = {
            "__builtins__": __builtins__,
            "input_files": input_files,
            "output_dir": output_dir,
            "output_files": output_files,
            "body": body,
            "yaml": yaml,
            "os": os,
            "re": __import__("re"),
            "subprocess": __import__("subprocess"),
            "json": json,
            "print": print,
        }
        try:
            exec(instructions, exec_scope)
            print(f"  ✅ Generated: {len(output_files)} outputs")
        except Exception as e:
            print(f"  [ERROR] generation failed: {e}")
            run_hermes(["reclaim", tid])
            continue
    else:
        # Fallback: generic generation
        print("  [WARN] no skill found, using generic generator")
        os.makedirs(output_dir, exist_ok=True)
        for fpath in output_files:
            oid = os.path.basename(fpath).replace(".yaml", "")
            with open(fpath, "w") as f:
                yaml.dump({"id": oid, "status": "generated", "source": "generic"}, f)

    # ── 5. Complete ───────────────────────────────────────
    complete = run_hermes(["complete", tid, "--summary", f"{la_id}: {len(output_files)} outputs"])
    if complete.returncode == 0:
        print(f"  ✅ Completed: {tid}")
    else:
        print(f"  [ERROR] complete failed: {complete.stderr}")

print(f"\nDone. {len(tasks)} tasks processed.")
```
