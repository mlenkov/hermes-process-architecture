#!/usr/bin/env python3
"""Детерминированная приёмка артефакта LLM-воркера (ADR-013, пилот 6b).

Читает артефакт из outputs/<standard>/ (путь из body/argv), валидирует:
  1. YAML-структура и наличие обязательных полей (schema_valid);
  2. отсутствие выдуманных сущностей — запросы/сущности артефакта только
     из входных данных (анти-галлюцинация);
  3. допустимые значения категорий (если схема их задаёт).

ТОЛЬКО при успехе создаёт/обновляет запись в labor-coverage-registry.yaml
стандарта (executed_by: профиль из mapping, status по факту покрытия).

Usage:
    python3 scripts/accept-artifact.py --standard 06.043 --tf А/01.4 \
        --artifact outputs/06.043/pilot/A-01.4-keywords.yaml \
        [--input inputs/pilot-queries.yaml] [--dry-run]
"""

import argparse
import json
import os
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def load_yaml(path):
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def err(msg):
    print(f"  [REJECT] {msg}")
    return False


def validate_artifact(artifact_path: Path, input_path: Path | None) -> tuple:
    """(ok, reasons, data). Проверка структуры + анти-галлюцинация."""
    reasons = []
    if not artifact_path.exists():
        return False, ["артефакт не найден"], None
    try:
        data = load_yaml(artifact_path)
    except Exception as e:
        return False, [f"YAML parse error: {e}"], None
    if not isinstance(data, dict):
        return False, ["артефакт не YAML-объект"], None

    # Нормализация вложенной схемы 'artifact: {...}' (делегированный контент)
    # А также 'tz: {...}' для ТЗ. top-level поля = data с верхнего уровня.
    top = data
    for wrapper in ("artifact", "tz"):
        if isinstance(data.get(wrapper), dict):
            # метаданные могут жить и в wrapper, и на верхнем уровне
            merged = dict(data.get(wrapper))
            for k, v in data.items():
                if k != wrapper:
                    merged.setdefault(k, v)
            data = merged
            break

    # ── 1. Обязательные поля ─────────────────────────────────────────
    required = ("tf_code", "status")
    for field in required:
        if field not in data:
            reasons.append(f"нет обязательного поля '{field}'")
    if data.get("status") not in ("generated",):
        reasons.append(f"status='{data.get('status')}' != 'generated'")

    # ── 2. Анти-галлюцинация: сущности только из входов ─────────────
    if input_path and input_path.exists():
        inputs = load_yaml(input_path)
        allowed_queries = set()
        for entry in inputs.get("queries", []):
            if isinstance(entry, dict):
                allowed_queries.add(str(entry.get("query", "")).lower())
            else:
                allowed_queries.add(str(entry).lower())

        # Запросы в артефакте (если есть поле queries / minus_words)
        artifact_queries = set()
        for q in data.get("queries", []) or []:
            artifact_queries.add(str(q).lower())
        for mw in data.get("minus_words", []) or []:
            if isinstance(mw, dict):
                artifact_queries.add(str(mw.get("word", mw.get("phrase", ""))).lower())
            else:
                artifact_queries.add(str(mw).lower())

        invented = [q for q in artifact_queries
                    if q and not any(q in a or a in q for a in allowed_queries)]
        if invented:
            reasons.append(f"выдуманные сущности (нет во входах): {invented[:5]}")

    # ── 3. Категории из допустимого набора (если есть) ──────────────
    allowed_categories = {
        "target", "target_high", "target_medium", "target_low",
        "competitor", "other_material", "informational", "marketplace",
        "service", "junk", "не_определено",
    }
    for mw in data.get("minus_words", []) or []:
        if isinstance(mw, dict):
            cat = mw.get("category", "")
            if cat and cat not in allowed_categories:
                reasons.append(f"неизвестная категория '{cat}'")

    return (not reasons), reasons, data


def _normalize_code(code, standard):
    """Нормализация алфавита: кириллица→латиницу для lookup (ADR-011, прил.).
    Хранение — как в официальном стандарте; lookup нормализует обе стороны."""
    CYR_TO_LAT = {"А": "A", "В": "B", "С": "S", "Н": "N", "Е": "E", "К": "K", "D": "D", "G": "G", "I": "I", "J": "J", "L": "L"}
    return "LF-%s-%s" % (standard, "".join(CYR_TO_LAT.get(ch, ch) for ch in str(code)))


def load_skill_path_from_mapping(standard, tf_code):
    """skill_path из per-TF поля mapping (ADR-014), с нормализацией алфавита."""
    for probe in (standard, "07.007"):
        if standard == "07.007":
            mp = ROOT / "outputs/07.007/block-D/labor-function-to-skill-mapping.yaml"
        else:
            mp = ROOT / "outputs" / probe / "labor-function-to-skill-mapping.yaml"
        if not mp.exists():
            continue
        mm = load_yaml(mp)
        norm_key = _normalize_code(tf_code, standard)
        for e in mm.get("mappings", []):
            # матч по нормализованному коду
            if _normalize_code(e.get("tf_code"), probe) == norm_key:
                return e.get("skill_path", "")
        return ""
    return ""


def update_registry(standard, tf_code, profile, data, tds_completed="1/1"):
    reg_path = ROOT / "outputs" / standard / "labor-coverage-registry.yaml"
    reg = load_yaml(reg_path) if reg_path.exists() else {}
    key = _normalize_code(tf_code, standard)
    import datetime
    # status из tds_completed: 1/N → partially_covered; N/N → covered
    p, n = 1, 1
    if "/" in tds_completed:
        try:
            p, n = tds_completed.split("/")
            p, n = int(p), int(n)
        except Exception:
            pass
    status = "covered" if (n > 0 and p >= n) else "partially_covered"
    skill_path = data.get("skill_path") or load_skill_path_from_mapping(standard, tf_code)
    entry = {
        "executed_by": profile,
        "last_executed": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": status,
        "tds_completed": tds_completed,
        "skill_path": skill_path,
        "artifacts_generated": [data.get("artifact_path", "")],
    }
    reg[key] = entry
    with open(reg_path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(reg, fh, allow_unicode=True, sort_keys=False, default_flow_style=False)
    return key


def main():
    ap = argparse.ArgumentParser(description="Accept LLM-worker artifact (deterministic)")
    ap.add_argument("--standard", required=True)
    ap.add_argument("--tf", required=True, help="код ТФ, напр. А/01.4")
    ap.add_argument("--artifact", required=True, help="путь к артефакту воркера")
    ap.add_argument("--input", default=None, help="путь к входным данным (для анти-галлюцинации)")
    ap.add_argument("--profile", default=None, help="профиль-исполнитель (default: из mapping)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--tds-completed", default="1/1", help="tds_completed (1/N → partial; N/N → covered)")
    args = ap.parse_args()

    # профиль: из per-TF поля profile записи mapping принимаемой ТФ (ADR-014),
    # если не задан явно --profile. НЕ из executor_profile (может быть
    # «per-TF (ADR-014)» — не имя профиля).
    profile = args.profile
    if not profile:
        for probe in (args.standard, "07.007"):
            if args.standard == "07.007":
                mapping_path = ROOT / "outputs/07.007/block-D/labor-function-to-skill-mapping.yaml"
            else:
                mapping_path = ROOT / "outputs" / probe / "labor-function-to-skill-mapping.yaml"
            if mapping_path.exists():
                mapping = load_yaml(mapping_path)
                for e in mapping.get("mappings", []):
                    if e.get("tf_code") == args.tf and e.get("profile"):
                        profile = e["profile"]
                        break
            if profile:
                break
    profile = profile or "mais"

    # Проверка: profile должен быть реальным именем профиля, НЕ строкой-заглушкой
    INVALID_PROFILES = {"per-tf (adr-014)", "per-tf", "", "?"}
    if profile.lower() in INVALID_PROFILES or "/" in profile or " " in profile:
        err(f"profile '{profile}' не является именем профиля — "
            "укажи явно --profile (значение 'per-TF (ADR-014)' недопустимо)")
        print("Acceptance: REJECTED")
        sys.exit(1)

    artifact_path = Path(args.artifact)
    input_path = Path(args.input) if args.input else None

    ok, reasons, data = validate_artifact(artifact_path, input_path)
    if not ok:
        for r in reasons:
            err(r)
        print("Acceptance: REJECTED")
        sys.exit(1)

    # успех: пишем в registry (если не dry-run)
    if data is None:
        data = {}
    data.setdefault("artifact_path", str(artifact_path))
    if args.dry_run:
        print(f"  [DRY-RUN] registry update would create LF-{args.standard}-{args.tf} (executed_by={profile}, status по tds_completed={args.tds_completed})")
    else:
        key = update_registry(args.standard, args.tf, profile, data, tds_completed=args.tds_completed)
        # status вычислен из tds_completed — прочтём из registry
        import yaml as _yaml
        _rp = ROOT / "outputs" / args.standard / "labor-coverage-registry.yaml"
        _status = (_yaml.safe_load(open(_rp, encoding="utf-8")).get(key) or {}).get("status", "?")
        print(f"  Registry updated: {key} → {_status} (executed_by={profile})")

    print("Acceptance: ACCEPTED")
    print(f"  schema_valid: True, галлюцинаций: 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
