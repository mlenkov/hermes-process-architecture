---
name: td-gen-D-02.7-la-005
description: td-gen for D/02.7/la-005: Согласование процессной архитектуры организации с заинтересо
version: 1.0.0
---

# td-gen: D/02.7 / la-005

**Трудовое действие:** Согласование процессной архитектуры организации с заинтересованными сторонами

## ICOM

**Inputs:**
  - `architecture-designed` — читает из `input_files`

**Outputs:**
  - `agreed-architecture` — пишет в `output_dir/agreed-architecture.yaml`

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
# Schema: agreed-architecture.yaml


output["agreed-architecture"] = {
    "architecture_version": "1.0",
    "stakeholders_consulted": [
        {"id": "st-001", "role": "owner", "agreement": "full"},
        {"id": "st-002", "role": "implementer", "agreement": "full"},
    ],
    "status": "approved",
    "process": "Согласование архитектуры",
}

# Write outputs
os.makedirs(output_dir, exist_ok=True)
for oid, data in output.items():
    path = os.path.join(output_dir, f"{oid}.yaml")
    with open(path, "w") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
```

## Схемы данных
- `schemas/07.007-d/agreed-architecture.yaml`
