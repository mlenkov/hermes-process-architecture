#!/usr/bin/env python3
"""Execute TF→TD pipeline: claim, generate output, complete."""
import json, os, re, subprocess, sys, yaml, urllib.request
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

    # ADR-007: ТФ в documented_gaps не получает фиктивную запись от
    # generic-исполнения (0/0 ТД). Запись появится только после реального
    # исполнения навыком с кодом (## Process).
    if key in (registry.get("documented_gaps") or {}):
        print(f"  [WARN] {key}: documented gap — фиктивная запись не создаётся (ADR-007)")
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


# ── Webhooks (ADR-009) ────────────────────────────────────────────────

def load_webhook_url() -> str:
    """Прочитать webhook_url из config.yaml (корень проекта).

    Отсутствие/пустое значение → "" (отправка пропускается; система
    остаётся работоспособной в polling-режиме).
    """
    cfg_path = ARCH_ROOT / "config.yaml"
    if not cfg_path.exists():
        return ""
    try:
        data = yaml.safe_load(open(cfg_path, encoding="utf-8")) or {}
        url = data.get("webhook_url", "")
        return str(url).strip() if url else ""
    except Exception as e:
        print(f"  [WARN] config.yaml webhook_url read error: {e}")
        return ""


def _webhook_payload(event: str, body: dict, artifact: str,
                     schema_valid: bool, awaiting_approval: bool) -> dict:
    import datetime
    tf = (body.get("parent_tf") or "").replace("LF-07.007-", "")
    return {
        "event": event,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tf_code": tf,
        "skill": body.get("skill", ""),
        "artifact": artifact,
        "schema_valid": schema_valid,
        "awaiting_approval": awaiting_approval,
    }


def send_webhook(event: str, body: dict, artifact: str = "",
                 schema_valid: bool = False, awaiting_approval: bool = False):
    """Отправить webhook (ADR-009).

    Транспорт: HTTP POST JSON через urllib, timeout 5 c.
    webhook_url отсутствует → пропуск (не ошибка).
    Недоступность endpoint → [WARN] в лог, НЕ прерывает исполнение.
    """
    url = load_webhook_url()
    if not url:
        return False

    payload = _webhook_payload(event, body, artifact, schema_valid, awaiting_approval)
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            if 200 <= resp.status < 300:
                print(f"  [WEBHOOK] {event} → {url} (HTTP {resp.status})")
                return True
            print(f"  [WARN] webhook {event}: HTTP {resp.status}")
            return False
    except Exception as e:
        print(f"  [WARN] webhook {event} failed: {e} — pipeline продолжается")
        return False


def read_artifact_quality(artifact_path: str) -> tuple:
    """(schema_valid, awaiting_approval) из quality артефакта (безопасно)."""
    if not artifact_path or not os.path.exists(artifact_path):
        return False, False
    try:
        data = yaml.safe_load(open(artifact_path, encoding="utf-8")) or {}
        q = data.get("quality", {}) if isinstance(data, dict) else {}
        return bool(q.get("schema_valid")), bool(q.get("awaiting_approval"))
    except Exception:
        return False, False


def dependencies_ready(body: dict) -> tuple:
    """Проверить depends_on_artifacts: все ли существуют и schema_valid == true.

    Возвращает (ready: bool, missing: list[str]).
    Пустой depends_on_artifacts → (True, []).

    Справочники (labor-coverage-registry.yaml, labor-function-to-skill-mapping.yaml)
    не имеют quality-блока — для них требуется ТОЛЬКО существование.
    schema_valid требуется для генерируемых артефактов (outputs/07.007/block-*).
    """
    REFERENCE_FILES = {"labor-coverage-registry.yaml",
                       "labor-function-to-skill-mapping.yaml"}
    deps = body.get("depends_on_artifacts") or []
    missing = []
    for rel in deps:
        p = ARCH_ROOT / rel if not os.path.isabs(rel) else Path(rel)
        base = os.path.basename(rel)
        if not p.exists():
            missing.append(f"{rel} (нет файла)")
            continue
        if base in REFERENCE_FILES:
            continue  # справочник существует — достаточно
        sv, _ = read_artifact_quality(str(p))
        if not sv:
            missing.append(f"{rel} (schema_valid != true)")
    return (len(missing) == 0), missing


def load_skill_timeout() -> int:
    """skill_timeout из config.yaml (fallback 120)."""
    cfg_path = ARCH_ROOT / "config.yaml"
    try:
        data = yaml.safe_load(open(cfg_path, encoding="utf-8")) or {}
        return int(data.get("skill_timeout", 120))
    except Exception:
        return 120


def get_task_started_ts(tid: str):
    """Время started задачи (ISO в show) → unix timestamp. None если неизвестно."""
    from datetime import datetime
    s = run_hermes(["show", tid])
    for line in s.stdout.splitlines():
        if line.strip().startswith("started:"):
            val = line.split(":", 1)[1].strip()
            try:
                dt = datetime.fromisoformat(val)
                return dt.timestamp()
            except Exception:
                try:
                    return float(val)
                except Exception:
                    return None
    return None


def reclaim_stale_running() -> int:
    """Stale running reclaim (hardening): задачи в status=running, у которых
    время claim старше skill_timeout × 3, возвращаются в ready.

    Счётчик reclaim ведётся в комментариях задачи: reclaim_count. При
    reclaim_count >= 3 → status=blocked + WARN (эскалация для selfheal).
    Детерминировано, без сети.
    Возвращает число обработанных задач.
    """
    stale_timeout = load_skill_timeout() * 3
    r = run_hermes(["list", "--status", "running", "--json"])
    if r.returncode != 0:
        return 0
    running = json.loads(r.stdout.strip()) if r.stdout.strip() else []
    handled = 0
    import time as _time
    now = _time.time()
    for t in running:
        tid = t["id"]
        started_ts = get_task_started_ts(tid)
        if started_ts is None:
            continue  # не можем оценить — не трогаем
        age = now - started_ts
        if age < stale_timeout:
            continue  # ещё не stale

        # счётчик reclaim — из комментариев задачи
        rc = get_task_counter(tid, "reclaim_count") + 1
        set_task_counter(tid, "reclaim_count", rc)
        if rc >= 3:
            # эскалация: blocked для selfheal
            run_hermes(["block", tid])
            print(f"  [WARN] {tid}: stale running x{rc} → BLOCKED (эскалация для selfheal)")
            handled += 1
            continue
        # reclaim → ready
        rc2 = run_hermes(["reclaim", tid])
        if rc2.returncode == 0:
            print(f"  [STALE] {tid}: reclaim (stale running, age={age:.0f}s, count={rc})")
            handled += 1
        else:
            print(f"  [WARN] {tid}: stale reclaim failed: {rc2.stderr.strip()}")
    return handled


WAIT_WATCHDOG_K = 5


def get_task_counter(tid: str, key: str) -> int:
    """Прочитать счётчик из комментариев задачи (последний комментарий)."""
    s = run_hermes(["show", tid])
    for line in reversed(s.stdout.splitlines()):
        if f"{key}=" in line:
            try:
                return int(line.split(f"{key}=", 1)[1].split()[0])
            except Exception:
                continue
    return 0


def set_task_counter(tid: str, key: str, value: int):
    """Записать счётчик в комментарий задачи (best-effort)."""
    try:
        run_hermes(["comment", tid, f"{key}={value}"])
    except Exception:
        pass


def bump_wait_cycle(tid: str, body: dict) -> bool:
    """WAIT-watchdog: увеличить wait_cycles (в комментариях задачи).

    Если wait_cycles >= K (5) прогонов подряд — WARN в сводке.
    Возвращает True, если watchdog сработал (>= K).
    """
    wc = get_task_counter(tid, "wait_cycles") + 1
    set_task_counter(tid, "wait_cycles", wc)
    return wc >= WAIT_WATCHDOG_K


def execute():
    # ── Hardening: stale running reclaim (до выбора ready-задач) ──
    try:
        stale_handled = reclaim_stale_running()
        if stale_handled:
            print(f"  [HARDENING] stale running reclaimed: {stale_handled}")
    except Exception as e:
        print(f"  [WARN] stale-running reclaim error: {e}")

    # Get all ready tasks
    r = run_hermes(["list", "--status", "ready", "--json"])
    if r.returncode != 0:
        print(f"Error listing tasks: {r.stderr}")
        return

    tasks = json.loads(r.stdout.strip()) if r.stdout.strip() else []
    waiting = 0
    wait_watchdog_fired = []

    if not tasks:
        print("No ready tasks.")
        return

    for t in tasks:
        tid = t["id"]
        title = t.get("title", "?")

        # ── Dependency gate (до claim): задача не становится ready, пока все
        # depends_on_artifacts не существуют и schema_valid == true (ADR: dependency-aware).
        body = get_task_body(tid)
        if not body:
            print(f"  [WARN] {tid}: no body (пропуск, не claim)")
            continue

        deps_ok, missing = dependencies_ready(body)
        if not deps_ok:
            waiting += 1
            print(f"  [WAIT] {tid}: {title[:50]} — ждёт артефакты: {missing}")
            # WAIT-watchdog: счётчик wait_cycles в body
            try:
                if bump_wait_cycle(tid, body):
                    wait_watchdog_fired.append((tid, missing))
            except Exception as e:
                print(f"  [WARN] wait-cycle bump error: {e}")
            continue

        # Claim
        claim = run_hermes(["claim", tid])
        if claim.returncode != 0:
            print(f"  [SKIP] cannot claim {tid}: {claim.stderr.strip()}")
            continue

        print(f"\n▶ {tid}: {title[:60]}")

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

                # ── Webhooks (ADR-009) ──────────────────────────────
                # Skip-путь Шага 0 (Skipping generation) → событий нет.
                is_skip = "Skipping generation" in (proc.stdout or "")
                if not is_skip and produced:
                    artifact_path = produced[0]
                    sv, aa = read_artifact_quality(artifact_path)
                    send_webhook("artifact.generated", body, artifact_path, sv, aa)
                    if aa:
                        send_webhook("approval.requested", body, artifact_path, sv, aa)
                    # HITL-компаньон (ADR-006): approval-request рядом с основным
                    # артефактом — тоже записанный артефакт → событие.
                    companion = artifact_path.replace(".yaml", "-approval-request.yaml")
                    if os.path.exists(companion) and companion != artifact_path:
                        send_webhook("artifact.generated", body, companion, sv, aa)
                completed_ok = True
            else:
                print(f"  [ERROR] skill failed, reclaiming {tid}")
                run_hermes(["reclaim", tid])
                send_webhook("pipeline.blocked", body,
                             output_files[0] if output_files else "", False, False)
                completed_ok = False
        else:
            print(f"  [WARN] no skill found for TF {body.get('parent_tf')}, using generic generator")
            generic_output(body)
            update_registry(body, None, output_files)
            produced = [f for f in output_files if os.path.exists(f)]
            if produced:
                send_webhook("artifact.generated", body, produced[0], False, False)
            completed_ok = True

        # ── Complete (если не отклонено) ─────────────────────────────
        if completed_ok:
            complete = run_hermes(["complete", tid, "--summary", f"{la_id}: {len(output_files)} outputs"])
        if complete.returncode == 0:
            print(f"  ✅ {tid} completed")
        else:
            print(f"  [ERROR] complete failed: {complete.stderr.strip()}")

    if wait_watchdog_fired:
        print("\n  [WARN] WAIT-watchdog: следующие задачи ждут артефакты "
              f"{WAIT_WATCHDOG_K}+ прогонов подряд:")
        for tid, missing in wait_watchdog_fired:
            print(f"    - {tid}: {missing}")

    if waiting:
        print(f"\n  Waiting for artifacts: {waiting} task(s) — dependencies not satisfied, will retry on next run.")
    else:
        print(f"\nDone. Check kanban for next batch.")

if __name__ == "__main__":
    execute()
