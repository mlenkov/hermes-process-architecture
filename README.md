# Hermes Process Architecture

**Мультиагентная система для покрытия профстандартов РФ навыками Hermes Agent**

Каждая Трудовая Функция (ТФ) профстандарта покрывается навыком, который исполняется
автономно через Kanban: `seeder → (executor | нативный LLM-воркер) → артефакт → registry → validate`.
Система поддерживает несколько профстандартов (ADR-011) с per-TF профилями-исполнителями (ADR-014).

## Стандарты

| Стандарт | Название | ТФ | covered | partial | missing | Записей registry | WARN |
|----------|----------|-----|---------|---------|---------|------------------|------|
| **07.007** | Специалист по процессному управлению | 18 | 9 | 9 | 0 | 17 (+1 gap С/05.7) | 0 |
| **06.043** | Специалист по интернет-маркетингу | 48 | 1 | 47 | 0 | 7 | 41 |
| **06.013** | Специалист по информационным ресурсам | 17 | 2 | 8 | 7 | 1 | 9 |

> **Семантика (8e):** mapping = статическое покрытие; registry = динамическое (после исполнения).
> covered без записи → ERROR; partially_covered без записи → **WARN** «назначено, не исполнено».

```bash
python3 scripts/validate-registry.py --standard 07.007   # → Registry valid: True (0 WARN)
python3 scripts/validate-registry.py --standard 06.043   # → Registry valid: True (41 WARN)
python3 scripts/validate-registry.py --standard 06.013   # → Registry valid: True (9 WARN)
```

## Топология профилей (ADR-014)

Исполнитель объявляется per-TF в mapping (поле `profile`), а не один на стандарт:

| Профиль | Роль | Стандарты/блоки |
|---------|------|------------------|
| **mais** | Архитектор стандартов; исполнитель ТОЛЬКО 07.007 (ADR-008) | 07.007 (A–D) |
| **ppc** | Контекст/медийная реклама | 06.043: B, E, F |
| **seo** | Поисковое продвижение | 06.043: A, D |
| **smm** | Соцмедиа | 06.043: C, G |
| **analyst** | Аналитика | 06.043: H |
| **marketing** | Стратегия | 06.043: I |
| **digital** | Тимлид, переговоры, команда | 06.043: J, K, L |
| **copywriter** | Контент (исполнитель делегирования 06.043) | 06.013 |

## Архитектура (ключевые ADR)

- **Гибрид** (ADR-010): seeder = нативный Kanban, executor = детерминированный Python.
- **Мульти-стандарт** (ADR-011): неймспейс `docs/standards/<S>/`, `outputs/<S>/`, борды `std-<digits>`,
  скрипты с `--standard`.
- **Кросс-стандартное делегирование** (ADR-012): контентные ТД 06.043 → 06.013
  (Е/03.5, F/03.5, G/03.5 — full; А/02.4, А/03.4, В/01.4, В/02.4, С/02.4, С/03.4,
  D/04.5, G/02.5, J/02.6 — partial). Делегатор сохраняет ТЗ/контроль/приёмку.
- **Доменная модель исполнения** (ADR-013): доменные стандарты = нативный LLM-воркер +
  детерминированная приёмка (`accept-artifact` / `accept-delegation`); 07.007 сохраняет
  детерминированный executor.
- **Per-TF профили** (ADR-014): топология выше.
- **HITL** (ADR-006): приёмка делегированного контента → approval-request.
- **Webhooks** (ADR-009): executor шлёт события (artifact.generated / approval.requested / pipeline.blocked).

## Быстрый старт

Требования: Python 3.10+, `pyyaml`, локальный Hermes Agent (`hermes kanban`).

### 1. Валидация консистентности

```bash
python3 scripts/validate-registry.py --standard 07.007
python3 scripts/validate-registry.py --standard 06.043
python3 scripts/validate-registry.py --standard 06.013
```

### 2. Автономный цикл (Kanban) — стандарт 07.007

```bash
# создать задачи для ТФ (нативный Kanban, ADR-010)
python3 scripts/seed-tf-pipeline.py --tf "А/01.6"
# исполнить ready-задачи (повторять до "No ready tasks")
python3 scripts/execute-tf-pipeline.py
```

### 3. Доменный стандарт (06.043 / 06.013) — нативный LLM-воркер

```bash
# сид ТФ на борд std-0643 (assignee из per-TF profile)
python3 scripts/seed-tf-pipeline.py --standard 06.043 --tf "B/01.4" --dry-run

# нативный dispatcher спавнит LLM-воркера профиля
hermes kanban --board std-0643 dispatch --max 2

# детерминированная приёмка артефакта воркера
python3 scripts/accept-artifact.py --standard 06.043 --tf "B/01.4" \
    --artifact outputs/06.043/block-B/B-01.4-...yaml --profile ppc \
    --tds-completed 1/1
```

### 4. Кросс-стандартное делегирование (06.043 → 06.013)

```bash
# Этап 1. ТЗ (делегатор ppc, 06.043) → борд std-0643, воркер создаёт ТЗ
# Этап 2. Контент (copywriter, 06.013) → борд std-0613, воркер читает ТЗ
# Этап 3. Детерминированная приёмка (06.043, без LLM):
python3 scripts/accept-delegation.py --standard 06.043 --tf "E/03.5" \
    --tz outputs/06.043/block-E/E-03.5-content-tz.yaml \
    --content outputs/06.013/block-B/B-02.5-content-materials.yaml \
    --request-id APR-01 --operator "Максим"
```
Оркестрация поэтапная (нативный Kanban не даёт кросс-бордовых связей), эволюция —
event-driven сидинг (зафиксирована, не реализована).

## Скрипты

| Скрипт | Назначение |
|--------|------------|
| `validate-registry.py` | Валидация mapping ↔ registry (`--standard`) |
| `seed-tf-pipeline.py` | Seeder (нативный Kanban: create + --parent + idempotency-key) |
| `execute-tf-pipeline.py` | Executor (детерминированное исполнение, 07.007) |
| `accept-artifact.py` | Детерминированная приёмка артефакта LLM-воркера (доменные) |
| `accept-delegation.py` | Детерминированная приёмка кросс-стандартного делегирования |
| `webhook-listener.py` | Mock-приёмник webhook-событий (ADR-009) |

## Структура проекта

```
.
├── profiles/{mais,ppc,seo,smm,digital,copywriter,analyst,marketing}/skills/
│              # Источник истины доменных навыков (8а.4/8d); деплой в ~/.hermes
├── outputs/<S>/               # Артефакты, mapping, registry по стандарту
│   ├── labor-coverage-registry.yaml
│   ├── labor-function-to-skill-mapping.yaml
│   └── block-*/               # артефакты по блокам
├── docs/standards/<S>/        # Локальные копии профстандартов (source.md, otf-section-*)
├── docs/ADR/  + outputs/07.007/block-D/ADR-*.md
├── scripts/                   # см. выше
├── config.yaml                # Sandbox/webhook конфигурация
└── AGENTS.md                  # Контекст проекта
```

## ADR 001–014

| ADR | Решение | Статус |
|-----|---------|--------|
| 001 | Структура файлов артефактов | Утверждён |
| 002 | Один ТД = один артефакт | Утверждён |
| 005 | Mapping «ТФ → навык» | Утверждён |
| 006 | HITL approval-requests | Утверждён |
| 007 | Registry / идемпотентность / documented gaps | Утверждён |
| 008 | Единый исполнитель 07.007 — профиль mais | Утверждён |
| 009 | Event-driven webhooks | Утверждён |
| 010 | Гибрид: нативный Kanban + детерминированный executor | Утверждён |
| 011 | Мульти-стандартный неймспейс | Утверждён |
| 012 | Кросс-стандартное делегирование (06.043→06.013) | Утверждён |
| 013 | Доменная модель исполнения | Утверждён |
| 014 | Профильная топология доменных стандартов | Утверждён |

## Зрелость и операционный бэклог

- **07.007**: 18 ТФ, 9/9/0, 17 записей + documented gap С/05.7 — зрелый, детерминированный исполняемый.
- **06.043**: 48 ТФ, 1/47/0, 7 записей, 41 WARN — **бэклог исполнений** (47 ТФ назначены, не исполнены).
- **06.013**: 17 ТФ, 2/8/7, 1 запись, 9 WARN; 7 missing — **бэклог навыков**.
- Делегирование 06.043→06.013 работает end-to-end (пилот Е/03.5→B/02.5, приёмка APR-01 утверждена).
- **Эволюция**: event-driven кросс-стандартный сидинг (webhook artifact.generated, ADR-012) —
  зафиксирована, не реализована.

## Лицензия

[MIT](LICENSE)
