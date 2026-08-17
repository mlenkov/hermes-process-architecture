# ADR-010: Гибридная архитектура — нативный Kanban для seeder + детерминированный executor

**Дата:** 2026-08-17
**Статус:** Утверждён
**Автор:** mais
**Профстандарт:** 07.007 «Специалист по процессному управлению»
**Связан с:** ADR-001 (standalone skills), ADR-007 (идемпотентность), ADR-009 (webhooks)

---

## Проблема

Аудит нативных возможностей Hermes Agent выявил ~40% функционального
дублирования между нашим seeder/executor и нативным Kanban. Возникло два
неприемлемых варианта развития:

1. **Оставить всё как есть** — техдолг растёт: кастомная seed-логика
   дублирует нативный create/dependencies, stale-detection и auto-promote
   реализованы вручную.
2. **Полная миграция на нативный Kanban** — нативный worker исполняет
   задачу через LLM-агента, что ломает детерминизм генерации артефактов,
   dependency gate по файлам и схему webhook-событий.

Полная миграция невозможна из-за фундаментальных различий в исполнении.

## Контекст

**Нативный Kanban покрывает:**

- Создание задач с dependencies (`--parent`)
- Auto-promote (todo → ready когда parents done)
- Idempotent create (`--idempotency-key`)
- Stale reclaim (dispatcher reclaims stale)
- Failure limit (auto-block после N фейлов)
- Workspace isolation (scratch/worktree/dir)

**НЕ покрывает:**

- Детерминированное исполнение Python-кода (нативный worker = LLM-агент)
- Dependency gate по файлам (ICOM Inputs — нативный промотит только по parents)
- Отправка webhook-событий (adapter = приём извне)
- Registry покрытия 07.007 (kanban не знает про executed_by/artifacts/gaps)

Верификация (2026-08-17, ветка `refactor/native-kanban`):

- migrate-to-native-kanban.py: 1 ТФ (А/01.6) → 1 TF + 10 TD на тестовом борде,
  la-001 ready, la-002..la-010 todo, `show` подтверждает `parents`
- Идемпотентность: повторный create с тем же `--idempotency-key` вернул тот же
  task_id (дубликатов 0)
- Нативный dispatcher: после complete la-001 → Spawned: 1 (la-002 promoted),
  stale-claim с истёкшим TTL → Reclaimed: 1
- Тестовый борд удалён после верификации

## Решение

**Гибридная модель:**

- **Seeder:** использует нативный `hermes kanban create` с `--parent`,
  `--idempotency-key`, `--assignee mais` (scripts/migrate-to-native-kanban.py)
- **Executor:** наш детерминированный Python-код с RLIMIT sandbox
  (scripts/execute-tf-pipeline.py — остаётся)
- **Skills:** исполняются как subprocess из SKILL.md, Шаг 0 (ADR-007) остаётся
- **Dependencies по файлам:** наш executor (depends_on_artifacts из ICOM Inputs)
- **Webhooks (ADR-009):** наш отправитель (urllib POST) — нативный adapter
  для этого не предназначен

## Последствия

**Плюсы:**

- Убрано дублирование seeder-логики (~200 строк)
- Сохранён детерминизм исполнения навыков
- Использованы production-ready возможности Hermes (dispatcher, workspace isolation, idempotency-key)
- Dependency gate по файлам работает через наш executor
- Откат безопасен: старые скрипты сохранены до полной верификации

**Минусы:**

- Два слоя оркестрации (нативный kanban + наш executor)
- Сложнее отладка (нужно понимать оба слоя)
- 6b-пилот (нативный dispatcher как исполнитель) отложен — решение по полному
  демонтажу executor'а принимается отдельно после пилота

## Суперседирование

Не суперседирует другие ADR. Дополняет ADR-001 (standalone skills),
ADR-007 (идемпотентность), ADR-009 (webhooks).
