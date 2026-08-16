---
name: meeting-facilitation
description: D/01.7-TD-1: Align stakeholders on goals for process architecture design
version: 2.0.0
environments: [kanban]
metadata:
  hermes:
    tags: [profstandart, 07.007, architecture, communication]
    related_skills: [stakeholder-mapping]
---

# Meeting Facilitation — D/01.7-TD-1

Выполняет второе трудовое действие ОТФ-D: **«Согласование с заинтересованными сторонами целей проектирования процессной архитектуры организации»**.

## File-based handoff

Читает `stakeholder-list` из предыдущего ТД, пишет `agreed-goals`.

## Входные данные

```python
for path in body["input_files"]:
    with open(path) as f:
        data = yaml.safe_load(f)
```

- `stakeholder-list` — список стейкхолдеров (output TD-0, путь в `input_files[0]`)
- `business-strategy` — стратегия (TF-level input, путь в `input_files[1]`)

## Выходные данные

```python
output = {"goals": [...]}
out_path = os.path.join(body["output_dir"], "agreed-goals.yaml")

kanban_complete(
    summary="Согласовано N целей проектирования",
    metadata={"output_files": [out_path]},
)
```

Схема: `ARCHITECTURE/schemas/07.007-d/agreed-goals.yaml`
