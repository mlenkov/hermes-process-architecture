#!/usr/bin/env python3
"""Гибрид registry → Memory System (ADR-016).

Читает labor-coverage-registry.yaml каждого стандарта (источник истины) и
пишет сжатую сводку «горячих фактов» в Memory System (горячий кэш) через
файл фактов, который Hermes инжектит в контекст. Сам registry НЕ меняется.

Гибрид: YAML = версионируемый источник истины; Memory = быстрый доступ к
состоянию покрытия без чтения файлов.

Usage:
    python3 scripts/memory-reporter.py            # все стандарты
    python3 scripts/memory-reporter.py --std 06.043
    python3 scripts/memory-reporter.py --std 07.007 --std 06.013 --dry-run

Вывод: сводка по стандартам + запись фактов за один вызов.
"""

import argparse
import datetime
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
MEM_FACTS = ROOT / ".hermes-facts"  # каталог фактов (gitignored или переживает удаление)


def load_registry(standard: str) -> dict:
    lp = ROOT / "outputs" / standard / "labor-coverage-registry.yaml"
    if not lp.exists():
        return {}
    with open(lp, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_mapping(standard: str) -> dict:
    if standard == "07.007":
        mp = ROOT / "outputs/07.007/block-D/labor-function-to-skill-mapping.yaml"
    else:
        mp = ROOT / "outputs" / standard / "labor-function-to-skill-mapping.yaml"
    if not mp.exists():
        return {}
    with open(mp, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def summarize(standard: str) -> dict:
    reg = load_registry(standard)
    mapping = load_mapping(standard)
    total = len(mapping.get("mappings", []))
    covered = sum(1 for m in mapping.get("mappings", [])
                  if m.get("coverage_status") == "covered")
    partial = sum(1 for m in mapping.get("mappings", [])
                  if m.get("coverage_status") == "partially_covered")
    missing = sum(1 for m in mapping.get("mappings", [])
                  if m.get("coverage_status") == "missing_skill")
    records = len([k for k in reg if str(k).startswith(f"LF-{standard}-")])
    return {
        "standard": standard,
        "total": total, "covered": covered,
        "partially_covered": partial, "missing": missing,
        "registry_records": records,
        "as_of": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--std", action="append", choices=["07.007", "06.043", "06.013"], help="стандарты (по умолчанию все)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    standards = args.std or ["07.007", "06.043", "06.013"]

    facts = []
    print("=== Memory-reporter: registry → Memory (ADR-016) ===")
    for s in standards:
        summ = summarize(s)
        fact = (f"Coverage {s}: {summ['covered']} covered / {summ['partially_covered']} "
                f"partial / {summ['missing']} missing из {summ['total']} ТФ; "
                f"registry_records={summ['registry_records']} (as_of {summ['as_of']})")
        print(f"  {fact}")
        facts.append({"standard": s, "fact": fact, "as_of": summ["as_of"]})

    if args.dry_run:
        print("  [DRY-RUN] факты не записаны")
        return 0

    # гибрид: пишем в файл фактов (Memory-каталог), Hermes инжектит в контекст
    MEM_FACTS.mkdir(parents=True, exist_ok=True)
    out = MEM_FACTS / "coverage-latest.txt"
    with open(out, "w", encoding="utf-8") as fh:
        for f in facts:
            fh.write(f"{f['fact']}\n")
    print(f"\nЗаписано {len(facts)} фактов → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
