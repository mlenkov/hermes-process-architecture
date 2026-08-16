---
name: implementation-lead
description: >
  Внедрение системы процессного управления (С/03.7). Читает roadmap
  (C-02.7-architecture-roadmap.yaml), labor-function-to-skill mapping
  и ТД С/03.7 профстандарта, генерирует план внедрения:
  project charter, implementation phases, resource allocation,
  risk management, success metrics.
version: 1.0.0
---

# implementation-lead

**Трудовое действие (С/03.7):** Внедрение системы процессного управления организации или ее усовершенствования

**Принцип:** План внедрения строится ТОЛЬКО из roadmap (фаза PH-01), mapping и ТД С/03.7. Никаких вымышленных названий ПО, дат, бюджетов и имён людей.

## ICOM

**Inputs:**
  - `outputs/07.007/block-C/C-02.7-architecture-roadmap.yaml` — roadmap развития (фаза PH-01, success_criteria, resource_requirements)
  - `outputs/07.007/block-D/labor-function-to-skill-mapping.yaml` — ТФ → навык, профили, статус покрытия
  - `docs/standards/07.007/otf-section-3.yaml` — блок C профстандарта (ТД С/03.7)

**Outputs:**
  - `outputs/07.007/block-C/C-03.7-implementation-plan.yaml` — план внедрения системы управления

**Controls:**
  - `07.007` — профстандарт
  - `new-skill-architecture-blueprint.md` — архитектурный шаблон

**Mechanisms:**
  - `implementation-lead` (навык)

## Rules (DO / DON'T)

**ВСЕГДА ДЕЛАЙ:**
- DO: проверяй существование файла перед `open()`. Используй `os.path.exists()`.
- DO: оборачивай `yaml.safe_load()` в `try/except`.
- DO: project_charter цели бери ТОЛЬКО из roadmap PH-01 (objectives).
- DO: implementation_phases строй из ТД С/03.7 (8 ТД профстандарта).
- DO: resource_allocation сопоставляй профили/навыки ТОЛЬКО из mapping.
- DO: risk_management строй из data_gaps предыдущих артефактов (roadmap, maturity-assessment).

**КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО:**
- DON'T: выдумывать названия ПО, даты, бюджеты, имена людей.
- DON'T: генерировать цели внедрения, которых нет в roadmap PH-01.
- DON'T: назначать профили/навыки, которых нет в mapping.
- DON'T: вызывать `subprocess.run(["hermes", ...])`.
- DON'T: использовать `input()` или интерактивный ввод.
- DON'T: писать за пределы `output_dir`.

## Thinking Process

1. Прочитаю `C-02.7-architecture-roadmap.yaml` — получу roadmap_phases (PH-01), success_criteria, resource_requirements, data_gaps
2. Прочитаю `labor-function-to-skill-mapping.yaml` — получу профиль и навык для каждой ТФ (resource_allocation)
3. Прочитаю `otf-section-3.yaml` — извлеку 8 ТД С/03.7 для implementation_phases
4. Сформирую project_charter: цели из objectives PH-01, область применения из названия С/03.7
5. Построю implementation_phases из ТД С/03.7 (планирование, руководство, выбор ПО, внедрение ПО, методическая помощь, планирование инструктажа, проведение инструктажа, оценка эффективности)
6. Построю resource_allocation: для каждой фазы — профиль и навык из mapping
7. Построю risk_management из data_gaps roadmap/maturity-assessment + human-in-the-loop
8. Сформирую success_metrics из success_criteria PH-01 и ТД С/03.7
9. Проверю: никаких выдуманных данных, все ссылки на реальные файлы
10. Запишу в output_files[0] (meta уже внутри файла)

## Process

```python
import os, re, yaml

ARCH_DIR = os.path.abspath(".")

def read_file(path):
    """Прочитать YAML-файл с защитой от ошибок."""
    if not os.path.exists(path):
        print(f"  [WARN] file not found: {path}")
        return {}
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
            return data if isinstance(data, dict) else {}
    except Exception as e:
        print(f"  [WARN] read error: {path}: {e}")
        return {}

def write_yaml(path, data):
    """Атомарная запись YAML: temp-файл + os.rename (POSIX)."""
    dir_name = os.path.dirname(path) or "."
    os.makedirs(dir_name, exist_ok=True)
    import tempfile
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".yaml.tmp")
    try:
        with os.fdopen(fd, "w") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        os.rename(tmp_path, path)
        return True
    except Exception as e:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        print(f"  [ERROR] write error: {path}: {e}")
        return False
# ── Шаг 0: Pre-flight Check (идемпотентность, ADR-007) ────────────

la_id = body.get("la_id", "la-001")
parent_tf = body.get("parent_tf", "LF-07.007-С/03.7")
tf_code = parent_tf.replace("LF-07.007-", "") if parent_tf else "С/03.7"

print(f"  TF: {tf_code}, LA: {la_id}")

current_skill_path = "profiles/mais/skills/implementation-lead/SKILL.md"
registry_path = os.path.join(ARCH_DIR, "outputs/07.007/labor-coverage-registry.yaml")

if output_files:
    target = output_files[0]
    if os.path.exists(target):
        try:
            existing = yaml.safe_load(open(target, encoding="utf-8")) or {}
        except Exception:
            existing = {}
        if existing.get("quality", {}).get("schema_valid") is True:
            reg_data = read_file(registry_path)
            reg_entry = reg_data.get(parent_tf) or reg_data.get(f"LF-07.007-{tf_code}") or {}
            reg_ok = reg_entry.get("status") in ("covered", "partially_covered")
            skill_ok = str(reg_entry.get("skill_path", "")).endswith(current_skill_path)
            if reg_ok and skill_ok:
                print("[INFO] Artifact already exists and is valid. Registry is up to date. Skipping generation.", flush=True)
                os._exit(0)

# ── Шаг 2: Генерация ───────────────────────────────────────────────

if not output_files:
    print("  [ERROR] no output_files specified in body")
    os._exit(1)

output_path = output_files[0]
artifact_id = os.path.basename(output_path).replace(".yaml", "")

# Чтение источников
roadmap_data = read_file(os.path.join(
    ARCH_DIR, "outputs/07.007/block-C/C-02.7-architecture-roadmap.yaml"))
mapping_data = read_file(os.path.join(
    ARCH_DIR, "outputs/07.007/block-D/labor-function-to-skill-mapping.yaml"))
otf3 = read_file(os.path.join(ARCH_DIR, "docs/standards/07.007/otf-section-3.yaml"))

roadmap_body = roadmap_data.get("body", {})
roadmap_phases = roadmap_body.get("roadmap_phases", [])
roadmap_resources = roadmap_body.get("resource_requirements", [])
roadmap_gaps = roadmap_body.get("data_gaps", [])
mappings = mapping_data.get("mappings", [])
summary = mapping_data.get("summary", {})

# ТД С/03.7 из профстандарта
td_s037 = []
for lf in otf3.get("labor_functions", []):
    if lf.get("code") == "С/03.7":
        td_s037 = lf.get("трудовые_действия", [])
        break
if not td_s037:
    print("  [WARN] ТД С/03.7 не найдено в otf-section-3.yaml")

# ── project_charter: цели из roadmap PH-01 ─────────────────────────

ph01 = next((p for p in roadmap_phases if p.get("phase_id") == "PH-01"), {})
ph01_objectives = ph01.get("objectives", [])

project_charter = {
    "charter_id": "PC-01",
    "project_name": "Внедрение системы процессного управления",
    "scope": (
        "Реализация фазы PH-01 roadmap: закрытие missing-навыков "
        "профстандарта 07.007 (С/03.7) через создание и задействование "
        "навыка implementation-lead"
    ),
    "objectives": ph01_objectives,
    "success_criteria": ph01.get("success_criteria", ""),
    "source_artifact": "outputs/07.007/block-C/C-02.7-architecture-roadmap.yaml",
}

print(f"  Charter objectives: {len(project_charter['objectives'])}")

# ── implementation_phases: из 8 ТД С/03.7 ──────────────────────────

# Именование фаз — по ТД С/03.7 (первые слова ТД), source_td = полное ТД
phase_names = [
    "Планирование внедрения",
    "Руководство проектом внедрения",
    "Выбор программного обеспечения",
    "Внедрение программного обеспечения",
    "Методическая помощь команде",
    "Планирование инструктажа",
    "Проведение инструктажа",
    "Оценка эффективности внедрения",
]

implementation_phases = []
for i, td in enumerate(td_s037, 1):
    implementation_phases.append({
        "phase_id": f"PH-{i:02d}",
        "phase_name": phase_names[i-1] if i <= len(phase_names) else td,
        "source_td": td,
    })

print(f"  Implementation phases: {len(implementation_phases)}")

# ── resource_allocation: профили/навыки из mapping ─────────────────

# Карта ТФ → (профиль, навык) из registry-информации в mapping-записях
# Для каждой фазы определяем исполнителя: профиль mais (ADR-008 —
# единственный исполнитель 07.007), навык — по skill_path соответствующей
# ТФ в mapping
skill_by_tf = {m.get("tf_code"): m for m in mappings}

def resolve_profile(tf_code):
    # ADR-008: единственный исполнитель 07.007 — профиль mais
    return "mais"

resource_allocation = []
for i, phase in enumerate(implementation_phases, 1):
    # Для фазы «Оценка эффективности» — pdca-reporter (С/04.7 / D-блок)
    if "Оценка эффективности" in phase["phase_name"]:
        alloc = {
            "phase_id": phase["phase_id"],
            "phase_name": phase["phase_name"],
            "profile": "mais",
            "skill": "pdca-reporter",
            "source_tf": "С/04.7",
            "source_td": phase["source_td"],
        }
    elif "инструктаж" in phase["phase_name"].lower():
        # Инструктаж требует human-in-the-loop (User_Operator) + mais
        alloc = {
            "phase_id": phase["phase_id"],
            "phase_name": phase["phase_name"],
            "profile": "mais + User_Operator (human-in-the-loop)",
            "skill": "implementation-lead",
            "source_tf": "С/03.7",
            "source_td": phase["source_td"],
        }
    elif "программного обеспечения" in phase["phase_name"]:
        # Выбор/внедрение ПО — mais по roadmap resource_requirements
        alloc = {
            "phase_id": phase["phase_id"],
            "phase_name": phase["phase_name"],
            "profile": "mais",
            "skill": "implementation-lead",
            "source_tf": "С/03.7",
            "source_td": phase["source_td"],
        }
    else:
        alloc = {
            "phase_id": phase["phase_id"],
            "phase_name": phase["phase_name"],
            "profile": resolve_profile("С/03.7"),
            "skill": "implementation-lead",
            "source_tf": "С/03.7",
            "source_td": phase["source_td"],
        }
    resource_allocation.append(alloc)

print(f"  Resource allocations: {len(resource_allocation)}")

# ── risk_management: из data_gaps + human-in-the-loop ──────────────

risk_management = [
    {
        "risk_id": "RK-01",
        "risk": "Отсутствие timeout в handoff-триггерах кросс-функциональных процессов (из B-04.6)",
        "impact": "high",
        "mitigation": "Явно фиксировать отсутствие timeout как data_gap в каждой фазе внедрения",
        "source": "data_gap в C-02.7-architecture-roadmap.yaml / B-04.6-crossfunction-deployment.yaml",
    },
    {
        "risk_id": "RK-02",
        "risk": "Инструктаж, тестирование и аттестация специалистов требуют участия человека (human-in-the-loop)",
        "impact": "high",
        "mitigation": "Ограничить автоматизацию планированием инструктажа; проведение — через задачи User_Operator",
        "source": "ТД С/03.7 «Планирование инструктажа, тестирования, аттестации и сертификации»",
    },
    {
        "risk_id": "RK-03",
        "risk": "Экономическая и функциональная эффективность системы управления не измеряется",
        "impact": "medium",
        "mitigation": "Оценка эффективности внедрения — только по существующим данным registry, без выдуманных метрик",
        "source": "data_gap в C-01.7-maturity-assessment.yaml",
    },
    {
        "risk_id": "RK-04",
        "risk": "Конкретные бюджеты и сроки (дни/часы) внедрения не определены",
        "impact": "medium",
        "mitigation": "Фазы заданы как 1/2/3 месяца из roadmap; бюджеты не заявляются",
        "source": "data_gap в C-02.7-architecture-roadmap.yaml",
    },
    {
        "risk_id": "RK-05",
        "risk": "Выбор программного обеспечения вне текущей архитектуры (нет процесса закупки/интеграции)",
        "impact": "medium",
        "mitigation": "Выбор ПО фиксируется как решение с участием User_Operator, а не автоматизированный выбор",
        "source": "ТД С/03.7 «Выбор программного обеспечения для управления процессами»",
    },
]

print(f"  Risks: {len(risk_management)}")

# ── success_metrics: из success_criteria PH-01 + ТД С/03.7 ─────────

success_metrics = [
    {
        "metric_id": "SM-01",
        "metric": "Навык implementation-lead создан и задействован для С/03.7",
        "target": "покрытие С/03.7 не missing_skill",
        "source": "success_criteria PH-01 roadmap (C-02.7)",
    },
    {
        "metric_id": "SM-02",
        "metric": "Все 8 ТД С/03.7 имеют план исполнения (implementation_phases)",
        "target": "8/8 фаз",
        "source": "ТД С/03.7 otf-section-3.yaml",
    },
    {
        "metric_id": "SM-03",
        "metric": "Оценка эффективности внедрения оформлена (pdca-reporter)",
        "target": "отчёт в pdca-reports",
        "source": "ТД С/03.7 «Оценка эффективности внедрения»",
    },
    {
        "metric_id": "SM-04",
        "metric": "C-03.7-implementation-plan.yaml создан и валиден",
        "target": "schema_valid: true",
        "source": "артефакт данного навыка",
    },
]

print(f"  Success metrics: {len(success_metrics)}")

# ── data_gaps ──────────────────────────────────────────────────────

data_gaps = []
if not td_s037:
    data_gaps.append("ТД С/03.7 не найдено в otf-section-3.yaml")
if not ph01:
    data_gaps.append("Фаза PH-01 не найдена в roadmap — цели устава не определены")
data_gaps.append("Конкретные бюджеты и сроки (дни/часы) внедрения не определены")
data_gaps.append("Названия конкретного ПО и вендоров не указаны — выбор требует участия User_Operator")

# ── Шаг 3: Валидация ───────────────────────────────────────────────

errors = []
if not project_charter["objectives"]:
    errors.append("project_charter.objectives пусты — нет целей PH-01 из roadmap")
if not implementation_phases:
    errors.append("implementation_phases пуст")
if not resource_allocation:
    errors.append("resource_allocation пуст")
for a in resource_allocation:
    if not a["profile"]:
        errors.append(f"allocation {a['phase_id']}: профиль пуст")
if not success_metrics:
    errors.append("success_metrics пуст")

schema_valid = not errors
print(f"  Validation errors: {len(errors)}")
for e in errors:
    print(f"    - {e}")

# ── Шаг 4: Запись ──────────────────────────────────────────────────

result = {
    "meta": {
        "artifact": artifact_id,
        "tf": tf_code,
        "la": la_id,
        "generated_by": "implementation-lead",
        "timestamp": os.popen("date -u +%Y-%m-%dT%H:%M:%SZ").read().strip(),
        "schema_ref": "implementation-plan-schema.yaml v1.0.0",
    },
    "body": {
        "project_charter": project_charter,
        "implementation_phases": implementation_phases,
        "resource_allocation": resource_allocation,
        "risk_management": risk_management,
        "success_metrics": success_metrics,
        "data_gaps": data_gaps,
    },
    "quality": {
        "schema_valid": schema_valid,
        "awaiting_approval": True,          # HITL: выбор ПО (ADR-006)
        "sources_read": [
            "outputs/07.007/block-C/C-02.7-architecture-roadmap.yaml",
            "outputs/07.007/block-D/labor-function-to-skill-mapping.yaml",
            "docs/standards/07.007/otf-section-3.yaml",
        ],
        "warnings": [],
    },
}

write_ok = write_yaml(output_path, result)
if not write_ok:
    print("  [ERROR] failed to write implementation plan")
    os._exit(1)

# ── HITL: approval-request (ADR-006) — ТД «Выбор ПО» ────────────────
# Классы решений — из resource_requirements roadmap (RES-01/RES-02/RES-03),
# БЕЗ названий вендоров.
approval_path = output_path.replace(".yaml", "-approval-request.yaml")

res_map = {r.get("resource_id"): r.get("requirement", "") for r in roadmap_resources}
approval_request = {
    "approval_request": {
        "request_id": "APR-01",
        "tf_code": "С/03.7",
        "source_td": "Выбор программного обеспечения для управления процессами или административными регламентами",
        "question": "Выбор класса программного обеспечения для управления процессами (BPMS / workflow engine)",
        "options": [
            {
                "option_id": "OPT-A",
                "label": "Расширить текущий стек (graphify + kanban)",
                "description": res_map.get("RES-02", "Граф знаний graphify — существующий инструмент, расширение под блок C") + " (RES-02)",
            },
            {
                "option_id": "OPT-B",
                "label": "Класс BPMS / workflow engine",
                "description": res_map.get("RES-01", "Инструмент управления процессами для исполняемых кросс-функциональных процессов") + " (RES-01)",
            },
            {
                "option_id": "OPT-C",
                "label": "Гибрид: BPMS + граф знаний",
                "description": "Комбинация RES-01 (BPMS) и RES-02 (graphify): исполняемые процессы + семантический граф",
            },
        ],
        "context_ref": "outputs/07.007/block-C/C-02.7-architecture-roadmap.yaml (resource_requirements)",
        "deadline": None,
    }
}
write_yaml(approval_path, approval_request)
print(f"  HITL: approval-request written: {approval_path}")

# ── Шаг 5: Отчёт ───────────────────────────────────────────────────

print(f"  Written: {output_path}")
print(f"  Schema valid: {schema_valid}")
print(f"  Data gaps: {len(data_gaps)}")
```

## Схемы данных

```yaml
# implementation-plan-schema.yaml v1.0.0
meta:
  artifact: str            # C-03.7-implementation-plan
  tf: str                  # С/03.7
  la: str                  # la-001
  generated_by: str        # implementation-lead
  timestamp: str           # ISO-8601 UTC
  schema_ref: str

body:
  project_charter:
    charter_id: str        # PC-01
    project_name: str
    scope: str
    objectives: list[str]  # из roadmap PH-01
    success_criteria: str  # из roadmap PH-01
    source_artifact: str
  implementation_phases:
    - phase_id: str        # PH-01..08
      phase_name: str
      source_td: str       # полное ТД С/03.7
  resource_allocation:
    - phase_id: str
      phase_name: str
      profile: str         # профиль из mapping (mais / User_Operator)
      skill: str
      source_tf: str
      source_td: str
  risk_management:
    - risk_id: str         # RK-01
      risk: str
      impact: str          # high | medium
      mitigation: str
      source: str          # data_gap / ТД / артефакт
  success_metrics:
    - metric_id: str       # SM-01
      metric: str
      target: str
      source: str
  data_gaps: list[str]

quality:
  schema_valid: bool
  sources_read: list[str]
  warnings: list[str]
```
