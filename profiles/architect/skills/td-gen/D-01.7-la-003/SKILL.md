---
name: td-gen-D-01.7-la-003
description: td-gen for D/01.7/la-003: Определение требований к процессной архитектуре организации 
version: 1.0.0
---

# td-gen: D/01.7 / la-003

**Трудовое действие:** Определение требований к процессной архитектуре организации исходя из структуры бизнеса, целей и стратегии организации

## ICOM

**Inputs:**
  - `agreed-goals` — читает из `input_files`
  - `business-strategy` — читает из `input_files`

**Outputs:**
  - `architecture-requirements` — пишет в `output_dir/architecture-requirements.yaml`

## Process

```python
import os, yaml

# Read inputs
input_data = {}
for fpath in ['agreed-goals', 'business-strategy']:
    # fpath is the input_id, actual file is in input_files list
    pass  # data loaded from input_files by executor

# Generate outputs
output = {}
# Schema: architecture-requirements.yaml


output["architecture-requirements"] = {
    "requirements": [
        {"id": "r-001", "domain": "Стратегический", "description": "Прослеживаемость целей до процессов", "priority": "critical"},
        {"id": "r-002", "domain": "Функциональный", "description": "Полная карта бизнес-функций", "priority": "high"},
        {"id": "r-003", "domain": "Интеграционный", "description": "Связь процессов с КИС", "priority": "high"},
        {"id": "r-004", "domain": "Нормативный", "description": "Соответствие ISO 9001:2025", "priority": "medium"},
    ],
    "process": "Определение требований к архитектуре",
}

# Write outputs
os.makedirs(output_dir, exist_ok=True)
for oid, data in output.items():
    path = os.path.join(output_dir, f"{oid}.yaml")
    with open(path, "w") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
```

## Схемы данных
- `schemas/07.007-d/architecture-requirements.yaml`
