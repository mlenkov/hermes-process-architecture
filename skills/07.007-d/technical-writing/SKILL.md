---
name: technical-writing
description: D/01.7-TD-6: Document and format analysis results into a structured report
version: 2.0.0
environments: [kanban]
metadata:
  hermes:
    tags: [profstandart, 07.007, architecture, documentation]
    related_skills: [gap-analysis, process-optimization-analysis]
---

# Technical Writing — D/01.7-TD-6

Выполняет седьмое трудовое действие ОТФ-D: **«Оформление результатов анализа процессной архитектуры организации»**.

## File-based handoff

- Читает: `gap-analysis`, `improvement-opportunities` (с диска)
- Пишет: `analysis-report.yaml`

## Процесс

1. Прочитать все входные артефакты с диска
2. Синтезировать итоговый отчёт
3. Записать `analysis-report.yaml`

Схема: `ARCHITECTURE/schemas/07.007-d/analysis-report.yaml`

```python
output = {
    "summary": "...",
    "stakeholder_analysis": {...},
    "goals_alignment": {...},
    "requirements_count": N,
    "processes_surveyed": N,
    "gaps_found": {...},
    "opportunities": N,
    "recommendations": [...],
    "key_findings": [...],
}
out_path = os.path.join(body["output_dir"], "analysis-report.yaml")

kanban_complete(
    summary="Составлен итоговый отчёт анализа",
    metadata={"output_files": [out_path]},
)
```
