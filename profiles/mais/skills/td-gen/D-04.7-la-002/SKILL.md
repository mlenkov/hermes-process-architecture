---
name: td-gen-D-04.7-la-002
description: td-gen for D/04.7/la-002: Внедрение в организации методологии трансформации процессной
version: 1.0.0
---

# td-gen: D/04.7 / la-002

**Трудовое действие:** Внедрение в организации методологии трансформации процессной архитектуры организации

## ICOM

**Inputs:**
  - `methodology-developed` — читает из `input_files`

**Outputs:**
  - `methodology-deployed` — пишет в `output_dir/methodology-deployed.yaml`

## Process

```python
import os, yaml

# Read inputs
input_data = {}
for fpath in ['methodology-developed']:
    # fpath is the input_id, actual file is in input_files list
    pass  # data loaded from input_files by executor

# Generate outputs
output = {}
# Schema: methodology-deployed.yaml


output["methodology-deployed"] = {
    "deployment_plan": {
        "phases": [
            {"phase": "Пилот (ИТ-департамент)", "status": "planned"},
            {"phase": "Масштабирование", "status": "planned"},
        ],
    },
    "adoption_rate": 0.3,
    "process": "Внедрение методологии",
}

# Write outputs
os.makedirs(output_dir, exist_ok=True)
for oid, data in output.items():
    path = os.path.join(output_dir, f"{oid}.yaml")
    with open(path, "w") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
```

## Схемы данных
- `schemas/07.007-d/methodology-deployed.yaml`
