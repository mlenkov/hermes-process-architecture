#!/usr/bin/env python3
"""Seed TF→TD pipeline from profstandart YAML into Hermes kanban.

Creates a parent-child DAG for each Трубовая Функция (ТФ):
  - Parent task: ТФ-level (workflow_template_id=LF-07.007-{code})
  - Child tasks: Трудовые Действия (ТД), linked via --parent

Usage:
    python3 scripts/seed-tf-pipeline.py                              # all 18 TFs
    python3 scripts/seed-tf-pipeline.py --otf A                      # only OTF-A
    python3 scripts/seed-tf-pipeline.py --tf "А/01.6"               # one TF
    python3 scripts/seed-tf-pipeline.py --dry-run                    # preview only
    python3 scripts/seed-tf-pipeline.py --remote                     # run via ssh on server
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

_ARCH_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_YAML_DIR = _ARCH_ROOT / "docs" / "standards" / "07.007"
YAML_DIR = _DEFAULT_YAML_DIR  # may be overridden

OTF_CODE_MAP = {
    "otf-section-1.yaml": "А",
    "otf-section-2.yaml": "В",
    "otf-section-3.yaml": "С",
    "otf-section-4.yaml": "D",
}

# 4 profiles per OTF, all mapped to 'mais' in current system
PROFILE = "mais"

OUTPUT_ROOT = _ARCH_ROOT / "outputs" / "07.007"  # file-based handoff root

# Cross-TF output registry: output_id → file path
# Populated during seeding so downstream TFs know where to find their inputs.
OUTPUT_REGISTRY: dict[str, str] = {}

# Skills per TF (OTF-A: pipeline-ready, OTF-B/C/D: placeholder)
TF_SKILLS = {
    "А": {
        "А/01.6": ["process-analysis"],
        "А/02.6": ["process-regulation"],
        "А/03.6": ["process-implementation"],
        "А/04.6": ["process-control"],
    },
    "В": {},
    "С": {},
    "D": {},
}

DEFAULT_SKILL = "kanban-worker"

# Источники истины (ADR-004): mapping → skill_path, registry → артефакты
MAPPING_PATH = _ARCH_ROOT / "outputs" / "07.007" / "block-D" / "labor-function-to-skill-mapping.yaml"
REGISTRY_PATH = _ARCH_ROOT / "outputs" / "07.007" / "labor-coverage-registry.yaml"


def load_mapping() -> dict:
    """tf_code → {"skill_path", "status"} из labor-function-to-skill-mapping.yaml."""
    data = load_yaml_safe(MAPPING_PATH) or {}
    out = {}
    for e in data.get("mappings", []):
        tf = e.get("tf_code")
        if tf:
            out[tf] = {
                "skill_path": e.get("skill_path", ""),
                "status": e.get("coverage_status", ""),
            }
    return out


def load_registry_data() -> dict:
    return load_yaml_safe(REGISTRY_PATH) or {}


def resolve_skill(tf_code: str, registry_data: dict, mapping: dict) -> tuple:
    """Вернуть (skill_name, skill_path) для ТФ.

    Приоритет: mapping (относительный skill_path) → registry (полный путь).
    skill_name — имя каталога навыка (используется как --skill в kanban).
    skill_path — полный путь profiles/mais/skills/<skill>/SKILL.md (кладётся в body, ADR-008).
    """
    rel = mapping.get(tf_code, {}).get("skill_path", "")
    if not rel:
        return DEFAULT_SKILL, ""
    skill_name = Path(rel).parent.name
    full = registry_data.get(f"LF-07.007-{tf_code}", {}).get("skill_path", "")
    return skill_name, full or rel


def resolve_artifact(tf_code: str, registry_data: dict) -> str:
    """Главный артефакт ТФ из registry.artifacts_generated (первый)."""
    entry = registry_data.get(f"LF-07.007-{tf_code}", {})
    artifacts = entry.get("artifacts_generated", [])
    return artifacts[0] if artifacts else ""


def load_yaml_safe(path: Path):
    """Load YAML, return None on failure."""
    try:
        import yaml
        with open(path) as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"  [WARN] Failed to load {path}: {e}", file=sys.stderr)
        return None


def load_all_tfs():
    """Load all labor functions from YAML directory, grouped by OTF."""
    yaml_files = sorted(YAML_DIR.glob("otf-section-*.yaml"))
    all_tfs = []
    for f in yaml_files:
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
    """Run hermes command and return result."""
    hermes_bin = os.environ.get("HERMES_BIN", "hermes")
    cmd = [hermes_bin, "kanban"]
    if board:
        cmd += ["--board", board]
    cmd += args
    env = os.environ.copy()
    env["PATH"] = "/home/hermes/.local/bin:" + env.get("PATH", "")
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )


def create_task(
    title: str,
    body: str = "",
    assignee: str = PROFILE,
    parent: Optional[str] = None,
    skills: list[str] | None = None,
    project: Optional[str] = None,
    dry_run: bool = False,
) -> Optional[str]:
    """Create a kanban task and return its task ID.

    Uses --json output to capture the task ID.
    workflow_template_id and step_key are stored in the body JSON
    (the CLI doesn't expose these create flags yet).
    """
    args = ["create", "--json", "--assignee", assignee]

    if body:
        args += ["--body", body]
    if parent:
        args += ["--parent", parent]
    if skills:
        for s in skills:
            args += ["--skill", s]
    if project:
        args += ["--project", project]

    args.append(title)

    if dry_run:
        print(f"  [DRY-RUN] hermes kanban create --json ... {' '.join(args[:10])}...")
        return f"dry-run-{hash(title) & 0xffff:04x}"

    result = run_hermes(args)
    if result.returncode != 0:
        print(f"  [ERROR] kanban create failed: {result.stderr.strip()}", file=sys.stderr)
        print(f"  [STDOUT] {result.stdout.strip()}", file=sys.stderr)
        return None

    try:
        data = json.loads(result.stdout.strip())
        return data.get("id")
    except json.JSONDecodeError:
        print(f"  [ERROR] Could not parse JSON from kanban create: {result.stdout[:200]}", file=sys.stderr)
        return None


def _resolve_input_path(input_id: str, tf_inputs: list,
                         td_output_paths: dict[str, str],
                         output_base: Path) -> str:
    """Resolve an input ID to a file path.

    Priority:
    1. Already produced by a TD in this TF (td_output_paths)
    2. Already in global OUTPUT_REGISTRY (from another TF)
    3. TF-level external input (source_tf=null) → outputs/{tf_dir}/inputs/{id}.yaml
    """
    # Already produced within this TF
    if input_id in td_output_paths:
        return td_output_paths[input_id]

    # From global registry (cross-TF handoff)
    if input_id in OUTPUT_REGISTRY:
        return OUTPUT_REGISTRY[input_id]

    # TF-level input — lookup its source_tf to determine path
    for inp in tf_inputs:
        if inp.get("id") == input_id:
            src = inp.get("source_tf")
            if src:
                # From another TF — must be in registry already
                if input_id in OUTPUT_REGISTRY:
                    return OUTPUT_REGISTRY[input_id]
            # External input — written by whoever provides the context
            ext_path = str(output_base / "inputs" / f"{input_id}.yaml")
            return ext_path

    # Fallback: assume external input
    return str(output_base / "inputs" / f"{input_id}.yaml")


def build_pipeline(tf: dict, dry_run: bool = False) -> dict:
    """Create kanban tasks for one TF as a sequential TD chain.

    Each TD depends on the previous one (TD1 → TD2 → TD3 → ...).
    TD1 is created ready (no parent), TD2 has parent=TD1, etc.

    Supports execution block from YAML (IDEF0 context: inputs/outputs,
    per-action skills, recommended profile). Falls back to hardcoded
    TF_SKILLS/PROFILE when execution block is absent.

    File-based handoff: each TD reads inputs from disk and writes
    outputs to disk. SQLite stores only paths, not data.

    Returns:
    {
        "tf_code": "А/01.6",
        "tasks": [{"la_code": "la-001", "task_id": "uuid-yyy", "is_lead": True}, ...],
        "errors": [...],
    }
    """
    result = {
        "tf_code": tf.get("code", "???"),
        "tasks": [],
        "errors": [],
    }

    otf_code = tf.get("_otf_code", "?")
    tf_code = tf.get("code", "?")
    tf_name = tf.get("name", "?")
    actions = tf.get("трудовые_действия", [])
    execution = tf.get("execution", {})
    lf_id = f"LF-07.007-{tf_code}"

    if not actions:
        result["errors"].append(f"No labor actions for {tf_code}")
        return result

    # ── Output directory (file-based handoff) ────────────────────────
    tf_dir_name = tf_code.replace("/", "-").replace(" ", "_")
    output_base = OUTPUT_ROOT / otf_code / tf_dir_name
    if not dry_run:
        output_base.mkdir(parents=True, exist_ok=True)

    # ── Resolve profile ──────────────────────────────────────────────
    profile = execution.get("recommended_profile", PROFILE)

    # ── Resolve per-action skills (mapping — источник истины, ADR-004) ──
    mapping = load_mapping()
    registry_data = load_registry_data()
    skill_name, skill_full_path = resolve_skill(tf_code, registry_data, mapping)
    artifact_path = resolve_artifact(tf_code, registry_data)

    exec_actions = execution.get("actions", [])
    if exec_actions:
        action_skills = [
            a.get("mechanism", {}).get("skills", [skill_name or DEFAULT_SKILL])
            for a in exec_actions
        ]
    elif skill_name:
        action_skills = [skill_name] * len(actions)
    else:
        otf_skills = TF_SKILLS.get(otf_code, {})
        tf_default = otf_skills.get(tf_code, otf_skills.get("__default__", [DEFAULT_SKILL]))
        action_skills = [tf_default] * len(actions)

    # ── Build TD chain metadata + resolve input/output paths ────────
    tf_inputs = execution.get("inputs", [])
    td_output_paths: dict[str, str] = {}  # output_id → real file path

    labor_actions = []
    td_entries = []  # list of (la_code, la_body_data, skills)
    for i, action_text in enumerate(actions, 1):
        la_code = f"la-{i:03d}"
        next_la = f"la-{(i+1):03d}" if i < len(actions) else None
        la_dir = output_base / la_code

        ea = exec_actions[i-1] if exec_actions and i <= len(exec_actions) else {}

        # IDEF0 ICOM IDs for this ТД
        td_in_ids = ea.get("inputs", [])
        td_out_ids = ea.get("outputs", [])

        # Resolve input paths
        input_files = [
            _resolve_input_path(pid, tf_inputs, td_output_paths, output_base)
            for pid in td_in_ids
        ]

        # Resolve output paths + register for downstream
        output_files = []
        if artifact_path:
            # Артефакт ТФ из registry (ADR-002: один артефакт = один файл).
            # Каждая ТД получает один и тот же целевой файл: первый ТД его
            # создаёт, последующие пропускаются Шагом 0 (ADR-007).
            output_files = [str(_ARCH_ROOT / artifact_path)]
        for oid in td_out_ids:
            opath = str(la_dir / f"{oid}.yaml")
            if opath not in output_files:
                output_files.append(opath)
            td_output_paths[oid] = opath  # downstream TDs can now find it

        # Create output dir
        if not dry_run:
            (output_base / la_code).mkdir(parents=True, exist_ok=True)

        # Task body
        la_body_data = {
            "la_id": la_code,
            "text": action_text,
            "sequence_index": i,
            "next_la": next_la,
            "parent_tf": lf_id,
            "otf_code": f"ОТФ-{otf_code}",
            "tf_task_id": "",
            "output_base": str(output_base),
            "output_dir": str(la_dir),
            "output_files": output_files,
            "input_files": input_files,
            "inputs": td_in_ids,
            "outputs": td_out_ids,
            "skill_path": skill_full_path,
            "skill": skill_name,
        }

        # Labor action entry for TF-level body
        la_entry = {
            "id": la_code,
            "text": action_text,
            "sequence_index": i,
            "profile": profile,
            "skill": (action_skills[i-1] or [DEFAULT_SKILL])[0],
            "inputs": td_in_ids,
            "outputs": td_out_ids,
            "output_files": output_files,
        }
        labor_actions.append(la_entry)
        td_entries.append((la_code, la_body_data, action_skills[i-1] if i <= len(action_skills) else [DEFAULT_SKILL]))

    # ── Register TF outputs globally (cross-TF handoff) ──────────────
    for oid, opath in td_output_paths.items():
        if oid in [o.get("id") for o in execution.get("outputs", [])]:
            # This is a TF-level output (last action's output IDs)
            OUTPUT_REGISTRY[oid] = opath

    # ── TF-level body ────────────────────────────────────────────────
    tf_body_data = {
        "type": "tf_pipeline",
        "standard": {"code": "07.007"},
        "function": {"code": tf_code, "name": tf_name},
        "total_actions": len(actions),
        "output_base": str(output_base),
        "skill_path": skill_full_path,
        "skill": skill_name,
        "labor_actions": labor_actions,
    }
    if tf_inputs:
        tf_body_data["tf_inputs"] = tf_inputs
    if execution.get("outputs"):
        tf_body_data["tf_outputs"] = execution["outputs"]
    tf_body = json.dumps(tf_body_data, ensure_ascii=False)

    # ── Create TF summary task ──────────────────────────────────────
    tf_title = f"🔄 {tf_code}: {tf_name[:80]}"
    if not dry_run:
        print(f"  Creating TF pipeline: {tf_title}")
    tf_skills = action_skills[0] if action_skills else [DEFAULT_SKILL]
    tf_id = create_task(
        title=tf_title,
        body=tf_body,
        assignee=profile,
        skills=tf_skills,
        dry_run=dry_run,
    )
    if not tf_id:
        result["errors"].append(f"Failed to create TF task for {tf_code}")
        return result
    result["tf_task_id"] = tf_id

    # ── Create TD chain: TD1 ← TD2 ← ... ← TDN ─────────────────────
    prev_id = None
    for la_code, la_body_data, td_skills in td_entries:
        la_body_data["tf_task_id"] = tf_id
        la_body = json.dumps(la_body_data, ensure_ascii=False)

        child_title = f"  {la_code}: {la_body_data['text'][:60]}"
        if not dry_run:
            print(f"    Creating TD: {la_code} — {la_body_data['text'][:40]}...")

        child_id = create_task(
            title=child_title,
            body=la_body,
            assignee=profile,
            parent=prev_id,
            skills=td_skills,
            dry_run=dry_run,
        )

        if child_id:
            result["tasks"].append({"la_code": la_code, "task_id": child_id, "is_lead": prev_id is None})
            prev_id = child_id
        else:
            result["errors"].append(f"Failed to create child {la_code}")

    # Link last TD as parent of TF task (TF completes after all TDs)
    if prev_id and not dry_run:
        link_result = run_hermes(["link", prev_id, tf_id])
        if link_result.returncode != 0:
            result["errors"].append(f"Failed to link last TD → TF: {link_result.stderr.strip()}")

    return result


def seed_all(args):
    """Seed all or filtered TFs."""
    all_tfs = load_all_tfs()

    if not all_tfs:
        print("No labor functions found.", file=sys.stderr)
        sys.exit(1)

    # Apply filters (normalize Cyrillic→Latin)
    CYR_TO_LAT = {'А': 'A', 'В': 'B', 'С': 'C'}

    def norm_otf(code):
        code = code.upper().strip()
        return CYR_TO_LAT.get(code, code)

    if args.otf:
        otf_filter = norm_otf(args.otf)
        all_tfs = [tf for tf in all_tfs
                   if norm_otf(tf.get("_otf_code", "")) == otf_filter]

    if args.tf:
        tf_filter = args.tf.strip()
        all_tfs = [tf for tf in all_tfs
                   if tf.get("code", "") == tf_filter]

    total_tfs = len(all_tfs)
    total_tds = sum(len(tf.get("трудовые_действия", [])) for tf in all_tfs)

    # Clean existing tasks if requested
    if args.clean and not args.dry_run:
        print("Archiving existing tasks...")
        existing = run_hermes(["list", "--json"])
        if existing.returncode == 0:
            try:
                tasks = json.loads(existing.stdout.strip())
                ids = [t["id"] for t in tasks if t.get("id")]
                if ids:
                    result = run_hermes(["archive"] + ids)
                    if result.returncode == 0:
                        print(f"  Archived {len(ids)} tasks")
                    else:
                        print(f"  Archive partial: {result.stderr.strip()}")
                else:
                    print("  No tasks to archive")
            except (json.JSONDecodeError, KeyError):
                print("  No tasks found")

    print(f"Seeding pipeline: {total_tfs} TFs, {total_tds} TDs")
    print(f"Dry-run: {'YES' if args.dry_run else 'NO'}")
    print()

    results = []
    errors = []

    for tf in all_tfs:
        result = build_pipeline(tf, dry_run=args.dry_run)
        results.append(result)
        if result["errors"]:
            errors.extend(result["errors"])
        if result.get("tasks"):
            lead_count = sum(1 for t in result["tasks"] if t.get("is_lead"))
            print(f"  ✅ {result['tf_code']}: "
                  f"tf_task={result.get('tf_task_id','?')[:8]}..., "
                  f"td_tasks={len(result['tasks'])} "
                  f"(lead={lead_count})")

    print()
    print("=" * 60)

    if not args.dry_run:
        tfs_ok = sum(1 for r in results if r.get("tf_task_id"))
        tds_ok = sum(len(r.get("tasks", [])) for r in results)
        print(f"Created: {tfs_ok}/{total_tfs} TF tasks, "
              f"{tds_ok}/{total_tds} TD tasks")

    if errors:
        print(f"Errors: {len(errors)}")
        for e in errors[:5]:
            print(f"  - {e}")

    # Summary table
    print()
    print("Pipeline summary:")
    print(f"{'TF':<12} {'TF-Task':<10} {'TDs':<10} {'Chain':<15} {'Status':<10}")
    print("-" * 57)
    for r in results:
        status = "✅" if r.get("tf_task_id") and not r["errors"] else "❌"
        td_ids = ",".join(t["task_id"][:6] for t in r.get("tasks", []))[:14]
        print(f"{r['tf_code']:<12} "
              f"{str(r.get('tf_task_id','?'))[:8]:<10} "
              f"{len(r.get('tasks',[])):<10} "
              f"{td_ids:<15} "
              f"{status:<10}")


def main():
    parser = argparse.ArgumentParser(description="Seed TF→TD pipeline into Hermes kanban")
    parser.add_argument("--otf", help="Filter by OTF code (A, B, C, D)")
    parser.add_argument("--tf", help="Filter by TF code (e.g. А/01.6)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without creating tasks")
    parser.add_argument("--clean", action="store_true", help="Archive all existing tasks before seeding")
    parser.add_argument("--yaml-dir", default=str(YAML_DIR), help="Path to YAML directory")
    args = parser.parse_args()

    yaml_dir = Path(args.yaml_dir)
    if not yaml_dir.exists():
        print(f"Error: YAML directory not found: {yaml_dir}", file=sys.stderr)
        sys.exit(1)

    import sys as _sys
    _sys.modules['__main__'].YAML_DIR = yaml_dir

    seed_all(args)


if __name__ == "__main__":
    main()
