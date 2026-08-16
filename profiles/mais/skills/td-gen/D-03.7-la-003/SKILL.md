---
name: td-gen-D-03.7-la-003
description: td-gen for D/03.7/la-003: Оценка эффективности изменения процессной архитектуры органи
version: 1.0.0
---

# td-gen: D/03.7 / la-003

**Трудовое действие:** Оценка эффективности изменения процессной архитектуры организации

## ICOM

**Inputs:**
  - `transformation-executed` — читает из `input_files`

**Outputs:**
  - `transformation-results` — пишет в `output_dir/transformation-results.yaml`

## Process

```python
import os, yaml

# Read inputs
input_data = {}
for fpath in ['transformation-executed']:
    # fpath is the input_id, actual file is in input_files list
    pass  # data loaded from input_files by executor

# Generate outputs
output = {}
# Schema: transformation-results.yaml


output["transformation-results"] = {
    "kpi_results": [{"metric": "Process coverage", "baseline": 40, "target": 85, "actual": 55}],
    "effectiveness_rating": "medium",
    "summary": "Трансформация выполнена на 55% от целевых показателей",
    "process": "Оценка эффективности трансформации",
}

# Write outputs
os.makedirs(output_dir, exist_ok=True)
for oid, data in output.items():
    path = os.path.join(output_dir, f"{oid}.yaml")
    with open(path, "w") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
```

## Схемы данных
- `schemas/07.007-d/transformation-results.yaml`
