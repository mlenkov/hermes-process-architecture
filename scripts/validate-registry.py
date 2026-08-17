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

    for entry in mapping.get("mappings", []):
        tf_code = entry.get("tf_code")
        status = entry.get("coverage_status")
        if status not in COVERED_STATUSES:
            continue

        checked += 1
        key = f"LF-{standard}-{tf_code}"

        if key not in registry:
            gap = documented_gaps.get(key)
            if gap:
                gap_skill = gap.get("skill_path", "")
                map_skill = entry.get("skill_path", "")
                if map_skill and gap_skill and skill_name(gap_skill) != skill_name(map_skill):
                    errors.append(
                        f"{key}: documented_gaps.skill_path '{gap_skill}' "
                        f"не совпадает с mapping '{map_skill}'"
                    )
                continue
            if status == "covered":
                errors.append(
                    f"{key}: статус 'covered' в mapping, но запись в registry отсутствует"
                )
            else:
                # partially_covered без записи — назначено, но не исполнено (WARN)
                warns.append(
                    f"{key}: статус 'partially_covered', но не исполнено (registry пуст) — WARN"
                )
            continue

        reg_entry = registry[key]
        reg_skill = reg_entry.get("skill_path")
        map_skill = entry.get("skill_path")

        if map_skill and reg_skill:
            if skill_name(reg_skill) != skill_name(map_skill):
                errors.append(
                    f"{key}: skill_path не совпадает — mapping='{map_skill}', "
                    f"registry='{reg_skill}'"
                )
        elif not reg_skill:
            errors.append(f"{key}: в registry не указан skill_path")

    print(f"Проверено ТФ со статусом {sorted(COVERED_STATUSES)}: {checked}")
    print(f"Записей в registry: {sum(1 for k in registry if k.startswith(f'LF-{standard}-'))}")
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

