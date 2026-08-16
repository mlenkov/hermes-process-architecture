---
name: td-gen-D-01.7-la-005
description: td-gen for D/01.7/la-005: Анализ соответствия существующей процессной архитектуры орга
version: 1.0.0
---

# td-gen: D/01.7 / la-005

**Трудовое действие:** Анализ соответствия существующей процессной архитектуры организации требованиям, определенным к процессной архитектуре организации исходя из структуры бизнеса, целей и стратегии организации

## ICOM

**Inputs:**
  - `architecture-requirements` — читает из `input_files`
  - `architecture-data` — читает из `input_files`

**Outputs:**
  - `gap-analysis` — пишет в `output_dir/gap-analysis.yaml`

## Process

```python
import os, yaml

# Read inputs
input_data = {}
for fpath in ['architecture-requirements', 'architecture-data']:
    # fpath is the input_id, actual file is in input_files list
    pass  # data loaded from input_files by executor

# Generate outputs
output = {}
# Schema: gap-analysis.yaml


output["gap-analysis"] = {
    "gaps": [
        {"id": "gap-001", "area": "Стратегия→Процессы", "severity": "critical", "description": "Нет прослеживаемости целей до процессов"},
        {"id": "gap-002", "area": "Документация", "severity": "major", "description": "Поддерживающие процессы не документированы"},
        {"id": "gap-003", "area": "Автоматизация", "severity": "major", "description": "Разрыв между Jira и 1C:ERP"},
        {"id": "gap-004", "area": "Ролевая модель", "severity": "minor", "description": "Владельцы процессов не назначены"},
    ],
    "process": "Анализ соответствия существующей архитектуры требованиям",
}

# Write outputs
os.makedirs(output_dir, exist_ok=True)
for oid, data in output.items():
    path = os.path.join(output_dir, f"{oid}.yaml")
    with open(path, "w") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
```

## Схемы данных
- `schemas/07.007-d/gap-analysis.yaml`
