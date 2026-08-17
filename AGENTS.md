# ARCHITECTURE — Мульти-стандартная архитектура → Hermes Agent

Актуальная, рабочая архитектура покрытия профессиональных стандартов РФ исполняемыми
навыками Hermes Agent. Три активных стандарта: **07.007** (процессное управление),
**06.043** (интернет-маркетинг), **06.013** (информационные ресурсы/контент).
См. ADR-001…ADR-014 (outputs/07.007/block-D/ADR-*.md) — отклонения ломают автономность.

## Профили (ADR-008, ADR-014)

| Профиль Hermes | Роль | Обслуживает |
|----------------|------|-------------|
| `mais` | архитектор всех стандартов; исполнитель ТОЛЬКО 07.007 | 07.007 (A–D), 19 навыков |
| `ppc` | контекст/медийная реклама | 06.043: B, E, F |
| `seo` | поисковое продвижение (семантика, онпейдж, линкбилдинг, тех) | 06.043: A, D |
| `smm` | соцмедиа (площадки, контент, соцреклама, привлечение) | 06.043: C, G |
| `analyst` | аналитика | 06.043: H |
| `marketing` | стратегия продвижения | 06.043: I |
| `digital` | тимлид (координация каналов, реализация стратегии) | 06.043: J, K, L |
| `copywriter` | контент (исполнитель делегирования из 06.043) | 06.013 |

Имя профиля = имя директории (~`.hermes/profiles/<name>`), НЕ display name
(напр. профиль отображается «ppc-specialist», но реальное имя — `ppc`).

## Борды Kanban

`std-7007` (07.007), `std-0643` (06.043), `std-0613` (06.013). dispatch_in_gateway: true.

## Ключевые ADR и модели

- **ADR-010 гибрид**: seeder = нативный Kanban create + --parent + idempotency-key;
  executor (07.007) = детерминированный Python-подпроцесс.
- **ADR-011 мульти-стандарт**: неймспейс docs/standards/<S>/, outputs/<S>/, борды std-<digits>,
  скрипты с --standard; нормализация алфавита (приложение).
- **ADR-012 делегирование**: контентные ТД 06.043 → 06.013; делегатор сохраняет
  ТЗ/контроль/приёмку; оркестрация поэтапная, эволюция — event-driven сидинг (не реализован).
- **ADR-013 доменная модель**: доменные стандарты = нативный LLM-воркер +
  детерминированная приёмка (accept-artifact / accept-delegation). 07.007 — детерминированный executor.
- **ADR-014 per-TF профили**: исполнитель объявляется в mapping (поле `profile`).
- **ADR-006 HITL**: приёмка делегированного контента → approval-request (пример APPROVAL-APR-01).
- **ADR-009 webhooks**: executor шлёт artifact.generated / approval.requested / pipeline.blocked.

## Скрипты Фазы 9

- `validate-registry.py --standard` — семантика WARN/ERROR (см. ниже)
- `seed-tf-pipeline.py --standard` — seeder (нативный Kanban)
- `execute-tf-pipeline.py` — executor (07.007, детерминированный)
- `accept-artifact.py` — приёмка артефакта LLM-воркера (доменные); флаг `--tds-completed`
  (status из 1/N→partial, N/N→covered) + автоподтягивание skill_path из per-TF mapping
- `accept-delegation.py` — приёмка кросс-стандартного делегирования
- `webhook-listener.py` — mock-приёмник webhook-событий

## Семантика валидатора registry (Фаза 9)

- mapping = статическое покрытие; registry = динамическое (после исполнения).
- **ERROR**: skill_path mismatch mapping↔registry; запись registry для ТФ вне mapping;
  covered без основного артефакта на диске; mapping указывает на несуществующий навык;
  documented_gaps skill_path mismatch.
- **WARN**: covered/partial без записи registry («назначено, не исполнено»).

## Нормализация алфавита (ADR-011, приложение)

Кириллица→латиница для lookup: `А→A, В→B, С→S, Н→N, Е→E, К→K`. Хранение — как в
официальном стандарте; lookup/сравнение нормализуют обе стороны (validate-registry.py,
accept-artifact.py). Запись `LF-06.043-С/01.4` и `LF-06.043-S01.4` — один ключ по смыслу.

## Доменные навыки: источник истины

Доменные навыки живут в **репозитории** `profiles/<profile>/skills/<skill>/` (8а.4/8d).
Деплой в рабочий профиль: `~/.hermes/profiles/<profile>/skills/agency/<skill>/SKILL.md`.
07.007-навыки mais также в репозитории `profiles/mais/skills/`.

## Зрелость и операционный бэклог (Фаза 9)

- **07.007**: 18 ТФ, 9/9/0, 17 записей + documented gap С/05.7 — зрелый, детерминированный.
- **06.043**: 48 ТФ, 1/47/0, 7 записей, 41 WARN — бэклог исполнений.
- **06.013**: 17 ТФ, 2/8/7, 1 запись, 9 WARN; 7 missing — бэклог навыков.
- Эволюция: event-driven кросс-стандартный сидинг (ADR-012) — зафиксирована, не реализована.

## Валидация

```bash
python3 scripts/validate-registry.py --standard 07.007   # True / 0 WARN
python3 scripts/validate-registry.py --standard 06.043   # True / 41 WARN
python3 scripts/validate-registry.py --standard 06.013   # True / 9 WARN
```
