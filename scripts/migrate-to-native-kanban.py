#!/usr/bin/env python3
"""Migrate TF→TD pipeline to native Hermes Kanban primitives (Фаза 6a).

Заменяет кастомную seed-логику на нативные возможности kanban:
  - hermes kanban create --idempotency-key <key>  → идемпотентное создание
  - --parent <id>                                  → нативные dependencies
                                                    (auto-promote todo→ready,
                                                     когда все parents done)
  - --assignee mais                                → назначение исполнителя

ВНИМАНИЕ: это миграционный скрипт. Он НЕ удаляет старые скрипты
(seed-tf-pipeline.py / execute-tf-pipeline.py) — те остаются до полной
верификации нативного dispatcher'а (ADR-010 ещё не принят).

Usage:
    python3 scripts/migrate-to-native-kanban.py                 # все ТФ
    python3 scripts/migrate-to-native-kanban.py --otf C         # блок C
    python3 scripts/migrate-to-native-kanban.py --tf "С/01.7"  # одна ТФ
    python3 scripts/migrate-to-native-kanban.py --dry-run       # preview
    python3 scripts/migrate-to-native-kanban.py --board mais-agency
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

_ARCH_ROOT = Path(__file__).resolve().parent.parent
_YAML_DIR = _ARCH_ROOT / "docs" / "standards" / "07.007"
_MAPPING_PATH = _ARCH_ROOT / "outputs" / "07.007" / "block-D" / "labor-function-to-skill-mapping.yaml"
_PROFILE = "mais"

OTF_CODE_MAP = {
    "otf-section-1.yaml": "А",
    "otf-section-2.yaml": "В",
    "otf-section-3.yaml": "С",
    "otf-section-4.yaml": "D",
}


def load_yaml_safe(path: Path):
    try:
        import yaml
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"  [WARN] Failed to load {path}: {e}", file=sys.stderr)
        return None


def load_mapping() -> dict:
    """tf_code → {skill_path, status}."""
    data = load_yaml_safe(_MAPPING_PATH) or {}
    out = {}
    for e in data.get("mappings", []):
        tf = e.get("tf_code")
        if tf:
            out[tf] = {
                "skill_path": e.get("skill_path", ""),
                "status": e.get("coverage_status", ""),
            }
    return out


def load_all_tfs():
    """Все ТФ из otf-секций (labor_functions), с _otf_code/_source_file."""
    all_tfs = []
    for f in sorted(_YAML_DIR.glob("otf-section-*.yaml")):
        data = load_yaml_safe(f)
        if not data or not isinstance(data, dict):
            continue
        otf_code = OTF_CODE_MAP.get(f.name, "?")
        for lf in data.get("labor_functions", []):
            lf["_otf_code"] = otf_code
            lf["_source_file"] = f.name
            all_tfs.append(lf)
    return all_tfs


def run_hermes(args: list[str], board: Optional[str] = None) -> subprocess.CompletedProcess:
    """hermes kanban [--board X] <args>."""
    hermes_bin = os.environ.get("HERMES_BIN", "hermes")
    cmd = [hermes_bin, "kanban"]
    if board:
        cmd += ["--board", board]
    cmd += args
    env = os.environ.copy()
    env["PATH"] = "/home/hermes/.local/bin:" + env.get("PATH", "")
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=env)


def create_task(
    title: str,
    body: str = "",
    assignee: str = _PROFILE,
    parent: Optional[str] = None,
    idem_key: Optional[str] = None,
    board: Optional[str] = None,
    dry_run: bool = False,
) -> Optional[str]:
    """Нативное создание задачи с idempotency-key и parent-ссылкой.

    --idempotency-key: повторный вызов с тем же ключом НЕ создаёт дубликат
    (нативный dedup — заменяет наш --clean / ручную проверку).
    """
    args = ["create", "--json", "--assignee", assignee]
    if body:
        args += ["--body", body]
    if parent:
        args += ["--parent", parent]
    if idem_key:
        args += ["--idempotency-key", idem_key]
    args.append(title)

    if dry_run:
        print(f"  [DRY-RUN] hermes kanban create ... ({title[:50]})")
        return f"dry-{idem_key or title[:20]}"

    result = run_hermes(args, board=board)
    if result.returncode != 0:
        print(f"  [ERROR] kanban create failed: {result.stderr.strip()}", file=sys.stderr)
        return None
    try:
        data = json.loads(result.stdout.strip())
        return data.get("id")
    except json.JSONDecodeError:
        # fallback: id из текста "Created t_xxx"
        m = re.search(r"(t_[a-f0-9]+)", result.stdout)
        return m.group(1) if m else None


def migrate_tf(tf: dict, mapping: dict, board: Optional[str], dry_run: bool) -> dict:
    """Создать TF-задачу + TD-цепочку для одной ТФ через нативные примитивы."""
    otf_code = tf.get("_otf_code", "?")
    tf_code = tf.get("code", "?")
    tf_name = tf.get("name", "?")
    actions = tf.get("трудовые_действия", [])
    lf_id = f"LF-07.007-{tf_code}"

    result = {"tf_code": tf_code, "tasks": [], "errors": []}

    if not actions:
        result["errors"].append(f"No labor actions for {tf_code}")
        return result

    entry = mapping.get(tf_code, {})
    skill_name = os.path.basename(entry.get("skill_path", "")).replace("/SKILL.md", "") or "kanban-worker"

    # ── TF-level body (та же схема, что в seed — executor её понимает) ──
    tf_body = json.dumps({
        "type": "tf_pipeline",
        "standard": {"code": "07.007"},
        "function": {"code": tf_code, "name": tf_name},
        "total_actions": len(actions),
        "skill_path": entry.get("skill_path", ""),
        "skill": skill_name,
        "labor_actions": [
            {"id": f"la-{i:03d}", "text": a, "sequence_index": i, "profile": _PROFILE,
             "skill": skill_name}
            for i, a in enumerate(actions, 1)
        ],
    }, ensure_ascii=False)

    tf_id = create_task(
        title=f"🔄 {tf_code}: {tf_name[:80]}",
        body=tf_body,
        idem_key=f"tf-{tf_code.replace('/', '-')}",
        board=board,
        dry_run=dry_run,
    )
    if not tf_id:
        result["errors"].append(f"Failed to create TF task for {tf_code}")
        return result
    result["tf_task_id"] = tf_id

    # ── TD-цепочка: TD1 (без parent) ← TD2 (parent=TD1) ← ... ──
    # Нативный dispatcher сам промотит todo→ready, когда все parents done.
    prev_id = None
    for i, action_text in enumerate(actions, 1):
        la_code = f"la-{i:03d}"
        la_body = json.dumps({
            "la_id": la_code,
            "text": action_text,
            "sequence_index": i,
            "parent_tf": lf_id,
            "otf_code": f"ОТФ-{otf_code}",
            "skill_path": entry.get("skill_path", ""),
            "skill": skill_name,
        }, ensure_ascii=False)

        child_id = create_task(
            title=f"  {la_code}: {action_text[:60]}",
            body=la_body,
            parent=prev_id,
            idem_key=f"tf-{tf_code.replace('/', '-')}-{la_code}",
            board=board,
            dry_run=dry_run,
        )
        if child_id:
            result["tasks"].append({"la_code": la_code, "task_id": child_id, "is_lead": prev_id is None})
            prev_id = child_id
        else:
            result["errors"].append(f"Failed to create child {la_code}")

    # TF-summary выполняется ПОСЛЕ всех TD: link last TD → TF
    if prev_id and not dry_run:
        link_result = run_hermes(["link", prev_id, tf_id], board=board)
        if link_result.returncode != 0:
            result["errors"].append(f"Failed to link last TD → TF: {link_result.stderr.strip()}")

    return result


def main():
    ap = argparse.ArgumentParser(description="Migrate to native kanban primitives")
    ap.add_argument("--otf", help="блок: A/B/C/D")
    ap.add_argument("--tf", help="одна ТФ, напр. С/01.7")
    ap.add_argument("--board", default=None, help="kanban board slug")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    mapping = load_mapping()
    all_tfs = load_all_tfs()

    # фильтры (кириллица → латиница)
    CYR_TO_LAT = {"А": "A", "В": "B", "С": "C"}
    def norm(code):
        code = code.upper().strip()
        return CYR_TO_LAT.get(code, code)

    if args.otf:
        f = norm(args.otf)
        all_tfs = [t for t in all_tfs if norm(t.get("_otf_code", "")) == f]
    if args.tf:
        f = args.tf.strip()
        all_tfs = [t for t in all_tfs if t.get("code", "") == f]

    if not all_tfs:
        print("No labor functions found.")
        sys.exit(1)

    print(f"Migrating {len(all_tfs)} ТФ to native kanban (board={args.board or 'default'})")
    stats = {"tf": 0, "td": 0, "errors": 0}
    for tf in all_tfs:
        r = migrate_tf(tf, mapping, args.board, args.dry_run)
        if r["errors"]:
            stats["errors"] += len(r["errors"])
            for e in r["errors"]:
                print(f"  [ERROR] {e}")
        stats["tf"] += 1
        stats["td"] += len(r["tasks"])
        print(f"  ✅ {r['tf_code']}: {len(r['tasks'])} TD создано"
              + (f", tf_task={r.get('tf_task_id')}" if r.get("tf_task_id") else ""))

    print(f"\nИтог: ТФ={stats['tf']}, TD={stats['td']}, ошибок={stats['errors']}")
    if stats["errors"]:
        sys.exit(2)


if __name__ == "__main__":
    main()
