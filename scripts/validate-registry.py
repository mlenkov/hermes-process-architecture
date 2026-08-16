#!/usr/bin/env python3
"""Проверка консистентности labor-function-to-skill-mapping ↔ labor-coverage-registry.

Для каждой ТФ из mapping со статусом covered/partially_covered:
  1. в registry существует запись LF-07.007-{tf_code};
  2. skill_path в registry совпадает с skill_path в mapping (по имени навыка).

Вывод: 'Registry valid: True/False' + список рассинхронизаций.
"""

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
MAPPING_PATH = ROOT / "outputs/07.007/block-D/labor-function-to-skill-mapping.yaml"
REGISTRY_PATH = ROOT / "outputs/07.007/labor-coverage-registry.yaml"

COVERED_STATUSES = {"covered", "partially_covered"}


def load_yaml(path: Path):
    if not path.exists():
        sys.exit(f"File not found: {path}")
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def skill_name(skill_path: str) -> str:
    """Из полного пути 'profiles/regulator/skills/info-gatherer/SKILL.md' -> 'info-gatherer'."""
    return Path(skill_path).parent.name


def validate() -> int:
    mapping = load_yaml(MAPPING_PATH)
    registry = load_yaml(REGISTRY_PATH)

    errors = []
    checked = 0
    documented_gaps = registry.get("documented_gaps", {})

    for entry in mapping.get("mappings", []):
        tf_code = entry.get("tf_code")
        status = entry.get("coverage_status")
        if status not in COVERED_STATUSES:
            continue

        checked += 1
        key = f"LF-07.007-{tf_code}"

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
            errors.append(
                f"{key}: статус '{status}' в mapping, но запись в registry отсутствует"
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
    print(f"Записей в registry: {sum(1 for k in registry if k.startswith('LF-07.007-'))}")
    if documented_gaps:
        print(f"Documented gaps: {len(documented_gaps)} ({', '.join(sorted(documented_gaps))})")
    if errors:
        print(f"Найдено рассинхронизаций: {len(errors)}")
        for err in errors:
            print(f"  ✗ {err}")
        print("Registry valid: False")
        return 1

    print("Registry valid: True")
    return 0


if __name__ == "__main__":
    sys.exit(validate())
