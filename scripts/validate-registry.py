#!/usr/bin/env python3
"""Проверка консистентности labor-function-to-skill-mapping ↔ labor-coverage-registry.

Для каждой ТФ из mapping со статусом covered/partially_covered:
  1. в registry существует запись LF-{standard}-{tf_code};
  2. skill_path в registry совпадает с skill_path в mapping (по имени навыка).
Семантика (8e): covered без записи → ERROR; partially_covered без записи
→ WARN «назначено, но не исполнено» (статическое покрытие по mapping vs
динамическое — registry после исполнения).

Поддерживает несколько профстандартов (ADR-011):
  --standard 07.007 (default) — legacy-схема: mapping в block-D/, registry в outputs/<S>/
  --standard <код>            — root-layout: mapping и registry в outputs/<S>/

Вывод: 'Registry valid: True/False' + список рассинхронизаций.
"""

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STANDARD = "07.007"

COVERED_STATUSES = {"covered", "partially_covered"}


def load_yaml(path: Path):
    if not path.exists():
        sys.exit(f"File not found: {path}")
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def skill_name(skill_path: str) -> str:
    """Из полного пути 'profiles/mais/skills/info-gatherer/SKILL.md' -> 'info-gatherer'."""
    return Path(skill_path).parent.name


def resolve_paths(standard: str):
    """Пути mapping/registry для стандарта (legacy для 07.007, root для остальных)."""
    out_root = ROOT / "outputs" / standard
    if standard == "07.007":
        mapping = out_root / "block-D" / "labor-function-to-skill-mapping.yaml"
    else:
        mapping = out_root / "labor-function-to-skill-mapping.yaml"
    registry = out_root / "labor-coverage-registry.yaml"
    return mapping, registry


def normalize_code(code: str) -> str:
    """Нормализация алфавита: кириллица→латиница для lookup (ADR-011, прил.).
    Хранение — как в официальном стандарте; lookup нормализует обе стороны."""
    CYR_TO_LAT = {"А": "A", "В": "B", "С": "S", "Н": "N", "Е": "E", "К": "K"}
    return "".join(CYR_TO_LAT.get(ch, ch) for ch in str(code))


def registry_key(standard: str, tf_code: str) -> str:
    # ключ registry строится с нормализованным алфавитом (А→A и т.д.)
    return f"LF-{standard}-{normalize_code(tf_code)}"


def skill_file_exists(skill_path: str) -> bool:
    """Проверка существования навыка (по имени) в любом профиле Hermes или репо."""
    if not skill_path:
        return True  # пустой путь обрабатывается отдельно
    skill = skill_name(skill_path)  # 'info-gatherer'
    # ~/.hermes/profiles/<p>/skills/<cat>/<skill>/SKILL.md
    hp = Path.home() / ".hermes" / "profiles"
    if list(hp.glob(f"*/skills/*/{skill}/SKILL.md")) or \
       list(hp.glob(f"*/skills/{skill}/SKILL.md")) or \
       list(hp.glob(f"*/skills/agency/{skill}/SKILL.md")):
        return True
    # репозиторий profiles/<p>/skills/<skill>/
    for rep in (ROOT / "profiles").glob("*/skills/*"):
        if rep.name == skill and (rep / "SKILL.md").exists():
            return True
    return False


def validate(standard: str) -> int:
    mapping_path, registry_path = resolve_paths(standard)

    if not mapping_path.exists() and not registry_path.exists():
        print(f"standard not found: {standard} "
              f"(нет {mapping_path.parent} и {registry_path})")
        return 2

    mapping = load_yaml(mapping_path)
    registry = load_yaml(registry_path)

    errors = []
    warns = []
    checked = 0
    documented_gaps = registry.get("documented_gaps", {})
    # нормализованный вид documented_gaps (ключи могут быть кириллическими)
    norm_gaps = {normalize_code(str(k).split(f"LF-{standard}-")[-1]): v
                 for k, v in documented_gaps.items()}
    map_keys = set()

    # Нормализованный маппинг код → запись (из mapping)
    norm_mapping = {}
    for entry in mapping.get("mappings", []):
        tf_code = entry.get("tf_code")
        ncode = normalize_code(tf_code)
        norm_mapping.setdefault(ncode, []).append(entry)
        if entry.get("coverage_status") in COVERED_STATUSES:
            checked += 1

    # Нормализованный registry: ключ (норм. алфавит) → запись (ADR-011, прил.)
    norm_registry = {}
    for key, val in registry.items():
        skey = str(key)
        if not skey.startswith(f"LF-{standard}-"):
            continue
        code = skey.split(f"LF-{standard}-")[-1]
        norm_registry[normalize_code(code)] = (skey, val)

    # ── 1. Записи registry, отсутствующие в mapping (ERROR) ────────
    for code, (skey, _v) in norm_registry.items():
        if code not in norm_mapping:
            errors.append(f"{skey}: запись registry для ТФ, отсутствующей в mapping")

    def reg_lookup(ncode):
        """Реальный ключ registry (для сообщений) + запись."""
        hit = norm_registry.get(ncode)
        if hit:
            return hit[1]
        return None

    # ── 2. По каждой ТФ из mapping ──────────────────────────────────
    for ncode, entries in norm_mapping.items():
        key = registry_key(standard, entries[0].get("tf_code"))
        entry = entries[0]
        status = entry.get("coverage_status")
        if status not in COVERED_STATUSES:
            continue
        skill_path = entry.get("skill_path", "")

        # mapping указывает на несуществующий файл навыка (ERROR)
        if skill_path and not skill_file_exists(skill_path):
            errors.append(f"{key}: mapping указывает на несуществующий навык '{skill_path}'")

        reg_entry = reg_lookup(ncode)
        if reg_entry is None:
            gap = norm_gaps.get(ncode)
            if gap:
                gap_skill = gap.get("skill_path", "")
                if skill_path and gap_skill and skill_name(gap_skill) != skill_name(skill_path):
                    errors.append(
                        f"{key}: documented_gaps.skill_path '{gap_skill}' "
                        f"не совпадает с mapping '{skill_path}'"
                    )
                continue
            if status == "covered":
                errors.append(
                    f"{key}: статус 'covered' в mapping, но запись в registry отсутствует"
                )
            else:
                warns.append(
                    f"{key}: статус 'partially_covered', но не исполнено (registry пуст) — WARN"
                )
            continue

        reg_skill = reg_entry.get("skill_path")

        # skill_path mismatch (ERROR)
        if skill_path and reg_skill:
            if skill_name(reg_skill) != skill_name(skill_path):
                errors.append(
                    f"{key}: skill_path не совпадает — mapping='{skill_path}', "
                    f"registry='{reg_skill}'"
                )
        elif not reg_skill:
            errors.append(f"{key}: в registry не указан skill_path")

        # covered без основного артефакта на диске (ERROR)
        if reg_entry.get("status") == "covered":
            artifacts = reg_entry.get("artifacts_generated", []) or []
            if not any(a and (ROOT / str(a)).exists() for a in artifacts):
                errors.append(
                    f"{key}: status 'covered' в registry, но основной артефакт отсутствует на диске"
                )

    print(f"Проверено ТФ со статусом {sorted(COVERED_STATUSES)}: {checked}")
    print(f"Записей в registry: {sum(1 for k in registry if str(k).startswith(f'LF-{standard}-'))}")
    if documented_gaps:
        print(f"Documented gaps: {len(documented_gaps)} ({', '.join(sorted(documented_gaps))})")
    if warns:
        print(f"Предупреждений (назначено, не исполнено): {len(warns)}")
        for w in warns:
            print(f"  ⚠ {w}")
    if errors:
        print(f"Найдено рассинхронизаций: {len(errors)}")
        for err in errors:
            print(f"  ✗ {err}")
        print("Registry valid: False")
        return 1

    print("Registry valid: True")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Validate registry ↔ mapping consistency")
    ap.add_argument("--standard", default=DEFAULT_STANDARD, help="код профстандарта (default: 07.007)")
    args = ap.parse_args()
    sys.exit(validate(args.standard))

