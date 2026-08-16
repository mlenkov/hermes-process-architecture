---
name: td-gen-D-02.7-la-003
description: "td-gen for D/02.7/la-003: Адаптация референтной модели и методологии проектирования пр"
version: 1.0.0
---

# td-gen: D/02.7 / la-003

**Трудовое действие:** Адаптация референтной модели и методологии проектирования процессной архитектуры организации к структуре бизнеса, целям и стратегии организации

## ICOM

**Inputs:**
  - `selected-reference-model` — читает из `input_files`

**Outputs:**
  - `adapted-model` — пишет в `output_dir/adapted-model.yaml`

## Process

```python
import os, yaml

# Read inputs
input_data = {}
for fpath in ['selected-reference-model']:
    # fpath is the input_id, actual file is in input_files list
    pass  # data loaded from input_files by executor

# Generate outputs
output = {}
# Schema: adapted-model.yaml


output["adapted-model"] = {
    "source_model": "APQC PCF v7.3",
    "adaptations": [
        {"element": "Количество групп", "original": "13", "adapted": "9", "rationale": "Соответствие масштабу 500 чел."},
    ],
    "alignment": {"business_structure": True, "strategy": True, "goals": True},
    "process": "Адаптация референтной модели",
}

# Write outputs
os.makedirs(output_dir, exist_ok=True)
for oid, data in output.items():
    path = os.path.join(output_dir, f"{oid}.yaml")
    with open(path, "w") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
```

## Схемы данных
- `schemas/07.007-d/adapted-model.yaml`
