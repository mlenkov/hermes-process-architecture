---
name: requirements-analysis
description: D/01.7-TD-2: Define requirements for process architecture based on business goals and strategy
version: 2.0.0
environments: [kanban]
metadata:
  hermes:
    tags: [profstandart, 07.007, architecture, requirements]
    related_skills: [meeting-facilitation]
---

# Requirements Analysis — D/01.7-TD-2

Выполняет третье трудовое действие ОТФ-D: **«Определение требований к процессной архитектуре организации исходя из структуры бизнеса, целей и стратегии организации»**.

## File-based handoff

- Читает: `agreed-goals`, `business-strategy` (с диска)
- Пишет: `architecture-requirements.yaml`

Схема: `ARCHITECTURE/schemas/07.007-d/architecture-requirements.yaml`

```python
output = {"requirements": [...]}
out_path = os.path.join(body["output_dir"], "architecture-requirements.yaml")

kanban_complete(
    summary="Определено N требований",
    metadata={"output_files": [out_path]},
)
```
