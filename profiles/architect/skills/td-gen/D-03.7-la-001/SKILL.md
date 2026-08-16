---
name: td-gen-D-03.7-la-001
description: td-gen for D/03.7/la-001: Планирование изменения процессной архитектуры организации в 
version: 1.0.0
---

# td-gen: D/03.7 / la-001

**Трудовое действие:** Планирование изменения процессной архитектуры организации в связи с реорганизацией бизнеса

## ICOM

**Inputs:**
  - `architecture-compliance` — читает из `input_files`
  - `business-reorg` — читает из `input_files`

**Outputs:**
  - `transformation-plan` — пишет в `output_dir/transformation-plan.yaml`

## Process

```python
import os, yaml

# Read inputs
input_data = {}
for fpath in ['architecture-compliance', 'business-reorg']:
    # fpath is the input_id, actual file is in input_files list
    pass  # data loaded from input_files by executor

# Generate outputs
output = {}
# Schema: transformation-plan.yaml


output["transformation-plan"] = {
    "plan": {
        "phases": [
            {"name": "Анализ", "duration": "1 мес", "deliverables": ["Impact assessment"]},
            {"name": "Проектирование", "duration": "2 мес", "deliverables": ["Целевая архитектура"]},
            {"name": "Внедрение", "duration": "3 мес", "deliverables": ["Внедрённая архитектура"]},
        ],
        "kpi": [{"metric": "Process coverage", "baseline": 40, "target": 85}],
    },
    "process": "Планирование изменений в связи с реорганизацией",
}

# Write outputs
os.makedirs(output_dir, exist_ok=True)
for oid, data in output.items():
    path = os.path.join(output_dir, f"{oid}.yaml")
    with open(path, "w") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
```

## Схемы данных
- `schemas/07.007-d/transformation-plan.yaml`
