---
name: td-gen-D-02.7-la-002
description: td-gen for D/02.7/la-002: Выбор референтной модели и методологии проектирования процес
version: 1.0.0
---

# td-gen: D/02.7 / la-002

**Трудовое действие:** Выбор референтной модели и методологии проектирования процессной архитектуры организации

## ICOM

**Inputs:**
  - `systematized-info` — читает из `input_files`

**Outputs:**
  - `selected-reference-model` — пишет в `output_dir/selected-reference-model.yaml`

## Process

```python
import os, yaml

# Read inputs
input_data = {}
for fpath in ['systematized-info']:
    # fpath is the input_id, actual file is in input_files list
    pass  # data loaded from input_files by executor

# Generate outputs
output = {}
# Schema: selected-reference-model.yaml


output["selected-reference-model"] = {
    "selected_model": "APQC PCF v7.3 (Process Classification Framework)",
    "methodology": "BPMN 2.0 + DMN",
    "alternatives_considered": [{"name": "SCOR", "reason": "Сфокусирован на supply chain"}, {"name": "eTOM", "reason": "Телеком-специфичный"}],
    "process": "Выбор референтной модели",
}

# Write outputs
os.makedirs(output_dir, exist_ok=True)
for oid, data in output.items():
    path = os.path.join(output_dir, f"{oid}.yaml")
    with open(path, "w") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
```

## Схемы данных
- `schemas/07.007-d/selected-reference-model.yaml`
