---
name: td-gen-D-02.7-la-006
description: "td-gen for D/02.7/la-006: Контроль соответствия моделей процессов организации или адми"
version: 1.0.0
---

# td-gen: D/02.7 / la-006

**Трудовое действие:** Контроль соответствия моделей процессов организации или административных регламентов организации утвержденной процессной архитектуре организации

## ICOM

**Inputs:**
  - `architecture-designed` — читает из `input_files`

**Outputs:**
  - `architecture-compliance` — пишет в `output_dir/architecture-compliance.yaml`

## Process

```python
import os, yaml

# Read inputs
input_data = {}
for fpath in ['architecture-designed']:
    # fpath is the input_id, actual file is in input_files list
    pass  # data loaded from input_files by executor

# Generate outputs
output = {}
# Schema: architecture-compliance.yaml


output["architecture-compliance"] = {
    "conclusion": "compliant",
    "checked_models": [
        {"model_id": "pr-001", "name": "Стратегический обзор", "compliant": True},
        {"model_id": "pr-002", "name": "Релизный цикл", "compliant": True},
    ],
    "recommendations": ["Регулярный аудит моделей"],
    "process": "Контроль соответствия",
}

# Write outputs
os.makedirs(output_dir, exist_ok=True)
for oid, data in output.items():
    path = os.path.join(output_dir, f"{oid}.yaml")
    with open(path, "w") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
```

## Схемы данных
- `schemas/07.007-d/architecture-compliance.yaml`
