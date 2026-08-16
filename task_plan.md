# Task Plan: Профстандарт → Kanban Pipeline Architecture

## Goal

Построить исполняемый pipeline ТФ→ТД через Hermes kanban: каждая ТФ — sequential chain, каждый ТД — skill.

## Current Phase

Phase 2 complete (tested on local Hermes)

## Phases

### Phase 0: Foundation (прошлая сессия)

- [x] Task-centric knowledge graph (315 nodes, 2263 edges)
- [x] Normative docs (147н, 148н, 170н)
- [x] Skills/knowledge at TF level
- [x] Cross-standard analysis (06.013, 06.043, 08.035)

### Phase 1: Pipeline Architecture Design

- [x] Analyse Hermes workflow/pipeline mechanisms
- [x] Analyse all 120 ТД → skill suitability (59% atomic, 41% complex, 0% impossible)
- [x] Compare: parent-child DAG vs sequential chain
- [x] Design: TP = sequential TD chain via kanban parent-child
- **Status:** complete

### Phase 2: Implementation & Test

- [x] Save architecture: `docs/pipeline-architecture.md`
- [x] Write seeder: `scripts/seed-tf-pipeline.py`
- [x] Test on local Hermes (ОТФ-А: 4 ТФ, 24 ТД)
- [x] Verify auto-promote mechanics
- [x] Execute full А/01.6 pipeline (10 ТД → TF summary)
- **Status:** complete

### Phase 3: TF Executor Skill

- [ ] Create skill files for each TD type (analysis-*, creation-*, coordination-*)
- [ ] Wire skill execution with real LLM call
- [ ] Test data handoff between TDs (kanban metadata)

### Phase 4: Monitor + Coverage

- [ ] Auto-update labor-coverage-registry.yaml on TF-summary complete
- [ ] PDCA report includes pipeline stats
- [ ] Cron integration for routine execution

### Phase 5: Scale to Other Standards

- [ ] 06.013 (17 ТФ, 94 ТД)
- [ ] 06.043 (48 ТФ, 159 ТД)
- [ ] 08.035 (8 ТФ, 54 ТД)

## Key Findings

| Discovery | Reference |
|-----------|-----------|
| Kanban auto-promote: child → ready when parent completes | Tested: TD-01 complete → TD-02 ready |
| Sequential chain: TD1→TD2→...→TDN→TF-summary | Tested: 10/10 TDs in A/01.6 |
| First TD without parent = ready, rest = todo | Важно для старта pipeline |
| TF-summary linked to last TD = coverage trigger | Аккумулирует метрики |
| Hermes `--parent` flag на `kanban create` | Создаёт parent-child DAG |
| `--workflow-template-id` недоступен на create | Хранить в body (v2 schema exists) |

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| Sequential chain (not hierarchical parent-child) | Kanban auto-promote работает от complete предыдущего, не от родителя |
| First TD without parent | Стартует как ready, без ручного promote |
| TF-summary linked to last TD | Coverage registry обновляется когда все ТД выполнены |
| Skills as `--skill` on each TD | Hermes force-loads skills per task |

## Errors Encountered

| Error | Attempt | Resolution |
|-------|---------|------------|
| `--workflow-template-id` и `--step-key` не существуют на create | 1 | Хранить в body вместо CLI flags |
| `cannot promote: unsatisfied parent dependencies` | 1 | Перешли на chain-модель (TD зависит от TD, не TF) |
| `cannot complete: unknown id` | 1 | Task нужно сначала claim (running), потом complete |
