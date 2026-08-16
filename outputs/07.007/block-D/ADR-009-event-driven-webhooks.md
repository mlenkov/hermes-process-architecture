# ADR-009: Событийная модель webhooks (event-driven notifications)

**Дата:** 2026-08-16
**Статус:** Утверждён
**Автор:** mais
**Профстандарт:** 07.007 «Специалист по процессному управлению»
**Связан с:** ADR-006 (Human-in-the-Loop), ADR-007 (идемпотентность)

---

## Проблема

Архитектура работает в чисто polling-режиме: исполнитель (executor) периодически
опрашивает kanban, внешние системы и User_Operator не получают уведомлений о
событиях pipeline. Это создаёт три проблемы:

1. **Задержка реакции на HITL-точки.** Артефакт-запрос (ADR-006,
   `approval-request.yaml`) создаётся, но никто не узнаёт о нём, пока не запустится
   следующий цикл опроса.
2. **Нет трассировки событий.** Невозможно подписаться на `artifact.generated` —
   внешний дашборд, CI или оркестратор другого уровня вынуждены самостоятельно
   сканировать файловую систему.
3. **Ошибки pipeline невидимы.** `pipeline.blocked` фиксируется только в kanban
   (статус blocked) и в escalate-файлах — нет активного сигнала.

## Контекст

- Исполнитель навыков — единый `scripts/execute-tf-pipeline.py` (профиль mais,
  ADR-008). Навыки запускаются в sandbox-подпроцессах и **не имеют доступа в сеть**
  (принцип изоляции: навык — pure data generator).
- config.yaml уже содержит sandbox-настройки (skill_timeout, rlimits) и читается
  executor'ом — естественное место для `webhook_url`.
- ADR-007 гарантирует: повторный запуск с валидным артефактом завершается на
  Шаге 0 (Skipping generation) — событий при этом НЕ возникает, и webhook слать
  не нужно.

## Варианты

### А: Навыки сами отправляют webhooks

**Плюсы:** событие отправляется в момент генерации, без посредника.
**Минусы:** навыки получают сетевой доступ (нарушение изоляции); дублирование
логики в каждом навыке; sandbox-ограничения (RLIMIT, no network) конфликтуют;
отсутствие единой точки контроля.

### Б: Executor отправляет все webhooks (ВЫБРАН)

**Плюсы:** единая точка отправки; навыки остаются изолированными; executor уже
знает результат (артефакт записан, quality прочитан, reclaim выполнен); легко
добавить новые события.
**Минусы:** требуется аккуратно определить точки вызова; событие шлётся после
завершения шага (не в реальном времени внутри навыка) — приемлемо для данного
уровня зрелости.

### В: Очередь/брокер (RabbitMQ/Kafka)

**Плюсы:** надёжная доставка, replay.
**Минусы:** избыточная инфраструктура для текущего масштаба; усложнение деплоя.

## Решение

**Выбран вариант Б.** Отправляет webhooks ТОЛЬКО executor
(`scripts/execute-tf-pipeline.py`). Навыки не шлют webhooks и не ходят в сеть.

### Транспорт

- HTTP POST, JSON body, через стандартную библиотеку `urllib.request`.
- Endpoint: `webhook_url` из `config.yaml` (корень проекта).
- `timeout=5` секунд.
- `try/except`: недоступность endpoint → `[WARN]` в лог, **НЕ ошибка задачи** —
  исполнение pipeline продолжается.

### События

| Событие | Условие отправки | Payload-поля |
|---------|------------------|--------------|
| `artifact.generated` | После успешной записи артефакта (Шаг 4 выполнен, schema_valid) | event, timestamp, tf_code, skill, artifact, schema_valid, awaiting_approval |
| `approval.requested` | quality основного артефакта содержит `awaiting_approval: true` (HITL-точка, ADR-006) | event, timestamp, tf_code, skill, artifact, schema_valid, awaiting_approval |
| `pipeline.blocked` | При reclaim/ошибке навыка (timeout, исключение, падение генерации) | event, timestamp, tf_code, skill, artifact (пустой/недоступный), schema_valid, awaiting_approval |

### Правила

- `webhook_url` отсутствует или пуст → отправка **пропускается** (система остаётся
  полностью работоспособной в polling-режиме).
- Skip-путь Шага 0 (ADR-007: `[INFO] Artifact already exists... Skipping generation`)
  → webhooks НЕ шлются (события нет — данные не изменились).
- Неуспешная отправка (сеть, таймаут, HTTP != 2xx) → `[WARN] webhook failed:
  <event> ...`, continue.

### Пример payload

```json
{
  "event": "approval.requested",
  "timestamp": "2026-08-16T21:00:00Z",
  "tf_code": "С/03.7",
  "skill": "implementation-lead",
  "artifact": "outputs/07.007/block-C/C-03.7-implementation-plan.yaml",
  "schema_valid": true,
  "awaiting_approval": true
}
```

## Последствия

- **Плюс:** HITL-запросы (ADR-006) становятся наблюдаемыми — User_Operator может
  получать уведомление об `approval.requested` через внешний endpoint.
- **Плюс:** внешние системы (дашборды, CI) могут подписаться на
  `artifact.generated` / `pipeline.blocked`.
- **Плюс:** навыки остаются изолированными от сети (sandbox-принцип сохранён).
- **Минус:** события — best-effort (без retry/очереди); при недоступности endpoint
  событие теряется, но pipeline не деградирует.
- **Минус:** требуется обновить `scripts/execute-tf-pipeline.py` (send_webhook +
  точки вызова).
