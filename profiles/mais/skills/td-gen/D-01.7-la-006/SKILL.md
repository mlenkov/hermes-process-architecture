---
name: td-gen-D-01.7-la-006
description: "td-gen for D/01.7/la-006: Выявление возможностей усовершенствования процессной архитек"
version: 1.0.0
---

# td-gen: D/01.7 / la-006

**Трудовое действие:** Выявление возможностей усовершенствования процессной архитектуры организации

## ICOM

**Inputs:**
  - `gap-analysis` — читает из `input_files`

**Outputs:**
  - `improvement-opportunities` — пишет в `output_dir/improvement-opportunities.yaml`

## Process

```python
import os, yaml

# Read inputs
input_data = {}
for fpath in ['gap-analysis']:
    # fpath is the input_id, actual file is in input_files list
    pass  # data loaded from input_files by executor

# Generate outputs
output = {}
# Schema: improvement-opportunities.yaml


output["improvement-opportunities"] = {
    "opportunities": [
        {"id": "opp-001", "description": "Внедрение BPMN-нотации для всех процессов", "impact": "high", "effort": "medium"},
        {"id": "opp-002", "description": "Автоматизация стыков КИС (Jira ↔ 1C)", "impact": "high", "effort": "high"},
        {"id": "opp-003", "description": "Назначение владельцев процессов", "impact": "medium", "effort": "low"},
        {"id": "opp-004", "description": "Построение процессной карты уровня 0-2", "impact": "high", "effort": "medium"},
    ],
    "process": "Выявление возможностей усовершенствования",
}

# Write outputs
os.makedirs(output_dir, exist_ok=True)
for oid, data in output.items():
    path = os.path.join(output_dir, f"{oid}.yaml")
    with open(path, "w") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
```

## Схемы данных
- `schemas/07.007-d/improvement-opportunities.yaml`
