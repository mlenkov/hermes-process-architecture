---
name: gap-analysis
description: D/01.7-TD-4: Analyze compliance of current architecture against defined requirements
version: 2.0.0
environments: [kanban]
metadata:
  hermes:
    tags: [profstandart, 07.007, architecture, analysis]
    related_skills: [requirements-analysis, process-survey]
---

# Gap Analysis — D/01.7-TD-4

Выполняет пятое трудовое действие ОТФ-D: **«Анализ соответствия существующей процессной архитектуры организации требованиям»**.

## File-based handoff

- Читает: `architecture-requirements`, `architecture-data` (с диска)
- Пишет: `gap-analysis.yaml`

Схема: `ARCHITECTURE/schemas/07.007-d/gap-analysis.yaml`

```python
output = {"gaps": [...]}
out_path = os.path.join(body["output_dir"], "gap-analysis.yaml")

kanban_complete(
    summary="Выявлено N разрывов: M критических",
    metadata={"output_files": [out_path]},
)
```
