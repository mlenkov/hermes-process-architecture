---
name: td-gen-D-02.7-la-001
description: td-gen for D/02.7/la-001: Систематизация информации о процессной архитектуре организац
version: 1.0.0
---

# td-gen: D/02.7 / la-001

**Трудовое действие:** Систематизация информации о процессной архитектуре организации

## ICOM

**Inputs:**
  - `architecture-analysis` — читает из `input_files`

**Outputs:**
  - `systematized-info` — пишет в `output_dir/systematized-info.yaml`

## Process

```python
import os, yaml

# Read inputs
input_data = {}
for fpath in ['architecture-analysis']:
    # fpath is the input_id, actual file is in input_files list
    pass  # data loaded from input_files by executor

# Generate outputs
output = {}
# Schema: systematized-info.yaml


output["systematized-info"] = {
    "domains": [
        {"id": "dom-strat", "name": "Стратегический", "processes": ["Стратегическое управление"], "gaps": ["Стратегия→Процессы"]},
        {"id": "dom-core", "name": "Основной", "processes": ["Управление продуктами", "Разработка"], "gaps": []},
        {"id": "dom-support", "name": "Поддерживающий", "processes": ["Финансовый учёт", "HR"], "gaps": ["Не документированы"]},
        {"id": "dom-integ", "name": "Интеграционный", "processes": [], "gaps": ["Разрыв КИС"]},
    ],
    "process": "Систематизация информации об архитектуре",
}

# Write outputs
os.makedirs(output_dir, exist_ok=True)
for oid, data in output.items():
    path = os.path.join(output_dir, f"{oid}.yaml")
    with open(path, "w") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
```

## Схемы данных
- `schemas/07.007-d/systematized-info.yaml`
