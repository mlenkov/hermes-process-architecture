---
name: registry-updater
description: >
  Атомарное обновление labor-coverage-registry.yaml. Вызывается другими профилями
  после завершения TF-summary pipeline. Добавляет/обновляет запись ТФ
  со статусом, артефактами, skill_path и pdca_ref.
version: 0.1.0
status: stub
---

# registry-updater (stub)

**Назначение:** Централизованное обновление реестра покрытия, чтобы бизнес-профили (regulator, architect, analyst) не писали в registry напрямую.

**Статус:** stub — подготовлен к реализации на следующем этапе (ADR-003, Фаза 4).

## Планируемый интерфейс

```yaml
# Вызов (через Hermes handoff или прямой вызов навыка)
inputs:
  tf_code: "А/01.6"
  status: "covered"
  tds_completed: "10/10"
  skill_path: "profiles/regulator/skills/info-gatherer/SKILL.md"
  artifacts_generated:
    - "outputs/07.007/block-A/A-01.6-info-context.yaml"

output:
  - "outputs/07.007/labor-coverage-registry.yaml"  # обновлённый registry
```

## Правила (proposed)

- Только append/update существующих записей. Никогда не удаляет.
- Валидирует tf_code по labor-function-to-skill-mapping.yaml перед записью.
- Добавляет `pdca_ref` ссылку на последний PDCA-отчёт, если есть.

## Реализация

Будет выполнена после создания всех 18 навыков, как часть финальной интеграции.
