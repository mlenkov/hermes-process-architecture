---
name: process-optimization-analysis
description: D/01.7-TD-5: Identify improvement opportunities in process architecture
version: 2.0.0
environments: [kanban]
metadata:
  hermes:
    tags: [profstandart, 07.007, architecture, optimization]
    related_skills: [gap-analysis]
---

# Process Optimization Analysis — D/01.7-TD-5

Выполняет шестое трудовое действие ОТФ-D: **«Выявление возможностей усовершенствования процессной архитектуры организации»**.

## File-based handoff

- Читает: `gap-analysis` (с диска)
- Пишет: `improvement-opportunities.yaml`

Схема: `ARCHITECTURE/schemas/07.007-d/improvement-opportunities.yaml`

```python
output = {"opportunities": [...]}
out_path = os.path.join(body["output_dir"], "improvement-opportunities.yaml")

kanban_complete(
    summary="Определено N возможностей усовершенствования",
    metadata={"output_files": [out_path]},
)
```
