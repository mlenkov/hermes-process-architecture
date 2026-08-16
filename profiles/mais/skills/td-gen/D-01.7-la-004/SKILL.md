---
name: td-gen-D-01.7-la-004
description: td-gen for D/01.7/la-004: Сбор информации о процессной архитектуре организации
version: 1.0.0
---

# td-gen: D/01.7 / la-004

**Трудовое действие:** Сбор информации о процессной архитектуре организации

## ICOM

**Inputs:**
  - `architecture-current` — читает из `input_files`

**Outputs:**
  - `architecture-data` — пишет в `output_dir/architecture-data.yaml`

## Process

```python
import os, yaml

# Read inputs
input_data = {}
for fpath in ['architecture-current']:
    # fpath is the input_id, actual file is in input_files list
    pass  # data loaded from input_files by executor

# Generate outputs
output = {}
# Schema: architecture-data.yaml


output["architecture-data"] = {
    "processes": [
        {"id": "p-001", "name": "Стратегическое управление", "owner": "CEO", "kis": ["Confluence"], "status": "documented"},
        {"id": "p-002", "name": "Управление продуктами", "owner": "CPO", "kis": ["Jira"], "status": "partial"},
        {"id": "p-003", "name": "Финансовый учёт", "owner": "CFO", "kis": ["1C:ERP"], "status": "automated"},
        {"id": "p-004", "name": "Разработка и релизы", "owner": "CTO", "kis": ["GitLab", "Jira"], "status": "partial"},
    ],
    "process": "Сбор информации о процессной архитектуре",
}

# Write outputs
os.makedirs(output_dir, exist_ok=True)
for oid, data in output.items():
    path = os.path.join(output_dir, f"{oid}.yaml")
    with open(path, "w") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
```

## Схемы данных
- `schemas/07.007-d/architecture-data.yaml`
