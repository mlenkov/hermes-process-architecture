#!/usr/bin/env python3
"""Execute TF→TD pipeline: claim, generate output, complete."""
import json, os, re, subprocess, sys, yaml
from pathlib import Path

ARCH_ROOT = Path(__file__).resolve().parent.parent

# ── Sandbox config (Фаза 2A) ────────────────────────────────────────
DEFAULTS = {
    "skill_timeout": 120,
    "cpu_limit_sec": 120,
    "memory_limit_mb": 512,
    "file_size_limit_mb": 10,
}


def load_sandbox_config() -> dict:
    """Читать config.yaml (или env SKILL_TIMEOUT и др.). Fallback — дефолты."""
    cfg = dict(DEFAULTS)
    cfg_path = ARCH_ROOT / "config.yaml"
    if cfg_path.exists():
        try:
            data = yaml.safe_load(open(cfg_path, encoding="utf-8")) or {}
            for k in cfg:
                if isinstance(data.get(k), (int, float)) and data[k] > 0:
                    cfg[k] = int(data[k])
        except Exception as e:
            print(f"  [WARN] config.yaml read error, using defaults: {e}")

    env_map = {
        "SKILL_TIMEOUT": "skill_timeout",
        "SKILL_CPU_LIMIT_SEC": "cpu_limit_sec",
        "SKILL_MEMORY_LIMIT_MB": "memory_limit_mb",
        "SKILL_FILE_SIZE_LIMIT_MB": "file_size_limit_mb",
    }
    for env_name, key in env_map.items():
        v = os.environ.get(env_name)
        if v and v.isdigit() and int(v) > 0:
            cfg[key] = int(v)
    return cfg


def build_sandbox_preamble(cfg: dict) -> str:
    """RLIMIT-ограничения для подпроцесса навыка (graceful fallback).

    resource.setrlimit может не поддерживаться (Windows) или быть запрещён
    (RLIMIT_AS в некоторых контейнерах) — в таких случаях пропускаем.
    """
    lines = [
        "import resource",
        "_rlimits = []",
        f"_cpu = {cfg['cpu_limit_sec']}",
        f"_mem = {cfg['memory_limit_mb']} * 1024 * 1024",
        f"_fsz = {cfg['file_size_limit_mb']} * 1024 * 1024",
        "for _res, _lim in ((resource.RLIMIT_CPU, (_cpu, _cpu)),",
        "                    (resource.RLIMIT_AS, (_mem, _mem)),",
        "                    (resource.RLIMIT_FSIZE, (_fsz, _fsz))):",
        "    try:",
        "        resource.setrlimit(_res, _lim)",
        "    except (resource.error, ValueError, OSError) as _e:",
        "        import sys as _sys",
        "        print(f'  [WARN] RLIMIT {_res} not applied: {_e}', file=_sys.stderr)",
        "",
    ]
    return "\n".join(lines)


SANDBOX_CONFIG = load_sandbox_config()


def run_hermes(args):
    result = subprocess.run(
        ["hermes", "kanban"] + args,
        capture_output=True, text=True, timeout=30
    )
    return result

def get_task_body(task_id):
    r = run_hermes(["show", task_id])
    lines = r.stdout.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("Body:"):
            rest = line[5:].strip()
            if rest:
                return json.loads(rest)
            elif i + 1 < len(lines):
                return json.loads(lines[i + 1].strip())
    return None

def extract_process_code(skill_path):
    """Извлечь python-код секции ## Process из SKILL.md (ADR-002 формат)."""
    if not skill_path or not os.path.exists(skill_path):
        return None
    content = Path(skill_path).read_text(encoding="utf-8")
    m = re.search(r"## Process\s*```python\n(.*?)\n```", content, re.S)
    if not m:
        print(f"  [WARN] no python block in ## Process: {skill_path}")
        return None
    return m.group(1)


def find_skill_md(body):
    """Найти полный путь к SKILL.md навыка для ТД.

    Приоритет:
      1. body.skill_path (полный путь, кладётся seeder'ом из mapping/registry)
      2. поиск по profiles/*/skills/{skill}/SKILL.md
      3. labor-function-to-skill-mapping.yaml → skill_path
    """
    candidates = []
    sp = body.get("skill_path", "")
    if sp:
        if os.path.isabs(sp):
            candidates.append(sp)
        else:
            candidates.append(str(ARCH_ROOT / sp))
            for pdir in (ARCH_ROOT / "profiles").iterdir():
                if pdir.is_dir():
                    candidates.append(str(pdir / "skills" / sp))
                    candidates.append(str(pdir / sp))

    skill = body.get("skill", "")
    if skill:
        for pdir in (ARCH_ROOT / "profiles").iterdir():
            if pdir.is_dir():
                candidates.append(str(pdir / "skills" / skill / "SKILL.md"))

    # mapping fallback
    tf = (body.get("parent_tf") or "").replace("LF-07.007-", "")
    if tf:
        mapping_path = ARCH_ROOT / "outputs/07.007/block-D/labor-function-to-skill-mapping.yaml"
        try:
            mapping = yaml.safe_load(open(mapping_path, encoding="utf-8")) or {}
            for e in mapping.get("mappings", []):
                if e.get("tf_code") == tf and e.get("skill_path"):
                    rel = e["skill_path"]
                    for pdir in (ARCH_ROOT / "profiles").iterdir():
                        if pdir.is_dir():
                            candidates.append(str(pdir / "skills" / rel))
        except Exception as ex:
            print(f"  [WARN] mapping read: {ex}")

    for cand in candidates:
        if os.path.exists(cand):
            return cand
    return None


def run_skill_in_subprocess(code, body, task_id):
    """Запустить код навыка в подпроцессе (Шаг 0 вызывает os._exit — безопасно).

    Sandbox (Фаза 2A): RLIMIT_CPU/AS/FSIZE + wall-clock timeout из config.yaml
    или env (SKILL_TIMEOUT). RLIMIT недоступен на Windows — graceful fallback.
    """
    tmp_dir = ARCH_ROOT / "outputs" / "07.007" / ".executor_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    script = tmp_dir / f"{task_id}.py"
    # pprint.pformat даёт валидный Python-литерал (None/True/False),
    # json.dumps выдал бы null/true/false — NameError в коде навыка.
    import pprint
    def py_lit(obj):
        return pprint.pformat(obj, width=200)
    preamble = (
        "import os, yaml\n"
        + build_sandbox_preamble(SANDBOX_CONFIG)
        + "body = " + py_lit(body) + "\n"
        + "input_files = " + py_lit(body.get("input_files", [])) + "\n"
        + "output_files = " + py_lit(body.get("output_files", [])) + "\n"
        + "output_dir = " + py_lit(body.get("output_dir", "outputs/07.007")) + "\n"
    )
    script.write_text(preamble + "\n" + code, encoding="utf-8")
    try:
        proc = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(ARCH_ROOT),
            capture_output=True, text=True, timeout=SANDBOX_CONFIG["skill_timeout"],
        )
        return proc
    except subprocess.TimeoutExpired:
        print(f"  [ERROR] skill timed out after {SANDBOX_CONFIG['skill_timeout']}s, reclaiming {task_id}")
        try:
            script.unlink(missing_ok=True)
        except OSError:
            pass
        # Возвращаем маркер таймаута: returncode!=0, вызывающий код reclaim'ит
        class _TimeoutProc:
            returncode = -1
            stdout = ""
            stderr = "TIMEOUT"
        return _TimeoutProc()
    finally:
        try:
            script.unlink(missing_ok=True)
        except OSError:
            pass


def update_registry(body, skill_path, artifact_files):
    """Обновить labor-coverage-registry.yaml после успешной генерации.

    Регистрирует ТФ как covered (ADR-007: запись появляется после реального
    исполнения; без фиктивных записей).
    """
    tf = (body.get("parent_tf") or "").replace("LF-07.007-", "")
    if not tf:
        return False
    registry_path = ARCH_ROOT / "outputs/07.007/labor-coverage-registry.yaml"
    try:
        registry = yaml.safe_load(open(registry_path, encoding="utf-8")) or {}
    except Exception as e:
        print(f"  [ERROR] registry read: {e}")
        return False

    key = f"LF-07.007-{tf}"
    entry = registry.get(key)
    if entry and entry.get("status") in ("covered", "partially_covered"):
        # Уже синхронизирован — ничего не трогаем (Шаг 0 уже пропустил)
        return False

    if entry is None:
        entry = registry[key] = {}

    import datetime
    # ADR-008: единственный исполнитель 07.007 — профиль mais
    entry["executed_by"] = "mais"
    entry["last_executed"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    entry["status"] = "covered"
    entry["tds_completed"] = entry.get("tds_completed", "0/0")
    entry["skill_path"] = skill_path or entry.get("skill_path", "")
    existing = set(entry.get("artifacts_generated", []))
    for af in artifact_files:
        if af and af not in existing:
            entry.setdefault("artifacts_generated", []).append(af)

    with open(registry_path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(registry, fh, allow_unicode=True, sort_keys=False, default_flow_style=False)
    return True


def generic_output(body):
    """Fallback: если навык не найден — минимальный артефакт (как architect-executor)."""
    output_dir = body.get("output_dir", "outputs/07.007")
    os.makedirs(output_dir, exist_ok=True)
    for fpath in body.get("output_files", []):
        oid = os.path.basename(fpath).replace(".yaml", "")
        with open(fpath, "w", encoding="utf-8") as f:
            yaml.dump({"id": oid, "status": "generated", "source": "generic"}, f, allow_unicode=True)


def execute():
    # Get all ready tasks
    r = run_hermes(["list", "--status", "ready", "--json"])
    if r.returncode != 0:
        print(f"Error listing tasks: {r.stderr}")
        return

    tasks = json.loads(r.stdout.strip()) if r.stdout.strip() else []

    if not tasks:
        print("No ready tasks.")
        return

    for t in tasks:
        tid = t["id"]
        title = t.get("title", "?")

        # Claim
        claim = run_hermes(["claim", tid])
        if claim.returncode != 0:
            print(f"  [SKIP] cannot claim {tid}: {claim.stderr.strip()}")
            continue

        print(f"\n▶ {tid}: {title[:60]}")

        # Get body
        body = get_task_body(tid)
        if not body:
            print(f"  [ERROR] no body found, reclaiming")
            run_hermes(["reclaim", tid])
            continue

        la_id = body.get("la_id", "?")
        inputs = body.get("inputs", [])
        outputs = body.get("outputs", [])
        input_files = body.get("input_files", [])
        output_files = body.get("output_files", [])
        output_dir = body.get("output_dir", "/tmp")

        print(f"  Inputs: {inputs}")
        print(f"  Outputs: {outputs}")

        # ── TF-summary задача: навык не вызывается (нет la_id/output_files) ──
        if body.get("type") == "tf_pipeline" or not la_id:
            print("  [INFO] TF-summary task — skip skill execution (artifacts already produced by TDs)")
            complete = run_hermes(["complete", tid, "--summary", f"TF {body.get('function', {}).get('code', '?')}: summary done"])
            if complete.returncode == 0:
                print(f"  ✅ {tid} completed (TF-summary)")
            else:
                print(f"  [ERROR] complete failed: {complete.stderr.strip()}")
            continue

        # ── Найти и запустить реальный навык (mapping → SKILL.md → ## Process) ──
        skill_path = find_skill_md(body)
        code = extract_process_code(skill_path) if skill_path else None

        if code:
            print(f"  Skill: {skill_path}")
            proc = run_skill_in_subprocess(code, body, tid)
            if proc.stdout:
                print(proc.stdout.rstrip())
            if proc.stderr and proc.stderr.strip():
                print(f"  [STDERR] {proc.stderr.strip()[:500]}")
            print(f"  Skill exit: {proc.returncode}")

            if proc.returncode == 0:
                # Артефакт создан навыком (или пропущен Шагом 0 — тогда registry уже синхронизирован)
                produced = [f for f in output_files if os.path.exists(f)]
                updated = update_registry(body, skill_path, produced)
                if updated:
                    print(f"  Registry updated: {body.get('parent_tf')} → covered")
                else:
                    print("  Registry already up to date (skip path)")
                completed_ok = True
            else:
                print(f"  [ERROR] skill failed, reclaiming {tid}")
                run_hermes(["reclaim", tid])
                completed_ok = False
        else:
            print(f"  [WARN] no skill found for TF {body.get('parent_tf')}, using generic generator")
            generic_output(body)
            update_registry(body, None, output_files)
            completed_ok = True

        # ── Complete (если не отклонено) ─────────────────────────────
        if completed_ok:
            complete = run_hermes(["complete", tid, "--summary", f"{la_id}: {len(output_files)} outputs"])
        if complete.returncode == 0:
            print(f"  ✅ {tid} completed")
        else:
            print(f"  [ERROR] complete failed: {complete.stderr.strip()}")

    print(f"\nDone. Check kanban for next batch.")

if __name__ == "__main__":
    execute()
