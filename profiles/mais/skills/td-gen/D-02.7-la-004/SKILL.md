---
name: td-gen-D-02.7-la-004
description: "td-gen for D/02.7/la-004: Разработка процессной архитектуры организации, включающей ор"
version: 1.0.0
---

# td-gen: D/02.7 / la-004

**Трудовое действие:** Разработка процессной архитектуры организации, включающей оргструктуру, бизнес-функции, процессы или административные регламенты, корпоративные информационные системы

## ICOM

**Inputs:**
  - `adapted-model` — читает из `input_files`

**Outputs:**
  - `architecture-designed` — пишет в `output_dir/architecture-designed.yaml`

## Process

```python
import os, yaml

# Read inputs
input_data = {}
for fpath in ['adapted-model']:
    # fpath is the input_id, actual file is in input_files list
    pass  # data loaded from input_files by executor

# Generate outputs
output = {}
# Schema: architecture-designed.yaml


output["architecture-designed"] = {
    "version": "1.0",
    "org_structure": [
        {"unit": "Совет директоров", "parent": None, "functions": ["Стратегия"]},
        {"unit": "ИТ-департамент", "parent": "Совет директоров", "functions": ["Разработка", "QA"]},
    ],
    "business_functions": [
        {"id": "f-001", "name": "Стратегическое планирование", "owner": "CEO"},
        {"id": "f-002", "name": "Управление релизами", "owner": "PM"},
    ],
    "processes": [
        {"id": "pr-001", "name": "Стратегический обзор", "input": "Анализ рынка", "output": "Стратегия", "owner": "CEO"},
        {"id": "pr-002", "name": "Релизный цикл", "input": "Backlog", "output": "Продукт", "owner": "PM"},
    ],
    "information_systems": [
        {"id": "is-001", "name": "1C:ERP", "supports": ["Финансовый учёт"]},
        {"id": "is-002", "name": "Jira", "supports": ["Управление релизами"]},
    ],
    "process": "Разработка процессной архитектуры",
}

# Write outputs
os.makedirs(output_dir, exist_ok=True)
for oid, data in output.items():
    path = os.path.join(output_dir, f"{oid}.yaml")
    with open(path, "w") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
```

## Схемы данных
- `schemas/07.007-d/architecture-designed.yaml`
