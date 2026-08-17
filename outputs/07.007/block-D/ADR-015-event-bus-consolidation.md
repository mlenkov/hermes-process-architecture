# ADR-015: Единая событийная шина (HITL + webhooks)

**Дата:** 2026-08-17
**Статус:** Утверждён
**Автор:** mais
**Объединяет:** ADR-006 (HITL), ADR-009 (event-driven webhooks)
**Supersedes:** ADR-006, ADR-009
**Профстандарты:** 07.007, 06.043, 06.013

---

## Проблема

ADR-006 (Human-in-the-Loop) и ADR-009 (webhooks) исторически развивались раздельно,
но реализуют **одну и ту же событийную шину**: генерация артефакта → уведомление →
(при необходимости) человеческое решение. Разделение создаёт дублирование и путаницу:
- `approval.requested` (из ADR-009) — это переформулировка HITL-точки (ADR-006);
- `artifact.generated` и `pipeline.blocked` — те же события разной важности из одной модели.

## Контекст

- Executor (`execute-tf-pipeline.py`) — единственная точка отправки событий (ADR-009);
  навыки изолированы от сети.
- HITL-приёмка (`accept-artifact.py`, `accept-delegation.py`) порождает
  `approval-request.yaml` (ADR-006-структура) и завершается.
- Webhook-приёмник (`webhook-listener.py`) — mock для тестирования.

## Решение

**Единая событийная модель.** Один документ описывает и уведомления, и HITL-запросы
как разновидности событий одного транспорта. Роли:
- **Notification-роль** (`artifact.generated`, `pipeline.blocked`) — информирует;
- **Decision-роль** (`approval.requested`) — запрашивает человеческое решение;
  результат решения (`approved`/`rework`) — событие `approval.decided`.

### События (единый реестр)

| Событие | Роль | Условие | Payload |
|---------|------|---------|---------|
| `artifact.generated` | notification | артефакт записан, schema_valid | event, timestamp, tf_code, skill, artifact, schema_valid, awaiting_approval |
| `pipeline.blocked` | notification | reclaim/ошибка навыка | event, timestamp, tf_code, skill, artifact, schema_valid, awaiting_approval |
| `approval.requested` | decision | HITL-точка (awaiting_approval) | event, timestamp, tf_code, skill, artifact, request_id, options |
| `approval.decided` | decision | оператор утвердил/вернул | event, request_id, decision, decided_by, basis, timestamp |

### Транспорт

- HTTP POST, JSON, `urllib.request`, `timeout=5`.
- `webhook_url` в `config.yaml`; отсутствие → polling-режим (тихий skip).
- Недоступность endpoint → `[WARN]`, НЕ ошибка задачи.
- Skip-путь ADR-007 → событий нет.

### HITL-протокол (из ADR-006, без изменений семантики)

Навык НЕ принимает решение за человека: формирует `approval-request.yaml`
(APR-xxx: request_id, question, options, context_ref, deadline) и фиксирует
`awaiting_approval: true`. Решение принимает оператор (User_Operator) →
`approval.decided` пишется в `*-acceptance-decision.yaml`.

## Последствия

- **Плюс:** один ADR вместо двух — меньше дублирования при изучении.
- **Плюс:** accept-* скрипты и webhook-listener ссылаются на единый реестр событий.
- **Плюс:** HITL-приёмка становится наблюдаемой (approval.requested + approval.decided).
- **Минус:** старые ссылки на ADR-006/009 в коде/README нужно обновить на ADR-015
  (постепенно, без обращения к устаревшим номерам).

## Суперседирование

Объединяет и заменяет ADR-006, ADR-009. Не отменяет ADR-007 (идемпотентность),
ADR-010–014.
