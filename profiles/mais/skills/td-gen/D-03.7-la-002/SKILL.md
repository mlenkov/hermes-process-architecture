---
name: td-gen-D-03.7-la-002
description: "td-gen for D/03.7/la-002: Руководство программами изменения процессной архитектуры орг"
version: 1.0.0
---

# td-gen: D/03.7 / la-002

**Трудовое действие:** Руководство программами изменения процессной архитектуры организации

## ICOM

**Inputs:**
  - `transformation-plan` — читает из `input_files`

**Outputs:**
  - `transformation-executed` — пишет в `output_dir/transformation-executed.yaml`

## Process

```python
import os, yaml

# Read inputs
input_data = {}
for fpath in ['transformation-plan']:
    # fpath is the input_id, actual file is in input_files list
    pass  # data loaded from input_files by executor

# Generate outputs
output = {}
# Schema: transformation-executed.yaml


output["transformation-executed"] = {
    "program": {"name": "Архитектурная трансформация", "status": "in_progress"},
    "execution_log": [{"phase": "Анализ", "status": "completed"}, {"phase": "Проектирование", "status": "60%"}],
    "overall_status": "on_track",
    "process": "Руководство программой изменений",
}

# Write outputs
os.makedirs(output_dir, exist_ok=True)
for oid, data in output.items():
    path = os.path.join(output_dir, f"{oid}.yaml")
    with open(path, "w") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
```

## Схемы данных
- `schemas/07.007-d/transformation-executed.yaml`
