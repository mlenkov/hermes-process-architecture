#!/usr/bin/env python3
"""Architect CLI — автономный хранитель архитектуры.

Исполняет цикл: monitor → executor → coverage → pdca.
Может работать как одноразовый запуск или как daemon (cron-ready).

Usage:
    python3 scripts/architect.py monitor         # проверить состояние
    python3 scripts/architect.py execute         # обработать ready-задачи
    python3 scripts/architect.py coverage        # обновить registry
    python3 scripts/architect.py pdca            # PDCA-отчёт
    python3 scripts/architect.py cycle           # полный цикл
    python3 scripts/architect.py daemon          # бесконечный цикл (cron)
"""
import argparse, json, os, subprocess, sys, time
from datetime import datetime
from pathlib import Path

ARCH = Path(__file__).resolve().parent.parent
OUTPUTS = ARCH / "outputs" / "07.007"
REGISTRY = OUTPUTS / "labor-coverage-registry.yaml"
REPORTS = OUTPUTS / "pdca-reports"
TD_GEN = ARCH / "profiles" / "architect" / "skills" / "td-gen"

# ── Config ───────────────────────────────────────────────────
TOTAL_TF = 124
Q3_TARGET = 43   # 35%
Q4_TARGET = 62   # 50%
# ──────────────────────────────────────────────────────────────

def hermes(cmd: list[str], timeout=30) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["hermes", "kanban"] + cmd,
        capture_output=True, text=True, timeout=timeout
    )

def parse_body(show_out: str) -> dict | None:
    lines = show_out.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("Body:"):
            rest = line[5:].strip()
            try:
                return json.loads(rest if rest else lines[i+1].strip())
            except (json.JSONDecodeError, IndexError):
                return None
    return None

# ── Monitor ──────────────────────────────────────────────────
def cmd_monitor():
    stats = hermes(["stats"])

    ready = hermes(["list", "--status", "ready", "--json"])
    ready_tasks = json.loads(ready.stdout) if ready.stdout.strip() else []

    blocked = hermes(["list", "--status", "blocked", "--json"])
    blocked_tasks = json.loads(blocked.stdout) if blocked.stdout.strip() else []

    report = {
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ready": len(ready_tasks),
        "blocked": len(blocked_tasks),
        "actions": [],
    }

    print(f"Kanban stats: {len(ready_tasks)} ready, {len(blocked_tasks)} blocked")

    if ready_tasks:
        report["actions"].append("executor")
        print("  → Запуск executor")
        cmd_execute()

    if blocked_tasks:
        report["actions"].append("selfheal")
        print("  → Запуск selfheal")
        cmd_selfheal()

    # Сохранить отчёт
    (OUTPUTS / "monitor").mkdir(parents=True, exist_ok=True)
    import yaml
    with open(OUTPUTS / "monitor" / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.yaml", "w") as f:
        yaml.dump(report, f)

# ── Selfheal ─────────────────────────────────────────────────
def cmd_selfheal():
    for status in ["blocked", "running"]:
        tasks = hermes(["list", "--status", status, "--json"])
        task_list = json.loads(tasks.stdout) if tasks.stdout.strip() else []
        for t in task_list:
            tid = t["id"]
            r = hermes(["reclaim", tid])
            if r.returncode == 0:
                print(f"  Reclaimed {tid}: {t.get('title','?')[:50]}")
            else:
                print(f"  [FAIL] {tid}: {r.stderr.strip()}")
                # escalate
                esc_dir = OUTPUTS / "escalate"
                esc_dir.mkdir(parents=True, exist_ok=True)
                import yaml
                with open(esc_dir / f"{datetime.now().strftime('%Y%m%d')}-{tid}.yaml", "w") as f:
                    yaml.dump({"task_id": tid, "tf": t.get("title","?"), "action": "requires OpenCode"}, f)
                print(f"  Escalate: {tid}")

# ── Executor ─────────────────────────────────────────────────
def cmd_execute():
    import yaml

    ready = hermes(["list", "--status", "ready", "--json"])
    tasks = json.loads(ready.stdout) if ready.stdout.strip() else []

    if not tasks:
        print("  No ready tasks.")
        return

    for t in tasks:
        tid = t["id"]

        # Claim
        claim = hermes(["claim", tid])
        if claim.returncode != 0:
            print(f"  [SKIP] {tid}: {claim.stderr.strip()}")
            continue
        print(f"\n  ⏩ {tid}: {t.get('title','?')[:60]}")

        # Body
        show = hermes(["show", tid])
        body = parse_body(show.stdout)
        if not body:
            hermes(["reclaim", tid])
            print("    [SKIP] no body")
            continue

        la_id = body.get("la_id")
        if not la_id:
            # TF-summary task — просто complete
            print(f"    TF-summary task, completing directly")
            hermes(["complete", tid, "--summary", "TF pipeline complete"])
            continue

        parent_tf = body.get("parent_tf", "")
        tf_code = parent_tf.replace("LF-07.007-", "") if parent_tf else "unknown"
        input_files = body.get("input_files", [])
        output_dir = body.get("output_dir")
        output_files = body.get("output_files", [])
        print(f"    TF: {tf_code}, LA: {la_id}, Outputs: {len(output_files)}")

        # Найти и выполнить skill через td_runner
        import td_runner
        td_runner.generate(tf_code, la_id, input_files, output_dir, output_files, body)

        # Complete
        complete = hermes(["complete", tid, "--summary", f"{la_id}: {len(output_files)} outputs"])
        if complete.returncode == 0:
            print(f"    ✅ {tid}")
        else:
            print(f"    [FAIL] complete: {complete.stderr.strip()}")
            hermes(["reclaim", tid])

    print(f"\n  Done: {len(tasks)} tasks")

# ── Coverage ──────────────────────────────────────────────────
def cmd_coverage():
    import yaml

    done = hermes(["list", "--status", "done", "--json"])
    tasks = json.loads(done.stdout) if done.stdout.strip() else []
    tf_summaries = [t for t in tasks if "\U0001f504" in t.get("title", "")]

    registry = {}
    if REGISTRY.exists():
        with open(REGISTRY) as f:
            registry = yaml.safe_load(f) or {}

    for t in tf_summaries:
        tid = t["id"]
        show = hermes(["show", tid])
        body = parse_body(show.stdout)
        if not body or body.get("type") != "tf_pipeline":
            continue

        tf_code = body.get("function", {}).get("code", "?")
        lf_id = f"LF-07.007-{tf_code}"
        total = body.get("total_actions", 0)

        registry[lf_id] = {
            "status": "covered",
            "last_executed": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tds_completed": f"{total}/{total}",
            "executed_by": "architect",
        }
        print(f"  {lf_id}: covered ({total}/{total})")

    with open(REGISTRY, "w") as f:
        yaml.dump(registry, f, allow_unicode=True, default_flow_style=False)

# ── PDCA ──────────────────────────────────────────────────────
def cmd_pdca():
    import yaml

    if not REGISTRY.exists():
        print("  No registry found.")
        return

    with open(REGISTRY) as f:
        registry = yaml.safe_load(f) or {}

    covered = sum(1 for v in registry.values() if v.get("status") == "covered")
    pct = round(covered / TOTAL_TF * 100, 1)
    gap_q3 = max(0, Q3_TARGET - covered)
    gap_q4 = max(0, Q4_TARGET - covered)
    status = "on_track" if pct >= 35 else "behind"

    report = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "coverage": {"covered": covered, "total": TOTAL_TF, "pct": pct, "status": status},
        "targets": {"q3": {"target": Q3_TARGET, "gap": gap_q3}, "q4": {"target": Q4_TARGET, "gap": gap_q4}},
        "recommendations": [],
    }

    if gap_q3 > 0:
        report["recommendations"].append({
            "action": f"Execute {min(gap_q3, 5)} uncovered TFs from priority list",
            "priority": "high",
        })

    REPORTS.mkdir(parents=True, exist_ok=True)
    path = REPORTS / f"pdca-{report['date']}.yaml"
    with open(path, "w") as f:
        yaml.dump(report, f, allow_unicode=True, default_flow_style=False)

    print(f"  Coverage: {pct}% ({covered}/{TOTAL_TF}) — {status}")
    print(f"  Report: {path}")

# ── Cycle / Daemon ────────────────────────────────────────────
def cmd_cycle():
    print("=" * 50)
    print(f"Architect cycle: {datetime.now().isoformat()}")
    cmd_monitor()
    cmd_coverage()
    cmd_pdca()

def cmd_daemon():
    interval = 900  # 15 min
    print(f"Architect daemon starting, interval={interval}s")
    while True:
        cmd_cycle()
        print(f"Sleeping {interval}s...")
        time.sleep(interval)

# ── CLI ───────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Architect — хранитель архитектуры")
    parser.add_argument("command", choices=["monitor", "execute", "selfheal", "coverage", "pdca", "cycle", "daemon"])
    args = parser.parse_args()

    commands = {
        "monitor": cmd_monitor,
        "execute": cmd_execute,
        "selfheal": cmd_selfheal,
        "coverage": cmd_coverage,
        "pdca": cmd_pdca,
        "cycle": cmd_cycle,
        "daemon": cmd_daemon,
    }

    commands[args.command]()

if __name__ == "__main__":
    main()
