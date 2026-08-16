---
name: td-gen-D-04.7-la-004
description: "td-gen for D/04.7/la-004: Контроль соблюдения методик и регламентов, регулирующих тран"
version: 1.0.0
---

# td-gen: D/04.7 / la-004

**Трудовое действие:** Контроль соблюдения методик и регламентов, регулирующих трансформацию процессной архитектуры организации

## ICOM

**Inputs:**
  - `methodology-deployed` — читает из `input_files`

**Outputs:**
  - `compliance-report` — пишет в `output_dir/compliance-report.yaml`

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
# Schema: compliance-report.yaml


output["compliance-report"] = {
    "audited_units": [
        {"unit": "ИТ-департамент", "compliant": True},
        {"unit": "Продуктовый отдел", "compliant": False, "findings": ["Не используются шаблоны BPMN"]},
    ],
    "overall_compliance_rate": 75,
    "process": "Контроль соблюдения методик",
}

# Write outputs
os.makedirs(output_dir, exist_ok=True)
for oid, data in output.items():
    path = os.path.join(output_dir, f"{oid}.yaml")
    with open(path, "w") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
```

## Схемы данных
- `schemas/07.007-d/compliance-report.yaml`
