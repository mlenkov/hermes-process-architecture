# Pipeline Architecture: ТФ → ТД через Kanban

## 1. Концептуальная модель

```
L1: ПРОФСТАНДАРТ РФ
  L2: ОТФ (A/B/C/D)
    L3: ТФ = цепочка ТД (sequential chain)
      ТД-01 (ready) ──parent──→ ТД-02 (todo) ──parent──→ ТД-03 (todo) ──...──→ ТД-N (todo) ──parent──→ TF-summary (todo)
        ↑ skill_01        ↑ skill_02        ↑ skill_03                      ↑ skill_N        ↑ coverage update
    L4: Coverage Registry ⟷ PDCA Reports
```

**ТФ** = sequential pipeline: kanban-задачи ТД, связанные parent-child цепочкой.
**ТД** = skill: kanban-задача с `--skill` для force-load и `--parent` на предыдущий ТД.
**TF-summary** = завершающая задача, которая аккумулирует результаты и обновляет coverage.

---

## 2. Pipeline chain (tested on Hermes v0.18.2)

### 2.1 Создание цепочки

```python
# Для каждой ТФ:
# 1. Создать TF-summary задачу (статус: todo, будет готова после всех ТД)
tf_task = kanban_create(title="🔄 А/01.6: Сбор информации о процессе", body=tf_body)

# 2. Создать цепочку ТД:
prev_id = None
for i, td in enumerate(actions, 1):
    td_id = kanban_create(
        title=f"la-{i:03d}: {td.text}",
        parent=prev_id,           # None для первого → ready, иначе → todo
        skill=td.skill_name,
        body=td_body
    )
    prev_id = td_id

# 3. Последний ТД → TF-summary
kanban_link(prev_id, tf_task)     # TF-summary готовится когда все ТД выполнены
```

### 2.2 Статусы pipeline

```
ТД-01: ready        (без parent, может быть взят в работу)
ТД-02: todo         (parent=ТД-01, auto-promote после complete ТД-01)
ТД-03: todo         (parent=ТД-02, auto-promote после complete ТД-02)
...
ТД-N:  todo         (parent=ТД-(N-1))
TF-summary: todo    (parent=ТД-N, auto-promote после complete ТД-N)
```

### 2.3 Data handoff

При `kanban_complete` каждого ТД:
```bash
kanban_complete <td-id> \
  --summary "Выполнено: Определение целей процесса" \
  --metadata '{"la_id":"la-001","next_la":"la-002","output":{...}}'
```

Следующий ТД получает данные через `kanban context` (видит body + parent results).

---

## 3. Состояния pipeline

```
  ┌──────────┐
  │  ready   │ ◄── ТД-01 (без parent, стартует первым)
  └────┬─────┘
       ↓ claim
  ┌──────────┐
  │ running  │ ◄── worker выполняет skill для ТД-01
  └────┬─────┘
       ↓ complete
  ┌──────────┐
  │   done   │ ◄── auto_promote_children → ТД-02 становится ready
  └──────────┘
       │
  ┌──────────┐
  │  ready   │ ◄── ТД-02 (parent=ТД-01 completed)
  └────┬─────┘
       ↓ ... повторяется для всех ТД ...
  ┌──────────┐
  │  ready   │ ◄── TF-summary (parent=ТД-N completed)
  └────┬─────┘
       ↓
  ┌──────────┐
  │  done    │ ◄── coverage registry updated
  └──────────┘

Если ТД упал:
  ┌──────────┐
  │ blocked  │ → human review → unblock → retry с того же ТД
  └──────────┘
```

---

## 4. Статус реализации (tested 2026-07-26)

### 4.1 Seeder (`scripts/seed-tf-pipeline.py`) — готов, протестирован

```bash
python3 scripts/seed-tf-pipeline.py                     # все 18 ТФ
python3 scripts/seed-tf-pipeline.py --otf A             # только ОТФ-А
python3 scripts/seed-tf-pipeline.py --tf "А/01.6"      # только одну ТФ
python3 scripts/seed-tf-pipeline.py --dry-run           # предпросмотр
python3 scripts/seed-tf-pipeline.py --clean             # очистить перед seed
```

**Создаёт**:
- Один `kanban create` для TF-summary (status: `todo`, parent: last TD)
- N `kanban create --parent=<prev>` для каждого ТД (первый: `ready`, остальные: `todo`)
- `kanban link` для связи последнего ТД → TF-summary

### 4.2 Тестовый прогон (ОТФ-А: 4 ТФ, 24 ТД)

```
Pipeline:  А/01.6 (10 ТД) → А/02.6 (4 ТД) → А/03.6 (4 ТД) → А/04.6 (6 ТД)
Результат:
  - 4 lead TD (la-001) → ready
  - 20 remaining TDs → todo (auto-promote по цепочке)
  - 4 TF-summary → todo (auto-promote после последнего ТД)

  Исполнен А/01.6:
    ТД-01 → claim → complete → auto-promote ТД-02
    ТД-02 → claim → complete → auto-promote ТД-03
    ... (все 10 ТД выполнены последовательно)
    TF-summary → claim → complete → coverage ready
  ✅ Pipeline работает: 10/10 ТД, 1/1 TF-summary
```

### 4.3 Механика auto-promote

Ключевое поведение kanban:
- **child auto-promote**: когда задача с parent завершается (→ `done`), её child автоматически переходит из `todo` в `ready` (dispatcher проверяет `auto_promote_children: true`)
- **первый ТД без parent**: сразу `ready`, может быть взят в работу
- **TF-summary с parent=последний ТД**: становится `ready` только когда все ТД выполнены

---

## 5. Компоненты системы

### 5.1 Seeder (готов, протестирован)

| Параметр | Описание |
|----------|---------|
| `--otf A/B/C/D` | Фильтр по блоку |
| `--tf "А/01.6"` | Фильтр по конкретной ТФ |
| `--dry-run` | Предпросмотр без создания |
| `--clean` | Архивация существующих задач |
| `--yaml-dir PATH` | Путь к YAML-файлам стандарта |

### 5.2 Pipeline executor (нужен следующий шаг)

Worker (профиль mais) получает ТД-задачу:
1. `skill_view("kanban-worker")` — загружает инструкцию
2. Читает `body` (la_id, text, next_la, sequence_index)
3. Выполняет шаги skill'а для данного LA
4. `kanban_complete(metadata={"la_id":"la-001", "output":{...}})`
5. dispatcher: auto_promote → следующий ТД в ready

### 5.3 Monitor + Coverage (нужен следующий шаг)

После complete TF-summary:
```yaml
labor-coverage-registry.yaml:
  LF-07.007-А/01.6:
    status: covered
    last_executed: 2026-07-26T23:23:00Z
    tds_completed: 10/10
    tds_summary:
      la-001: {status: completed, duration_sec: 8}
      la-002: {status: completed, duration_sec: 5}
      ...
    executed_by: mais
```

### 5.4 Обработка ошибок

- **Fail N раз**: `kanban.failure_limit` (default 2) → задача в `blocked`
- **Timeout**: `--max-runtime` → SIGTERM → reclaim → re-ready
- **Dead worker**: dispatcher reclaim → re-ready
- **Human gate**: `kanban_block` → unblock → retry

---

## 6. Схема данных

### TF-summary задача

```yaml
id: t_a2ffb49a
title: "🔄 А/01.6: Сбор информации о процессе"
status: todo             # → ready после complete последнего ТД
assignee: mais
parents: [t_6d24ee88]    # последний ТД
skills: ["kanban-worker"]
body:
  type: tf_pipeline
  function:
    code: "А/01.6"
    name: "Сбор информации о процессе"
  total_actions: 10
  labor_actions:
    - {id: la-001, text: "Определение целей...", sequence_index: 1, profile: mais, skill: kanban-worker}
    - ...
```

### TD задача

```yaml
id: t_4d90f578
title: "la-001: Определение целей процесса"
status: ready            # первый ТД без parent
assignee: mais
skills: ["kanban-worker"]
body:
  la_id: la-001
  text: "Определение целей процесса..."
  sequence_index: 1
  next_la: la-002
  parent_tf: LF-07.007-А/01.6
  otf_code: ОТФ-А
  tf_task_id: t_a2ffb49a
```

---

## 7. IDEF0 execution schema

### 7.1 Формат YAML

В каждый профстандарт (YAML в `docs/standards/`) добавлен блок `execution`, описывающий IDEF0-контекст исполнения ТФ. Блок не ломает существующий парсинг — старые разделы (А/В/С) работают без него.

```yaml
execution:
  recommended_profile: mais           # профиль-исполнитель
  inputs:                             # входы ТФ (IDEF0 Input)
    - id: architecture-current
      description: "Текущая архитектура"
      source_tf: null                 # null = внешний источник
  outputs:                            # выходы ТФ (IDEF0 Output)
    - id: architecture-analysis
      description: "Результаты анализа"
      target_tf: [D/02.7, D/04.7]    # потребители

  actions:                            # IDEF0 per трудовое действие
    - index: 0
      text: "Определение заинтересованных сторон..."  # полный текст ТД
      inputs: [architecture-current]                  # что потребляет
      outputs: [stakeholder-list]                     # что производит
      mechanism:                                      # IDEF0 Mechanism
        profile: mais
        skills: ["stakeholder-mapping"]
```

### 7.2 IDEF0  →  Hermes kanban

| IDEF0 | YAML execution | Hermes kanban |
|-------|---------------|---------------|
| **Activity** | `actions[].text` | kanban task per ТД |
| **Input** | `actions[].inputs[]` | в body задачи как `inputs: [...]` |
| **Output** | `actions[].outputs[]` | в body задачи как `outputs: [...]` |
| **Control** | `необходимые_знания` из профстандарта | RAG-контекст (загружается в skill) |
| **Mechanism** | `actions[].mechanism` | `--assignee` + `--skill` |
| **Декомпозиция** | ТФ → `actions[]` | `--parent` chain |

### 7.3 Data handoff между ТФ

Pipeline execution отслеживает ICOM-связи через метаданные в body задачи:

```json
// TF-level body (TF-summary task)
{
  "type": "tf_pipeline",
  "function": {"code": "D/01.7", "name": "Анализ процессной архитектуры"},
  "total_actions": 8,
  "tf_inputs": [{"id": "architecture-current", "source_tf": null}, ...],
  "tf_outputs": [{"id": "architecture-analysis", "target_tf": ["D/02.7", "D/04.7"]}, ...],
  "labor_actions": [
    {"id": "la-001", "text": "Определение заинтересованных сторон...",
     "inputs": ["architecture-current"], "outputs": ["stakeholder-list"],
     "profile": "mais", "skill": "stakeholder-mapping"}
  ]
}
```

```json
// TD-уровень body (каждый ТД)
{
  "la_id": "la-001",
  "text": "Определение заинтересованных сторон...",
  "inputs": ["architecture-current"],
  "outputs": ["stakeholder-list"],
  "parent_tf": "LF-07.007-D/01.7",
  "otf_code": "ОТФ-D",
  "tf_task_id": "t_a2ffb49a"
}
```

### 7.4 Граф знаний (IDEF0 в graphify)

При запуске `build-graph-from-yaml.py` execution block рождает IDEF0-сущности:

```
[id: idef0_input]    ──input_to──→ [activity: task]  ──output_from──→ [id: idef0_output]
                                         │
                                    executed_by
                                         │
                                    [profile]
```

Graphify-типы:
- `file_type: idef0_input` — артефакты на входе
- `file_type: idef0_output` — артефакты на выходе
- `relation: input_to` — связь вход → активность
- `relation: output_from` — связь активность → выход

Граф поддерживает `graphify path "architecture-current" "methodology-updates"` — полный data flow через OTF-D.

### 7.5 Data flow OTF-D

```
architecture-current (external)
business-strategy (external)
       │
       ▼
┌─────────────────┐    architecture-analysis    ┌─────────────────────┐
│ D/01.7 Анализ   │────────────────────────────▶│ D/02.7 Разработка  │
│ architecture-current                           │                     │
│  → stakeholder-list                            │  → systematized-info
│  → agreed-goals                                │  → selected-reference-model
│  → architecture-requirements                   │  → adapted-model
│  → architecture-data                           │  → architecture-designed
│  → gap-analysis                                │  → agreed-architecture
│  → improvement-opportunities                   │  → architecture-compliance
│  → analysis-report                             └─────────┬───────────┘
│  → architecture-analysis                                   │
└─────────┬──────────────────┐                               │
          │                  │                      architecture-compliance
          │                  │                               │
          │   architecture-analysis (context)                 ▼
          │                  │                    ┌─────────────────────┐
          │                  │                    │ D/03.7 Трансформация│
          │                  │                    │  → transformation-plan
          │                  │                    │  → transformation-executed
          │                  │                    │  → transformation-results
          │                  │                    └─────────┬───────────┘
          │                  │                               │
          │                  │                      transformation-results
          │                  │                               │
          ▼                  ▼                               ▼
     ┌──────────────────────────────────────────────────────────────┐
     │                    D/04.7 Методология                         │
     │  → methodology-developed → methodology-deployed              │
     │  → teams-supported → compliance-report → methodology-updates │
     └──────────────────────────────────────────────────────────────┘
                            │
                            ▼
                    methodology-updates
              (контроль для всех ТФ D-уровня)
```

---

## 8. Развёртывание

### Локально (тестирование)

```bash
python3 scripts/seed-tf-pipeline.py
hermes kanban list --status ready
hermes kanban claim <td-id>          # взять ТД в работу
hermes kanban complete <td-id>       # завершить ТД
hermes kanban stats                  # проверить auto-promote
```

### На сервере

```bash
scp scripts/seed-tf-pipeline.py ai.mais.agency:/home/hermes/
ssh ai.mais.agency "sudo -u hermes python3 /home/hermes/seed-tf-pipeline.py"
ssh ai.mais.agency "sudo -u hermes hermes kanban stats"
```

---

## 9. Архитектурные решения (верифицированы)

| Решение | Выбор | Статус |
|---------|-------|--------|
| **Pipeline model** | Sequential chain (TD1→TD2→...→TDN→TF) | ✅ Tested |
| **Parent-child** | `--parent` на предыдущий ТД | ✅ Tested |
| **First TD** | Без parent → ready | ✅ Tested |
| **Auto-promote** | `auto_promote_children: true` | ✅ Tested |
| **TF-summary** | linked после последнего ТД | ✅ Tested |
| **Skill loading** | `--skill` на каждый ТД | ✅ Tested |
| **Profile routing** | Per-TF из `execution.recommended_profile` | ✅ Tested (D-уровень) |
| **IDEF0 ICOM** | `execution.actions[].inputs/outputs` в body задачи | ✅ Tested (D-уровень) |
| **Cross-TF handoff** | output ID → input ID через metadata | ✅ Tested (D→D chain) |
| **Graphify IDEF0** | `idef0_input/output` узлы + `input_to/output_from` рёбра | ✅ Tested (340 nodes) |
| **HR-поля** | Убраны из YAML (educaton, experience, references) | ✅ Implemented |
| **Trigger** | Cron + Manual | 🔧 Config |

---

## 10. Roadmap

| Phase | Что делаем | Статус |
|-------|-----------|--------|
| **1** | Seeder script + базовая архитектура | ✅ Done |
| **2** | Тест на локальном Hermes (ОТФ-А, 4 ТФ, 24 ТД) | ✅ Done |
| **3** | IDEF0 execution schema (YAML + graphify + граф) | ✅ Done |
| **3a** | ОТФ-D: 4 ТФ, 22 ТД с IDEF0 ICOM | ✅ Done |
| **4** | TF executor skill (шаги LA с real LLM) | 🔜 Next |
| **5** | Monitor + Coverage auto-update | 🔜 Next |
| **6** | Масштабирование на другие стандарты | 📋 Backlog |

---

## 11. Связанные файлы

| Файл | Назначение |
|------|-----------|
| `docs/standards/07.007/otf-section-*.yaml` | Исходные данные ТФ/ТД + execution block |
| `docs/standards/07.007/meta.yaml` | Метаданные стандарта (code, title, activity) |
| `scripts/seed-tf-pipeline.py` | Seeder pipeline → kanban (читает execution) |
| `scripts/build-graph-from-yaml.py` | Graph builder (IDEF0 узлы + рёбра) |
| `docs/pipeline-architecture.md` | Данный документ |
| `docs/standards/07.007` | YAML-файлы профстандарта |
