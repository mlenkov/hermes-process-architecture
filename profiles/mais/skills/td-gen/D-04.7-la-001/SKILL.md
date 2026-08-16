---
name: td-gen-D-04.7-la-001
description: "td-gen for D/04.7/la-001: Разработка или доработка методик и регламентов, регулирующих"
version: 1.0.0
---

# td-gen: D/04.7 / la-001

**Трудовое действие:** Разработка или доработка методик и регламентов, регулирующих трансформацию процессной архитектуры организации

## ICOM

**Inputs:**
  - `transformation-results` — читает из `input_files`
  - `architecture-analysis` — читает из `input_files`

**Outputs:**
  - `methodology-developed` — пишет в `output_dir/methodology-developed.yaml`

## Process

```python
import os, yaml

# Read inputs
input_data = {}
for fpath in ['transformation-results', 'architecture-analysis']:
    # fpath is the input_id, actual file is in input_files list
    pass  # data loaded from input_files by executor

# Generate outputs
output = {}
# Schema: methodology-developed.yaml


output["methodology-developed"] = {
    "methodologies": [
        {"name": "Регламент управления архитектурой", "type": "регламент", "version": "1.0", "status": "approved"},
        {"name": "Методика описания процессов", "type": "методика", "version": "1.0", "status": "draft"},
    ],
    "process": "Разработка методик и регламентов",
}

# Write outputs
os.makedirs(output_dir, exist_ok=True)
for oid, data in output.items():
    path = os.path.join(output_dir, f"{oid}.yaml")
    with open(path, "w") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
```

## Схемы данных
- `schemas/07.007-d/methodology-developed.yaml`
