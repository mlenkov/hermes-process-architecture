---
name: td-gen-D-01.7-la-002
description: "td-gen for D/01.7/la-002: Согласование с заинтересованными сторонами целей проектирова"
version: 1.0.0
---

# td-gen: D/01.7 / la-002

**Трудовое действие:** Согласование с заинтересованными сторонами целей проектирования процессной архитектуры организации

## ICOM

**Inputs:**
  - `stakeholder-list` — читает из `input_files`
  - `business-strategy` — читает из `input_files`

**Outputs:**
  - `agreed-goals` — пишет в `output_dir/agreed-goals.yaml`

## Process

```python
import os, yaml

# Read inputs
input_data = {}
for fpath in ['stakeholder-list', 'business-strategy']:
    # fpath is the input_id, actual file is in input_files list
    pass  # data loaded from input_files by executor

# Generate outputs
output = {}
# Schema: agreed-goals.yaml


output["agreed-goals"] = {
    "goals": [
        {"id": "g-001", "description": "Построить целостную процессную архитектуру", "consensus": True, "owner": "CEO"},
        {"id": "g-002", "description": "Обеспечить прослеживаемость стратегии до процессов", "consensus": True, "owner": "COO"},
        {"id": "g-003", "description": "Устранить дублирование функций", "consensus": True, "owner": "CFO"},
    ],
    "process": "Согласование целей с заинтересованными сторонами",
}

# Write outputs
os.makedirs(output_dir, exist_ok=True)
for oid, data in output.items():
    path = os.path.join(output_dir, f"{oid}.yaml")
    with open(path, "w") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
```

## Схемы данных
- `schemas/07.007-d/agreed-goals.yaml`
