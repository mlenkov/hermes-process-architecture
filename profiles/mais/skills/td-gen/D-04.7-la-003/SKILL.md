---
name: td-gen-D-04.7-la-003
description: td-gen for D/04.7/la-003: Методическая помощь проектным командам, осуществляющим транс
version: 1.0.0
---

# td-gen: D/04.7 / la-003

**Трудовое действие:** Методическая помощь проектным командам, осуществляющим трансформацию процессной архитектуры организации

## ICOM

**Inputs:**
  - `methodology-deployed` — читает из `input_files`

**Outputs:**
  - `teams-supported` — пишет в `output_dir/teams-supported.yaml`

## Process

```python
import os, yaml

# Read inputs
input_data = {}
for fpath in ['methodology-deployed']:
    # fpath is the input_id, actual file is in input_files list
    pass  # data loaded from input_files by executor

# Generate outputs
output = {}
# Schema: teams-supported.yaml


output["teams-supported"] = {
    "support_log": [{"team": "Продуктовый отдел", "request": "Описание процесса релиза", "satisfaction": "high"}],
    "faq": [{"question": "Какую нотацию использовать?", "answer": "BPMN 2.0"}],
    "process": "Методическая помощь командам",
}

# Write outputs
os.makedirs(output_dir, exist_ok=True)
for oid, data in output.items():
    path = os.path.join(output_dir, f"{oid}.yaml")
    with open(path, "w") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
```

## Схемы данных
- `schemas/07.007-d/teams-supported.yaml`
