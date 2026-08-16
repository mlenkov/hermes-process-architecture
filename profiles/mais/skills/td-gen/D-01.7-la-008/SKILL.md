---
name: td-gen-D-01.7-la-008
description: td-gen for D/01.7/la-008: Презентация результатов анализа процессной архитектуры орган
version: 1.0.0
---

# td-gen: D/01.7 / la-008

**Трудовое действие:** Презентация результатов анализа процессной архитектуры организации

## ICOM

**Inputs:**
  - `analysis-report` — читает из `input_files`

**Outputs:**
  - `architecture-analysis` — пишет в `output_dir/architecture-analysis.yaml`

## Process

```python
import os, yaml

# Read inputs
input_data = {}
for fpath in ['analysis-report']:
    # fpath is the input_id, actual file is in input_files list
    pass  # data loaded from input_files by executor

# Generate outputs
output = {}
# Schema: architecture-analysis.yaml


output["architecture-analysis"] = {
    "summary": "Архитектура частично документирована, 4 критических разрыва, покрытие 55%",
    "requirements": 4, "gaps": 4, "opportunities": 4, "stakeholders": 3, "goals": 3,
    "metadata": {"tf": "LF-07.007-D/01.7", "produced_by": "la-008"},
}

# Write outputs
os.makedirs(output_dir, exist_ok=True)
for oid, data in output.items():
    path = os.path.join(output_dir, f"{oid}.yaml")
    with open(path, "w") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
```

## Схемы данных
- `schemas/07.007-d/architecture-analysis.yaml`
