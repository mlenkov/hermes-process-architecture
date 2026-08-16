---
name: stakeholder-mapping
description: D/01.7-TD-0: Identify and document stakeholders for process architecture design/transformation
version: 2.0.0
environments: [kanban]
metadata:
  hermes:
    tags: [profstandart, 07.007, architecture, analysis]
    related_skills: [meeting-facilitation]
---

# Stakeholder Mapping — D/01.7-TD-0

Выполняет первое трудовое действие ОТФ-D: **«Определение заинтересованных сторон в проектировании и трансформации процессной архитектуры организации»**.

## File-based handoff

Читает входные YAML-файлы с диска, пишет выходной YAML на диск.
В SQLite идут только пути к файлам.

## Входные данные

Прочитать YAML-файлы из `input_files` (в body задачи):

```python
import yaml
for path in body["input_files"]:
    with open(path) as f:
        data = yaml.safe_load(f)
```

- `architecture-current` — описание текущей архитектуры
- `business-strategy` — цели и стратегия организации

## Процесс

1. Проанализировать входные данные
2. Идентифицировать все заинтересованные стороны
3. Для каждой: роль, интерес, влияние, требования
4. Записать результат в `output_dir/{output_id}.yaml`

## Выходные данные

```python
import yaml, os
output = {
    "stakeholders": [
        {"id": "st-001", "name": "...", "role": "owner",
         "interest": "...", "influence": "high",
         "requirements": ["..."]},
    ]
}
out_path = os.path.join(body["output_dir"], "stakeholder-list.yaml")
with open(out_path, "w") as f:
    yaml.dump(output, f, allow_unicode=True, default_flow_style=False)

kanban_complete(
    summary="Идентифицировано N заинтересованных сторон",
    metadata={"output_files": [out_path]},
)
```

Схема данных: `ARCHITECTURE/schemas/07.007-d/stakeholder-list.yaml`
