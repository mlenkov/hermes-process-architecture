# Progress Log

## Session 1: 2026-07-26 — Knowledge Graph

### Phase 0-4: Task-Centric Graph

- ✅ planning-with-files persistence
- ✅ build-graph-from-yaml.py (315 nodes, 2263 edges)
- ✅ graph built + validated

### Phase 5-6: Normative + Repo

- ✅ Normative docs (147н, 148н, 170н, structure)
- ✅ Skills/knowledge at TF level (per 147н/170н)
- ✅ Repo cleanup: detached git, moved to docs/

---

## Session 2: 2026-07-26 — Pipeline Architecture

### Phase 1: Research & Design

- **Status:** complete
- Explored Hermes workflow mechanisms (kanban, delegate, cron, execute_code)
- Analysed 120 ТД → skill suitability (59% atomic, 41% complex, 0% impossible)
- Read server-side LF YAML format
- Read existing kanban schema (workflow_template_id, current_step_key columns)
- Designed sequential chain model: TD1→TD2→...→TDN→TF-summary

### Phase 2: Implementation & Test

- **Status:** complete
- **Files created/modified:**
  - `docs/pipeline-architecture.md` — architecture document
  - `scripts/seed-tf-pipeline.py` — seeder script
  - `task_plan.md` — updated
  - `findings.md` — updated
  - `progress.md` — updated

- **Test results (local Hermes, ОТФ-А):**

| Test | Result |
|------|--------|
| Seed ОТФ-А (4 ТФ, 24 ТД) | ✅ 28 tasks created (4 TF + 24 TD) |
| First TD без parent → ready | ✅ 4 tasks ready |
| Subsequent TDs with parent → todo | ✅ 24 tasks todo |
| Auto-promote after complete | ✅ TD-01 done → TD-02 ready |
| Full chain А/01.6 (10 ТД) | ✅ All 10 completed sequentially |
| TF-summary auto-promote | ✅ После complete TD-10 → TF-summary ready |
| TF-summary complete | ✅ 11/11 done |

## Error Log

| Timestamp | Error | Attempt | Resolution |
|-----------|-------|---------|------------|
| Session 2 | `--workflow-template-id` unrecognized on create | 1 | Store in body JSON |
| Session 2 | `cannot promote: unsatisfied parent dependencies` | 1 | Changed model to sequential chain (TD→TD) |
| Session 2 | `cannot complete: unknown id` | 1 | Must claim (→ running) before complete |
| Session 2 | OTF filter: "A" (Latin) != "А" (Cyrillic) | 1 | Added Cyrillic→Latin normalization |

## 5-Question Reboot Check

| Question | Answer |
|----------|--------|
| Where am I? | Phase 2 complete — pipeline tested on Hermes |
| Where am I going? | Phase 3: TF executor skill with real LLM |
| What's the goal? | Executable ТФ→ТД pipeline via Hermes kanban |
| What have I learned? | Chain model: TD1→TD2→...→TF-summary |
| What have I done? | Architected + implemented + tested pipeline on 4 TFs |
