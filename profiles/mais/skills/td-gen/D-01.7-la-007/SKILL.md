---
name: td-gen-D-01.7-la-007
description: td-gen for D/01.7/la-007: Оформление результатов анализа процессной архитектуры органи
version: 1.0.0
---

# td-gen: D/01.7 / la-007

**Трудовое действие:** Оформление результатов анализа процессной архитектуры организации

## ICOM

**Inputs:**
  - `gap-analysis` — читает из `input_files`
  - `improvement-opportunities` — читает из `input_files`

**Outputs:**
  - `analysis-report` — пишет в `output_dir/analysis-report.yaml`

## Process

```python
import os, yaml

# Read inputs
input_data = {}
for fpath in ['gap-analysis', 'improvement-opportunities']:
    # fpath is the input_id, actual file is in input_files list
    pass  # data loaded from input_files by executor

# Generate outputs
output = {}
# Schema: analysis-report.yaml


output["analysis-report"] = {
    "title": "Анализ процессной архитектуры ООО ТехноПроект",
    "sections": [
        {"title": "Методология", "content": "SWOT-анализ, GAP-анализ, бенчмаркинг APQC PCF"},
        {"title": "Ключевые выводы", "content": "Архитектура частично документирована, выявлено 4 критических разрыва"},
        {"title": "Рекомендации", "content": "Внедрение BPMN, назначение владельцев, автоматизация стыков КИС"},
    ],
    "process": "Оформление результатов анализа",
}

# Write outputs
os.makedirs(output_dir, exist_ok=True)
for oid, data in output.items():
    path = os.path.join(output_dir, f"{oid}.yaml")
    with open(path, "w") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
```

## Схемы данных
- `schemas/07.007-d/analysis-report.yaml`
