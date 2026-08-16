# Findings & Decisions

## Requirements

- Профстандарт 07.007 → исполняемый pipeline в Hermes kanban
- ТФ = sequential chain of ТД, каждый ТД = skill
- Pipeline должен поддерживать crash recovery, data handoff, coverage tracking

## Research Findings

### Pipeline Model

| Аспект | Результат |
|--------|-----------|
| Механизм | Kanban parent-child DAG с auto_promote_children: true |
| Chain type | Sequential (TD1→TD2→...→TDN→TF-summary) |
| First TD | Без parent → ready (может быть взят немедленно) |
| N-й TD | parent=TD-N-1 → todo (auto-promote после complete предыдущего) |
| TF-summary | parent=TD-N → todo (auto-promote после complete последнего ТД) |

### Kanban CLI facts

- `--parent` flag: работает на `kanban create` (добавляет parent-child зависимость)
- `--workflow-template-id` и `--step-key`: только на `kanban list`, НЕ на `create`
- `auto_promote_children: true`: задача переходит todo→ready, когда ВСЕ её parent'ы в done
- `kanban complete`: требует статус running (нужно claim сначала)
- `kanban promote --force`: обходит parent-child защиту (для административных действий)

### Тест ОТФ-А (2026-07-26)

```
Seed: 4 TF parents + 24 TD children → 28 задач
Pipeline: А/01.6 (10 ТД)
Исполнение: claim TD-01 → complete → auto-promote TD-02 → claim → complete → ...
           ... → complete TD-10 → auto-promote TF-summary → claim → complete
Результат: all 10/10 TDs + 1/1 TF-summary = 11/11 done ✅
```

## Technical Decisions

| Decision | Rationale |
|----------|-----------|
| Sequential chain (TD→TD), not hierarchical (TF→TD) | Kanban auto-promote зависит от complete parent'а, не от родителя иерархии |
| Body JSON вместо workflow_template_id | CLI не поддерживает create с этими flags; DB schema имеет колонки (v2) |
| First TD without parent | Стартует как ready, без необходимости promote |
| TF-summary как отдельная задача | Coverage update, aggregation, PDCA trigger |
| `--skill` per TD | Force-load нужного skill для каждого типа ТД |

## Pipeline Stats

| Metric | Value |
|--------|-------|
| TFs seeded | 18 (4 per OTF A/B, 5 OTF C, 4 OTF D) |
| TDs per TF | avg 6.7 (min 3, max 10) |
| Total TD tasks | 120 |
| Total TF-summary | 18 |
| Total kanban tasks | 138 |
| Chain length | 3–11 tasks per chain |

## Resources

- `docs/standards/07.007/` — YAML-файлы (5 шт)
- `scripts/seed-tf-pipeline.py` — seeder pipeline → kanban
- `docs/pipeline-architecture.md` — архитектурный документ
- `~/.hermes/kanban.db` — SQLite kanban database
