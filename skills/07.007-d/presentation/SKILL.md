---
name: presentation
description: D/01.7-TD-7: Present analysis results and produce final TF output
version: 2.0.0
environments: [kanban]
metadata:
  hermes:
    tags: [profstandart, 07.007, architecture, presentation]
    related_skills: [technical-writing]
---

# Presentation — D/01.7-TD-7

Выполняет восьмое трудовое действие ОТФ-D: **«Презентация результатов анализа процессной архитектуры организации»**.

## File-based handoff

- Читает: `analysis-report` (с диска, из `input_files[0]`)
- Пишет: `architecture-analysis.yaml` — итоговый выход ТФ

## Процесс

1. Прочитать `analysis-report` и все артефакты из `output_base`
2. Собрать финальный `architecture-analysis` — агрегат всех артефактов
3. Записать на диск

Схема: `ARCHITECTURE/schemas/07.007-d/architecture-analysis.yaml`

```python
import yaml, os, glob

# Read all artifacts from this TF's output directory
all_data = {}
for la_dir in sorted(glob.glob(os.path.join(body["output_base"], "la-*"))):
    for yf in glob.glob(os.path.join(la_dir, "*.yaml")):
        with open(yf) as f:
            key = os.path.splitext(os.path.basename(yf))[0]
            all_data[key] = yaml.safe_load(f)

output = {
    "requirements": all_data.get("architecture-requirements"),
    "gaps": all_data.get("gap-analysis"),
    "opportunities": all_data.get("improvement-opportunities"),
    "stakeholders": all_data.get("stakeholder-list"),
    "goals": all_data.get("agreed-goals"),
    "report": all_data.get("analysis-report"),
    "metadata": {
        "tf": body.get("parent_tf"),
        "output_base": body.get("output_base"),
    },
}
out_path = os.path.join(body["output_dir"], "architecture-analysis.yaml")
with open(out_path, "w") as f:
    yaml.dump(output, f, allow_unicode=True, default_flow_style=False)

kanban_complete(
    summary="Сформирован финальный architecture-analysis",
    metadata={"output_files": [out_path]},
)
```
