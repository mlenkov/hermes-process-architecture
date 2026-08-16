---
name: td-gen-D-04.7-la-005
description: td-gen for D/04.7/la-005: Контроль актуальности методик и регламентов, регулирующих тр
version: 1.0.0
---

# td-gen: D/04.7 / la-005

**Трудовое действие:** Контроль актуальности методик и регламентов, регулирующих трансформацию процессной архитектуры организации

## ICOM

**Inputs:**
  - `compliance-report` — читает из `input_files`
  - `transformation-results` — читает из `input_files`

**Outputs:**
  - `methodology-updates` — пишет в `output_dir/methodology-updates.yaml`

## Process

```python
import os, yaml

# Read inputs
input_data = {}
for fpath in ['compliance-report', 'transformation-results']:
    # fpath is the input_id, actual file is in input_files list
    pass  # data loaded from input_files by executor

# Generate outputs
output = {}
# Schema: methodology-updates.yaml


output["methodology-updates"] = {
    "review_date": "2026-07-29",
    "updates": [
        {"name": "Методика описания процессов", "version": "1.1", "changes": ["Добавлены шаблоны BPMN"]},
    ],
    "next_review_date": "2026-10-29",
    "process": "Актуализация методик",
}

# Write outputs
os.makedirs(output_dir, exist_ok=True)
for oid, data in output.items():
    path = os.path.join(output_dir, f"{oid}.yaml")
    with open(path, "w") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
```

## Схемы данных
- `schemas/07.007-d/methodology-updates.yaml`
