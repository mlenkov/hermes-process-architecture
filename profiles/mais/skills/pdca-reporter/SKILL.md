---
name: pdca-reporter
description: Еженедельный PDCA-цикл — план vs факт coverage, рекомендации, отчёт
version: 1.0.0
environments: [kanban]
---

# PDCA — Plan-Do-Check-Act цикл

Еженедельно: читает registry, сравнивает с целями, пишет отчёт.

## Цели покрытия
- Q3 2026: 35% (43/124 ТФ)
- Q4 2026: 50% (62/124 ТФ)

## Процедура

```python
import yaml, os, json
from datetime import datetime

REGISTRY = "/Volumes/Storage/work/mais/_TOOLS/VM-SRV001-SETUP/ARCHITECTURE/outputs/07.007/labor-coverage-registry.yaml"
REPORTS = "/Volumes/Storage/work/mais/_TOOLS/VM-SRV001-SETUP/ARCHITECTURE/outputs/07.007/pdca-reports"

# 1. Прочитать registry
if not os.path.exists(REGISTRY):
    print("No registry found.")
    exit()

with open(REGISTRY) as f:
    registry = yaml.safe_load(f) or {}

# 2. Посчитать статистику
total_tf = 124  # всего ТФ по 6 активным стандартам
covered = sum(1 for v in registry.values() if v.get("status") == "covered")
pct = round(covered / total_tf * 100, 1)

# 3. Сравнить с целями
q3_target = 43  # 35%
q4_target = 62  # 50%
status = "on_track" if pct >= 35 else "behind"
gap_q3 = max(0, q3_target - covered)
gap_q4 = max(0, q4_target - covered)

# 4. Сформировать отчёт
report = {
    "date": datetime.now().strftime("%Y-%m-%d"),
    "summary": {
        "covered": covered,
        "total": total_tf,
        "percentage": pct,
        "status": status,
    },
    "targets": {
        "q3_2026": {"target": q3_target, "gap": gap_q3},
        "q4_2026": {"target": q4_target, "gap": gap_q4},
    },
    "recommendations": [],
}

if gap_q3 > 0:
    uncovered = [k for k, v in registry.items() if v.get("status") != "covered"]
    report["recommendations"].append({
        "action": f"Execute {min(gap_q3, 5)} uncovered TFs from priority list",
        "priority": "high",
    })
    report["uncovered_sample"] = uncovered[:10]

# 5. Записать отчёт
os.makedirs(REPORTS, exist_ok=True)
path = f"{REPORTS}/pdca-{report['date']}.yaml"
with open(path, "w") as f:
    yaml.dump(report, f, allow_unicode=True, default_flow_style=False)

print(f"PDCA report: {path}")
print(f"Coverage: {pct}% ({covered}/{total_tf}) — {status}")
```
