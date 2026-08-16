---
name: process-survey
description: D/01.7-TD-3: Collect information about current process architecture
version: 2.0.0
environments: [kanban]
metadata:
  hermes:
    tags: [profstandart, 07.007, architecture, survey]
    related_skills: [gap-analysis]
---

# Process Survey — D/01.7-TD-3

Выполняет четвёртое трудовое действие ОТФ-D: **«Сбор информации о процессной архитектуре организации»**.

## File-based handoff

- Читает: `architecture-current` (с диска)
- Пишет: `architecture-data.yaml`

Схема: `ARCHITECTURE/schemas/07.007-d/architecture-data.yaml`

```python
output = {"processes": [...]}
out_path = os.path.join(body["output_dir"], "architecture-data.yaml")

kanban_complete(
    summary="Собрана информация о N процессах",
    metadata={"output_files": [out_path]},
)
```
