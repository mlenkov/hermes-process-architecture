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
_DEFAULT_STANDARD = "07.007"
_PROFILE = "mais"

OTF_CODE_MAP = {
    "otf-section-1.yaml": "А",
    "otf-section-2.yaml": "В",
    "otf-section-3.yaml": "С",
    "otf-section-4.yaml": "D",
}


def standard_yaml_dir(standard: str) -> Path:
    """docs/standards/<S>/ (нормы)."""
    return _ARCH_ROOT / "docs" / "standards" / standard


def standard_output_root(standard: str) -> Path:
    """outputs/<S>/ (артефакты)."""
    return _ARCH_ROOT / "outputs" / standard


def standard_registry_path(standard: str) -> Path:
    """Registry стандарта: outputs/<S>/labor-coverage-registry.yaml (ADR-011)."""
    return standard_output_root(standard) / "labor-coverage-registry.yaml"


def load_registry_data(standard: str) -> dict:
    return load_yaml_safe(standard_registry_path(standard)) or {}


def resolve_skill(tf_code: str, registry_data: dict, mapping: dict) -> tuple:
    """(skill_name, skill_path) для ТФ. mapping (relative) → registry (full)."""
    rel = mapping.get(tf_code, {}).get("skill_path", "")
    if not rel:
        return "kanban-worker", ""
    skill_name = Path(rel).parent.name
    full = registry_data.get(f"LF-{_DEFAULT_STANDARD}-{tf_code}", {}).get("skill_path", "")
    if not full:
        # попытка по текущему стандарту (для новых стандартов — registry ещё пуст)
        full = registry_data.get(f"LF-{mapping.get('_standard', _DEFAULT_STANDARD)}-{tf_code}", {}).get("skill_path", "")
    return skill_name, full or rel


def resolve_artifact(tf_code: str, registry_data: dict, standard: str) -> str:
    """Главный артефакт ТФ из registry.artifacts_generated (первый)."""
    entry = registry_data.get(f"LF-{standard}-{tf_code}", {})
    artifacts = entry.get("artifacts_generated", [])
    return artifacts[0] if artifacts else ""


def extract_icom_artifacts(skill_full_path: str, standard: str = _DEFAULT_STANDARD) -> list:
    """Зависимости ТФ из ## ICOM Inputs SKILL.md (ADR: dependency-aware).

    Пути нормализуются к outputs/<standard>/<path>. Для 07.007 legacy —
    как раньше (outputs/07.007/...). Пути вне outputs игнорируются.
    """
    if not skill_full_path or not os.path.exists(skill_full_path):
        return []
    try:
        text = Path(skill_full_path).read_text(encoding="utf-8")
    except OSError:
        return []
    m = re.search(r"## ICOM(.*?)(## Rules|## Thinking|## Process)", text, re.S)
    if not m:
        return []
    icom = m.group(1)
    im = re.search(r"\*\*Inputs:\*\*(.*?)(\*\*Outputs:\*\*|$)", icom, re.S)
    if not im:
        return []
    out = []
    prefix = f"outputs/{standard}/"
    for line in im.group(1).splitlines():
        s = line.strip()
        mm = re.match(r"^-? ?`([^`]+)`", s)
        if not mm:
            continue
        p = mm.group(1).strip()
        norm = None
        if p.startswith(prefix):
            norm = p
        elif p.startswith(("block-A/", "block-B/", "block-C/", "block-D/",
                           "labor-coverage-registry.yaml", "monitor/", "pdca-reports/")):
            norm = f"{prefix}{p}"
        if norm and norm not in out:
            out.append(norm)
    return out


def standard_mapping_path(standard: str) -> Path:
    """Mapping стандарта: legacy block-D/ для 07.007, root-layout для остальных (ADR-011)."""
    out_root = standard_output_root(standard)
    if standard == "07.007":
        return out_root / "block-D" / "labor-function-to-skill-mapping.yaml"
    return out_root / "labor-function-to-skill-mapping.yaml"


def standard_board(standard: str) -> str:
    """Kanban-борд per-standard (ADR-011/014).

    Явный маппинг (конвенция из ADR-011: 06.043 → std-0643, борд создан
    при онбординге стандарта). Fallback — digits без точки.
    """
    BOARD_MAP = {
        "06.043": "std-0643",
        "07.007": "std-7007",
        "06.013": "std-0613",
    }
    if standard in BOARD_MAP:
        return BOARD_MAP[standard]
    digits = re.sub(r"\D", "", standard).lstrip("0")
    return f"std-{digits}" if digits else "default"


def load_mapping(standard: str) -> dict:
    """tf_code → {skill_path, status, profile}. Профиль per-TF (ADR-014)."""
    data = load_yaml_safe(standard_mapping_path(standard)) or {}
    out = {}
    for e in data.get("mappings", []):
        tf = e.get("tf_code")
        if tf:
            out[tf] = {
                "skill_path": e.get("skill_path", ""),
                "status": e.get("coverage_status", ""),
                "profile": e.get("profile", ""),
            }
    # Профиль-исполнитель: executor_profile в заголовке mapping (ADR-011).
    out["_executor_profile"] = data.get("executor_profile", _PROFILE)
    return out


def load_yaml_safe(path: Path):
    try:
        import yaml
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"  [WARN] Failed to load {path}: {e}", file=sys.stderr)
        return None


def load_all_tfs(standard: str = _DEFAULT_STANDARD):
    """Все ТФ из otf-секций стандарта (labor_functions), с _otf_code/_source_file."""
    all_tfs = []
    yaml_dir = standard_yaml_dir(standard)
    if not yaml_dir.exists():
        print(f"standard not found: {standard} (нет {yaml_dir})", file=sys.stderr)
        return all_tfs
    for f in sorted(yaml_dir.glob("otf-section-*.yaml")):
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


def migrate_tf(tf: dict, mapping: dict, standard: str, board: Optional[str],
               dry_run: bool, profile: str) -> dict:
    """Создать TF-задачу + TD-цепочку для одной ТФ через нативные примитивы."""
    otf_code = tf.get("_otf_code", "?")
    tf_code = tf.get("code", "?")
    tf_name = tf.get("name", "?")
    actions = tf.get("трудовые_действия", [])
    lf_id = f"LF-{standard}-{tf_code}"

    result = {"tf_code": tf_code, "tasks": [], "errors": []}

    if not actions:
        result["errors"].append(f"No labor actions for {tf_code}")
        return result

    entry = mapping.get(tf_code, {})
    # ADR-014: профиль-исполнитель per-ТФ (поле profile в mapping).
    # Для 07.007 — общий fallback (executor_profile); для доменных — per-TF.
    tf_profile = entry.get("profile") or profile
    skill_name = os.path.basename(entry.get("skill_path", "")).replace("/SKILL.md", "") or "kanban-worker"
    idem_prefix = f"tf-{standard}-{tf_code.replace('/', '-')}"

    # ── Registry-aware: полный путь навыка + главный артефакт ТФ (ADR-002/004) ──
    registry_data = load_registry_data(standard)
    skill_name, skill_full_path = resolve_skill(tf_code, registry_data, mapping)
    artifact_path = resolve_artifact(tf_code, registry_data, standard)
    depends_on_artifacts = extract_icom_artifacts(skill_full_path, standard) if skill_full_path else []

    # ── Output directory (file-based handoff) ────────────────────────
    tf_dir_name = tf_code.replace("/", "-").replace(" ", "_")
    output_base = standard_output_root(standard) / otf_code / tf_dir_name

    # ── TF-level body (та же схема, что в seed — executor её понимает) ──
    tf_body = json.dumps({
        "type": "tf_pipeline",
        "standard": {"code": standard},
        "function": {"code": tf_code, "name": tf_name},
        "total_actions": len(actions),
        "profile": tf_profile,
        "skill_path": skill_full_path or entry.get("skill_path", ""),
        "skill": skill_name,
        "depends_on_artifacts": depends_on_artifacts,
        "labor_actions": [
            {"id": f"la-{i:03d}", "text": a, "sequence_index": i, "profile": tf_profile,
             "skill": skill_name}
            for i, a in enumerate(actions, 1)
        ],
    }, ensure_ascii=False)

    tf_id = create_task(
        title=f"🔄 {tf_code}: {tf_name[:80]}",
        body=tf_body,
        assignee=tf_profile,
        idem_key=idem_prefix,
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
        # Вывод ТД: только маппированный артефакт ТФ (ADR-002). Per-TD папки
        # и la-файлы НЕ создаём — мусор вне mapped путей (харденинг 8с).
        td_output_files = []
        if artifact_path:
            td_output_files.append(str(_ARCH_ROOT / artifact_path))

        la_body = json.dumps({
            "la_id": la_code,
            "text": action_text,
            "sequence_index": i,
            "next_la": f"la-{(i+1):03d}" if i < len(actions) else None,
            "parent_tf": lf_id,
            "otf_code": f"ОТФ-{otf_code}",
            "standard": {"code": standard},
            "profile": tf_profile,
            "output_base": str(output_base),
            "output_files": td_output_files,
            "skill_path": skill_full_path or entry.get("skill_path", ""),
            "skill": skill_name,
            "depends_on_artifacts": depends_on_artifacts,
        }, ensure_ascii=False)

        child_id = create_task(
            title=f"  {la_code}: {action_text[:60]}",
            body=la_body,
            assignee=tf_profile,
            parent=prev_id,
            idem_key=f"{idem_prefix}-{la_code}",
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
    ap.add_argument("--standard", default=_DEFAULT_STANDARD, help="код профстандарта (default: 07.007)")
    ap.add_argument("--otf", help="блок: A/B/C/D")
    ap.add_argument("--tf", help="одна ТФ, напр. С/01.7")
    ap.add_argument("--board", default=None, help="kanban board slug (default: std-<digits>)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    standard = args.standard
    mapping = load_mapping(standard)
    all_tfs = load_all_tfs(standard)
    profile = mapping.get("_executor_profile", _PROFILE)
    board = args.board or standard_board(standard)

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

    print(f"Migrating {len(all_tfs)} ТФ (standard={standard}) to native kanban "
          f"(board={board}, profile={profile})")
    stats = {"tf": 0, "td": 0, "errors": 0}
    for tf in all_tfs:
        r = migrate_tf(tf, mapping, standard, board, args.dry_run, profile)
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
