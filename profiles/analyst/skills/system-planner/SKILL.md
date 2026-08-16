---
name: system-planner
description: >
  Разработка и усовершенствование системы управления (С/02.7). Читает
  оценку зрелости (C-01.7-maturity-assessment.yaml), labor-function-to-skill
  mapping и ТД С/02.7 профстандарта, генерирует roadmap развития:
  phases, milestones, skill development plan, dependencies,
  resource requirements.
version: 1.0.0
---

# system-planner

**Трудовое действие (С/02.7):** Разработка и усовершенствование системы процессного управления

**Принцип:** Roadmap строится ТОЛЬКО на данных оценки зрелости, mapping и ТД С/02.7. Никаких вымышленных сроков, ресурсов и зависимостей.

## ICOM

**Inputs:**
  - `outputs/07.007/block-C/C-01.7-maturity-assessment.yaml` — оценка зрелости (gaps, recommendations, scores)
  - `outputs/07.007/block-D/labor-function-to-skill-mapping.yaml` — ТФ → навык, gaps, summary
  - `docs/standards/07.007/otf-section-3.yaml` — блок C профстандарта (ТД С/02.7)

**Outputs:**
  - `outputs/07.007/block-C/C-02.7-architecture-roadmap.yaml` — roadmap развития архитектуры

**Controls:**
  - `07.007` — профстандарт
  - `new-skill-architecture-blueprint.md` — архитектурный шаблон

**Mechanisms:**
  - `system-planner` (навык)

## Rules (DO / DON'T)

**ВСЕГДА ДЕЛАЙ:**
- DO: проверяй существование файла перед `open()`. Используй `os.path.exists()`.
- DO: оборачивай `yaml.safe_load()` в `try/except`.
- DO: roadmap_phases, milestones и skill_development_plan строй ТОЛЬКО из gaps maturity-assessment.
- DO: timeframe используй фиксированный (1 месяц / 2 месяца / 3 месяца) из ТД «Разработка перспективного плана».
- DO: resource_requirements выводи из ТД «Формирование требований к ПО» и реальной инфраструктуры.

**КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО:**
- DON'T: выдумывать сроки, бюджеты, команды, инструменты.
- DON'T: придумывать зависимости между навыками — только из реальной последовательности pipeline (граф/спецификация/внедрение/аудит).
- DON'T: вызывать `subprocess.run(["hermes", ...])`.
- DON'T: использовать `input()` или интерактивный ввод.
- DON'T: писать за пределы `output_dir`.

## Thinking Process

1. Прочитаю `C-01.7-maturity-assessment.yaml` — получу gaps, maturity_scores, recommendations
2. Прочитаю `labor-function-to-skill-mapping.yaml` — получу summary, required_new_skills, coverage_status
3. Прочитаю `otf-section-3.yaml` — извлеку ТД С/02.7 для фаз и ресурсных требований
4. Сформирую roadmap_phases: 3 фазы (месяц 1-2-3), objectives из gaps maturity-assessment
5. Сформирую milestones: вехи по фазам из ТД «Разработка перспективного плана»
6. Построю skill_development_plan: недостающие навыки (С/03.7 missing + partially covered), priority из влияния
7. Построю dependencies: последовательность создания навыков (деплой зависит от дизайна и т.д.)
8. Сформирую resource_requirements из ТД «Формирование требований к ПО» + реальной инфраструктуры
9. Проверю: каждый объект привязан к реальному gap/ТД, никаких выдуманных данных
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
parent_tf = body.get("parent_tf", "LF-07.007-С/02.7")
tf_code = parent_tf.replace("LF-07.007-", "") if parent_tf else "С/02.7"

print(f"  TF: {tf_code}, LA: {la_id}")

current_skill_path = "profiles/analyst/skills/system-planner/SKILL.md"
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
maturity_data = read_file(os.path.join(
    ARCH_DIR, "outputs/07.007/block-C/C-01.7-maturity-assessment.yaml"))
mapping_data = read_file(os.path.join(
    ARCH_DIR, "outputs/07.007/block-D/labor-function-to-skill-mapping.yaml"))
otf3 = read_file(os.path.join(ARCH_DIR, "docs/standards/07.007/otf-section-3.yaml"))

maturity_body = maturity_data.get("body", {})
maturity_gaps = maturity_body.get("gaps", [])
maturity_scores = maturity_body.get("maturity_scores", [])
mappings = mapping_data.get("mappings", [])
summary = mapping_data.get("summary", {})

print(f"  Maturity gaps: {len(maturity_gaps)}, Mapping entries: {len(mappings)}")

# ТД С/02.7 из профстандарта
td_s027 = []
for lf in otf3.get("labor_functions", []):
    if lf.get("code") == "С/02.7":
        td_s027 = lf.get("трудовые_действия", [])
        break
if not td_s027:
    print("  [WARN] ТД С/02.7 не найдено в otf-section-3.yaml")

# ── roadmap_phases: 3 фазы из gaps ─────────────────────────────────

# Группируем gaps: missing (С/03.7) и partially (В/01.6-В/05.6, С/01.7, С/02.7, С/04.7)
missing_gaps = [g for g in maturity_gaps if g.get("type") == "missing_skill"]
partial_gaps = [g for g in maturity_gaps if g.get("type") == "partially_covered"]

phase_plan = [
    {
        "phase_id": "PH-01",
        "phase_name": "Закрытие missing-навыков",
        "timeframe": "1 месяц",
        "objectives": [f"Создать навык для {g['tf_code']} ({g['tf_name']})" for g in missing_gaps],
        "success_criteria": f"Все missing_skill ({len(missing_gaps)}) закрыты навыками",
    },
    {
        "phase_id": "PH-02",
        "phase_name": "Расширение partially-навыков блока B",
        "timeframe": "2 месяца",
        "objectives": [f"Повысить покрытие {g['tf_code']} ({g['tf_name']})" for g in partial_gaps if g.get("tf_code", "").startswith("В/")],
        "success_criteria": "ТФ блока B переведены из partially в covered",
    },
    {
        "phase_id": "PH-03",
        "phase_name": "Расширение partially-навыков блока C",
        "timeframe": "3 месяца",
        "objectives": [f"Повысить покрытие {g['tf_code']} ({g['tf_name']})" for g in partial_gaps if g.get("tf_code", "").startswith("С/")],
        "success_criteria": "ТФ блока C переведены из partially в covered",
    },
]

roadmap_phases = []
for p in phase_plan:
    if p["objectives"]:
        roadmap_phases.append(p)

print(f"  Roadmap phases: {len(roadmap_phases)}")

# ── milestones: из ТД «Разработка перспективного плана» ───────────

plan_td = next((t for t in td_s027 if "перспективного плана" in t), "")
milestones = []
for p in roadmap_phases:
    milestones.append({
        "milestone_id": f"MS-{len(milestones)+1:02d}",
        "phase_id": p["phase_id"],
        "milestone_name": f"Завершена фаза «{p['phase_name']}»",
        "criteria": p["success_criteria"],
        "source_td": plan_td,
    })

print(f"  Milestones: {len(milestones)}")

# ── skill_development_plan: недостающие навыки ─────────────────────

# Существующие навыки (skill_path) — чтобы не предлагать создание существующих
existing_skills = {e["skill_path"].split("/")[0] for e in mappings if e.get("skill_path")}

# Навыки для missing (из mapping required_new_skill)
skill_plan = []

# 1. missing_skill (С/03.7) — приоритет high
for g in missing_gaps:
    m_entry = next((e for e in mappings if e.get("tf_code") == g["tf_code"]), {})
    skill_plan.append({
        "skill_name": "implementation-lead",
        "tf_code": g["tf_code"],
        "tf_name": g.get("tf_name", ""),
        "priority": "high",
        "estimated_effort": "средний (1 навык, комплекс ТД)",
        "status": "to_create",
    })

# 2. partially_covered блока B — развитие существующих навыков, medium
for g in partial_gaps:
    if g.get("tf_code", "").startswith("В/"):
        m_entry = next((e for e in mappings if e.get("tf_code") == g["tf_code"]), {})
        skill_name = m_entry.get("skill_path", "").split("/")[0] if m_entry.get("skill_path") else ""
        skill_plan.append({
            "skill_name": skill_name or g["tf_code"],
            "tf_code": g["tf_code"],
            "tf_name": g.get("tf_name", ""),
            "priority": "medium",
            "estimated_effort": "низкий (расширение существующего навыка)",
            "status": "to_extend",
        })

# 3. partially_covered блока C — развитие существующих навыков, low
for g in partial_gaps:
    if g.get("tf_code", "").startswith("С/"):
        m_entry = next((e for e in mappings if e.get("tf_code") == g["tf_code"]), {})
        skill_name = m_entry.get("skill_path", "").split("/")[0] if m_entry.get("skill_path") else ""
        skill_plan.append({
            "skill_name": skill_name or g["tf_code"],
            "tf_code": g["tf_code"],
            "tf_name": g.get("tf_name", ""),
            "priority": "low",
            "estimated_effort": "низкий (расширение существующего навыка)",
            "status": "to_extend",
        })

print(f"  Skill development plan: {len(skill_plan)}")

# ── dependencies: последовательность создания навыков ─────────────

# Реальная последовательность pipeline: спецификация → деплой → аудит
dependencies = [
    {
        "dependency_id": "DEP-01",
        "from_skill": "crossfunction-designer",
        "to_skill": "crossfunction-deployer",
        "reason": "План внедрения (B-04.6) строится из спецификации (B-03.6) — designer должен существовать раньше deployer",
    },
    {
        "dependency_id": "DEP-02",
        "from_skill": "crossfunction-deployer",
        "to_skill": "crossfunction-auditor",
        "reason": "Аудит (B-05.6) проверяет артефакты плана внедрения (B-04.6) — deployer раньше auditor",
    },
    {
        "dependency_id": "DEP-03",
        "from_skill": "maturity-assessor",
        "to_skill": "system-planner",
        "reason": "Roadmap (С/02.7) строится из gaps оценки зрелости (С/01.7) — assessor раньше planner",
    },
    {
        "dependency_id": "DEP-04",
        "from_skill": "system-planner",
        "to_skill": "implementation-lead",
        "reason": "Внедрение системы управления (С/03.7) исполняет roadmap — planner раньше implementation-lead",
    },
]

print(f"  Dependencies: {len(dependencies)}")

# ── resource_requirements: из ТД «Формирование требований к ПО» ───

po_td = next((t for t in td_s027 if "Формирование требований" in t), "")
resource_requirements = [
    {
        "resource_id": "RES-01",
        "resource_type": "software",
        "requirement": (
            "Инструмент управления процессами для построения исполняемых "
            "кросс-функциональных процессов (BPMS / workflow engine)"
        ),
        "source_td": po_td,
    },
    {
        "resource_id": "RES-02",
        "resource_type": "software",
        "requirement": (
            "Граф знаний для моделей процессов (graphify) — существующий "
            "инструмент, расширение под блок C"
        ),
        "source_td": po_td,
    },
    {
        "resource_id": "RES-03",
        "resource_type": "infrastructure",
        "requirement": "Хранилище артефактов (outputs/07.007/) и реестр покрытия (labor-coverage-registry.yaml)",
        "source_td": po_td,
    },
]

print(f"  Resource requirements: {len(resource_requirements)}")

# ── data_gaps ──────────────────────────────────────────────────────

data_gaps = []
if not td_s027:
    data_gaps.append("ТД С/02.7 не найдено в otf-section-3.yaml")
if not roadmap_phases:
    data_gaps.append("Нет gaps в maturity-assessment — roadmap не из чего строить")
data_gaps.append("Конкретные бюджеты и сроки (дни/часы) не определены — фазы заданы как 1/2/3 месяца")

# ── Шаг 3: Валидация ───────────────────────────────────────────────

errors = []
if not roadmap_phases:
    errors.append("roadmap_phases пуст")
if not skill_plan:
    errors.append("skill_development_plan пуст")
for p in roadmap_phases:
    if not p["objectives"]:
        errors.append(f"phase {p['phase_id']}: objectives пусты")
for s in skill_plan:
    if s["priority"] not in ("high", "medium", "low"):
        errors.append(f"skill_plan: недопустимый priority {s['priority']}")

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
        "generated_by": "system-planner",
        "timestamp": os.popen("date -u +%Y-%m-%dT%H:%M:%SZ").read().strip(),
        "schema_ref": "architecture-roadmap-schema.yaml v1.0.0",
    },
    "body": {
        "roadmap_phases": roadmap_phases,
        "milestones": milestones,
        "skill_development_plan": skill_plan,
        "dependencies": dependencies,
        "resource_requirements": resource_requirements,
        "data_gaps": data_gaps,
    },
    "quality": {
        "schema_valid": schema_valid,
        "sources_read": [
            "outputs/07.007/block-C/C-01.7-maturity-assessment.yaml",
            "outputs/07.007/block-D/labor-function-to-skill-mapping.yaml",
            "docs/standards/07.007/otf-section-3.yaml",
        ],
        "warnings": [],
    },
}

write_ok = write_yaml(output_path, result)
if not write_ok:
    print("  [ERROR] failed to write roadmap")
    os._exit(1)

# ── Шаг 5: Отчёт ───────────────────────────────────────────────────

print(f"  Written: {output_path}")
print(f"  Schema valid: {schema_valid}")
```

## Схемы данных

```yaml
# architecture-roadmap-schema.yaml v1.0.0
meta:
  artifact: str            # C-02.7-architecture-roadmap
  tf: str                  # С/02.7
  la: str                  # la-001
  generated_by: str        # system-planner
  timestamp: str           # ISO-8601 UTC
  schema_ref: str

body:
  roadmap_phases:
    - phase_id: str        # PH-01..03
      phase_name: str
      timeframe: str       # 1 месяц / 2 месяца / 3 месяца
      objectives: list[str]   # из gaps maturity-assessment
      success_criteria: str
  milestones:
    - milestone_id: str    # MS-01
      phase_id: str
      milestone_name: str
      criteria: str
      source_td: str
  skill_development_plan:
    - skill_name: str
      tf_code: str
      tf_name: str
      priority: str        # high/medium/low
      estimated_effort: str
      status: str          # to_create | to_extend
  dependencies:
    - dependency_id: str   # DEP-01
      from_skill: str
      to_skill: str
      reason: str
  resource_requirements:
    - resource_id: str     # RES-01
      resource_type: str   # software | infrastructure
      requirement: str
      source_td: str
  data_gaps: list[str]

quality:
  schema_valid: bool
  sources_read: list[str]
  warnings: list[str]
```
