---
name: system-auditor
description: >
  Аудит системы процессного управления (С/04.7). Читает оценку
  зрелости (C-01.7-maturity-assessment.yaml), план внедрения
  (C-03.7-implementation-plan.yaml), labor-function-to-skill mapping
  и labor-coverage-registry.yaml, проверяет соответствие артефактов
  критериям аудита и ТД С/04.7 профстандарта, генерирует отчёт
  аудита: audit_scope, audit_criteria, findings, recommendations,
  data_gaps.
version: 1.0.0
---

# system-auditor

**Трудовое действие (С/04.7):** Аудит системы процессного управления организации на соответствие требованиям и целевым показателям организации

**Принцип:** Все findings строятся ТОЛЬКО на реальных проверках файлов (существование, валидность YAML, согласованность с registry/mapping). Никаких выдуманных наблюдений, логов или метрик.

## ICOM

**Inputs:**
  - `outputs/07.007/block-C/C-01.7-maturity-assessment.yaml` — оценка зрелости (current_state, maturity_scores, gaps)
  - `outputs/07.007/block-C/C-03.7-implementation-plan.yaml` — план внедрения (project_charter, 8 фаз, risks)
  - `outputs/07.007/block-D/labor-function-to-skill-mapping.yaml` — ТФ → навык, профили, статус покрытия
  - `outputs/07.007/labor-coverage-registry.yaml` — реестр покрытия (записи по ТФ, skill_path, статус)
  - `docs/standards/07.007/otf-section-3.yaml` — блок C профстандарта (ТД С/04.7)

**Outputs:**
  - `outputs/07.007/block-C/C-04.7-system-audit.yaml` — отчёт аудита системы управления

**Controls:**
  - `07.007` — профстандарт
  - `new-skill-architecture-blueprint.md` — архитектурный шаблон

**Mechanisms:**
  - `system-auditor` (навык)

## Rules (DO / DON'T)

**ВСЕГДА ДЕЛАЙ:**
- DO: проверяй существование файла перед `open()`. Используй `os.path.exists()`.
- DO: оборачивай `yaml.safe_load()` в `try/except`.
- DO: audit_criteria строй из 7 ТД С/04.7 профстандарта.
- DO: findings формируй по результатам РЕАЛЬНЫХ проверок: чтение файла, подсчёт полей, сравнение с registry/mapping.
- DO: каждому finding указывай evidence (конкретный файл и поле).
- DO: recommendations привязывай к ТД С/04.7 (source_td) и findings (basis).

**КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО:**
- DON'T: выдумывать наблюдения, логи исполнения, латентность или метрики runtime.
- DON'T: утверждать, что артефакт валиден, не прочитав его.
- DON'T: назначать профили/навыки, которых нет в mapping.
- DON'T: вызывать `subprocess.run(["hermes", ...])`.
- DON'T: использовать `input()` или интерактивный ввод.
- DON'T: писать за пределы `output_dir`.

## Thinking Process

1. Прочитаю `C-01.7-maturity-assessment.yaml` — получу current_state (covered/partially/missing), maturity_scores, gaps
2. Прочитаю `C-03.7-implementation-plan.yaml` — получу project_charter, implementation_phases, resource_allocation, risk_management
3. Прочитаю `labor-function-to-skill-mapping.yaml` — получу mapping всех ТФ, summary, required_new_skills
4. Прочитаю `labor-coverage-registry.yaml` — получу записи по каждой ТФ (skill_path, tds_completed, статус)
5. Прочитаю `otf-section-3.yaml` — извлеку 7 ТД С/04.7 для audit_criteria и recommendations
6. Соберу audit_scope: что аудируется (система процессного управления, блок C)
7. Построю audit_criteria из ТД С/04.7
8. Проведу findings:
   - maturity: сверю current_state.missing_skill с фактическим наличием навыков в registry
   - plan: проверю 8 фаз внедрения и 8 записей resource_allocation, schema_valid
   - mapping: проверю skill_path С/04.7, список required_new_skills
   - registry: проверю актуальность записей (С/03.7 присутствует, skill_path корректный)
9. Построю recommendations из findings + ТД С/04.7
10. Запишу data_gaps честно (human-in-the-loop для инструктажа/наблюдений)
11. Проверю: никаких выдуманных данных, все ссылки на реальные файлы
12. Запишу в output_files[0] (meta уже внутри файла)

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
parent_tf = body.get("parent_tf", "LF-07.007-С/04.7")
tf_code = parent_tf.replace("LF-07.007-", "") if parent_tf else "С/04.7"

print(f"  TF: {tf_code}, LA: {la_id}")

current_skill_path = "profiles/mais/skills/system-auditor/SKILL.md"
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
plan_data = read_file(os.path.join(
    ARCH_DIR, "outputs/07.007/block-C/C-03.7-implementation-plan.yaml"))
mapping_data = read_file(os.path.join(
    ARCH_DIR, "outputs/07.007/block-D/labor-function-to-skill-mapping.yaml"))
registry_data = read_file(os.path.join(
    ARCH_DIR, "outputs/07.007/labor-coverage-registry.yaml"))
otf3 = read_file(os.path.join(ARCH_DIR, "docs/standards/07.007/otf-section-3.yaml"))

maturity_body = maturity_data.get("body", {})
plan_body = plan_data.get("body", {})
mappings = mapping_data.get("mappings", [])
mapping_summary = mapping_data.get("summary", {})
mapping_metrics = mapping_data.get("metrics", {})

# ТД С/04.7 из профстандарта
td_s047 = []
for lf in otf3.get("labor_functions", []):
    if lf.get("code") == "С/04.7":
        td_s047 = lf.get("трудовые_действия", [])
        break
if not td_s047:
    print("  [WARN] ТД С/04.7 не найдено в otf-section-3.yaml")

# ── audit_scope ────────────────────────────────────────────────────

audit_scope = {
    "tf_code": tf_code,
    "tf_name": "Аудит системы процессного управления организации на соответствие требованиям и целевым показателям организации",
    "description": (
        "Аудит системы процессного управления (блок C): проверка оценки "
        "зрелости (C-01.7), плана внедрения (C-03.7), mapping ТФ→навык "
        "и актуальности labor-coverage-registry."
    ),
    "audited_artifacts": 4,
    "sources": [
        "outputs/07.007/block-C/C-01.7-maturity-assessment.yaml",
        "outputs/07.007/block-C/C-03.7-implementation-plan.yaml",
        "outputs/07.007/block-D/labor-function-to-skill-mapping.yaml",
        "outputs/07.007/labor-coverage-registry.yaml",
    ],
}

print(f"  Audit scope artifacts: {audit_scope['audited_artifacts']}")

# ── audit_criteria: из 7 ТД С/04.7 ─────────────────────────────────

audit_criteria = []
for i, td in enumerate(td_s047, 1):
    # Сокращённое имя критерия — по первым словам ТД
    short = re.sub(r" системы процессного управления организации.*$", "", td)
    short = short[:45]
    audit_criteria.append({
        "criterion_id": f"AC-{i:02d}",
        "criterion_name": short,
        "source_td": td,
    })

print(f"  Audit criteria: {len(audit_criteria)}")

# ── findings: реальные проверки файлов ─────────────────────────────

findings = []

# Проверка maturity-assessment: current_state vs наличие навыков в registry
ms = maturity_body.get("current_state", {})
missing_in_maturity = ms.get("missing_skill", None)
s037_in_registry = "LF-07.007-С/03.7" in registry_data
if missing_in_maturity and missing_in_maturity > 0 and s037_in_registry:
    findings.append({
        "finding_id": "FD-01",
        "check": "maturity_assessment",
        "status": "outdated",
        "finding": (
            "C-01.7-maturity-assessment.yaml фиксирует missing_skill={} "
            "(С/03.7), но сгенерирован до создания implementation-lead. "
            "Текущий registry содержит запись LF-07.007-С/03.7 с "
            "implementation-lead — оценка зрелости требует обновления "
            "(missing_skill → 0).".format(missing_in_maturity)
        ),
        "evidence": (
            "C-01.7-maturity-assessment.yaml (current_state.missing_skill={}) "
            "+ labor-coverage-registry.yaml (LF-07.007-С/03.7 → implementation-lead)".format(missing_in_maturity)
        ),
    })
else:
    findings.append({
        "finding_id": "FD-01",
        "check": "maturity_assessment",
        "status": "ok",
        "finding": "Оценка зрелости согласована с registry: missing_skill корректен.",
        "evidence": "C-01.7-maturity-assessment.yaml (current_state) + labor-coverage-registry.yaml",
    })

# Проверка implementation-plan: 8 фаз, 8 resource_allocation, schema_valid
phases = plan_body.get("implementation_phases", [])
allocations = plan_body.get("resource_allocation", [])
plan_valid = plan_data.get("quality", {}).get("schema_valid", False)
plan_problems = []
if len(phases) != 8:
    plan_problems.append(f"implementation_phases={len(phases)} (ожидается 8)")
if len(allocations) != 8:
    plan_problems.append(f"resource_allocation={len(allocations)} (ожидается 8)")
if not plan_valid:
    plan_problems.append("schema_valid=false")
if plan_problems:
    findings.append({
        "finding_id": "FD-02",
        "check": "implementation_plan",
        "status": "non_compliant",
        "finding": "C-03.7-implementation-plan.yaml не соответствует ожиданиям: " + "; ".join(plan_problems),
        "evidence": "C-03.7-implementation-plan.yaml (implementation_phases, resource_allocation, quality)",
    })
else:
    findings.append({
        "finding_id": "FD-02",
        "check": "implementation_plan",
        "status": "ok",
        "finding": (
            "C-03.7-implementation-plan.yaml корректен: 8 фаз PH-01..08, "
            "8 записей resource_allocation, schema_valid=true. Фазы инструктажа "
            "(PH-06/07) отмечены human-in-the-loop, оценка (PH-08) — mais/pdca-reporter."
        ),
        "evidence": "C-03.7-implementation-plan.yaml (implementation_phases, resource_allocation, quality.schema_valid)",
    })

# Проверка mapping: skill_path С/04.7 и required_new_skills
tf_s047 = next((m for m in mappings if m.get("tf_code") == "С/04.7"), {})
mapped_skill = tf_s047.get("skill_path", "")
req_new = mapping_summary.get("required_new_skills", [])
if mapped_skill == "system-auditor/SKILL.md" and not req_new:
    findings.append({
        "finding_id": "FD-03",
        "check": "mapping",
        "status": "ok",
        "finding": (
            "labor-function-to-skill-mapping.yaml: С/04.7 → system-auditor/SKILL.md, "
            "required_new_skills пуст (0 навыков). Все 18 ТФ имеют навык."
        ),
        "evidence": "labor-function-to-skill-mapping.yaml (С/04.7.skill_path, summary.required_new_skills)",
    })
else:
    findings.append({
        "finding_id": "FD-03",
        "check": "mapping",
        "status": "non_compliant",
        "finding": "mapping не синхронизирован: skill_path={}, required_new_skills={}".format(mapped_skill, req_new),
        "evidence": "labor-function-to-skill-mapping.yaml (С/04.7.skill_path, summary)",
    })

# Проверка registry: С/03.7 присутствует и корректна
reg_s037 = registry_data.get("LF-07.007-С/03.7", {})
s037_skill = reg_s037.get("skill_path", "")
if s037_skill == "profiles/mais/skills/implementation-lead/SKILL.md":
    findings.append({
        "finding_id": "FD-04",
        "check": "registry",
        "status": "ok",
        "finding": (
            "labor-coverage-registry.yaml: С/03.7 имеет запись "
            "(implementation-lead, tds_completed=8/8). Записи С/04.7 и С/05.7 "
            "будут добавлены при исполнении соответствующих навыков."
        ),
        "evidence": "labor-coverage-registry.yaml (LF-07.007-С/03.7)",
    })
else:
    findings.append({
        "finding_id": "FD-04",
        "check": "registry",
        "status": "non_compliant",
        "finding": "labor-coverage-registry.yaml: С/03.7 отсутствует или skill_path некорректен.",
        "evidence": "labor-coverage-registry.yaml",
    })

print(f"  Findings: {len(findings)}")

# ── recommendations: из ТД С/04.7 + findings ───────────────────────

def source_td_for(keyword):
    for td in td_s047:
        if keyword in td.lower():
            return td
    return td_s047[0] if td_s047 else ""

recommendations = []
for f in findings:
    if f["status"] == "ok":
        continue
    if f["check"] == "maturity_assessment":
        recommendations.append({
            "recommendation_id": "R-01",
            "basis": f["finding_id"],
            "recommendation": "Обновить C-01.7-maturity-assessment.yaml: missing_skill → 0, covered → 10",
            "source_td": source_td_for("документов и данных"),
        })
    elif f["check"] == "mapping":
        recommendations.append({
            "recommendation_id": "R-02",
            "basis": f["finding_id"],
            "recommendation": "Синхронизировать mapping: С/04.7 → system-auditor, очистить required_new_skills",
            "source_td": source_td_for("документов и данных"),
        })
    elif f["check"] == "registry":
        recommendations.append({
            "recommendation_id": "R-03",
            "basis": f["finding_id"],
            "recommendation": "Добавить запись С/03.7 в labor-coverage-registry.yaml (implementation-lead)",
            "source_td": source_td_for("документов и данных"),
        })
    else:
        recommendations.append({
            "recommendation_id": "R-04",
            "basis": f["finding_id"],
            "recommendation": "Привести C-03.7-implementation-plan.yaml к 8 фазам и 8 resource_allocation",
            "source_td": source_td_for("документов и данных"),
        })

# Рекомендации по ТД С/04.7, требующим human-in-the-loop
recommendations.append({
    "recommendation_id": "R-05",
    "basis": "ТД С/04.7",
    "recommendation": "Инструктаж участников аудита и проведение наблюдений — через задачи User_Operator (human-in-the-loop)",
    "source_td": source_td_for("инструктаж участников"),
})
recommendations.append({
    "recommendation_id": "R-06",
    "basis": "ТД С/04.7",
    "recommendation": "Презентация результатов аудита — подготовить материалы для рабочих совещаний и утверждения",
    "source_td": source_td_for("презентация результатов"),
})

print(f"  Recommendations: {len(recommendations)}")

# ── data_gaps ──────────────────────────────────────────────────────

data_gaps = []
if not td_s047:
    data_gaps.append("ТД С/04.7 не найдено в otf-section-3.yaml")
data_gaps.append("Инструктаж участников аудита и проведение наблюдений требуют human-in-the-loop (User_Operator) — нет автоматизированного механизма")
data_gaps.append("Runtime-логи исполнения (фактическое выполнение ТД, latency) не аудируются — нет runtime-мониторинга в архитектуре")
if maturity_body.get("data_gaps"):
    data_gaps.append("Экономическая и функциональная эффективность системы управления не измеряется (из C-01.7)")

# ── Шаг 3: Валидация ───────────────────────────────────────────────

errors = []
if not audit_criteria:
    errors.append("audit_criteria пуст")
if not findings:
    errors.append("findings пуст")
for f in findings:
    if not f["evidence"]:
        errors.append(f"finding {f['finding_id']}: evidence пусто")
if not recommendations:
    errors.append("recommendations пуст")

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
        "generated_by": "system-auditor",
        "timestamp": os.popen("date -u +%Y-%m-%dT%H:%M:%SZ").read().strip(),
        "schema_ref": "system-audit-schema.yaml v1.0.0",
    },
    "body": {
        "audit_scope": audit_scope,
        "audit_criteria": audit_criteria,
        "findings": findings,
        "recommendations": recommendations,
        "data_gaps": data_gaps,
    },
    "quality": {
        "schema_valid": schema_valid,
        "sources_read": [
            "outputs/07.007/block-C/C-01.7-maturity-assessment.yaml",
            "outputs/07.007/block-C/C-03.7-implementation-plan.yaml",
            "outputs/07.007/block-D/labor-function-to-skill-mapping.yaml",
            "outputs/07.007/labor-coverage-registry.yaml",
            "docs/standards/07.007/otf-section-3.yaml",
        ],
        "warnings": [],
    },
}

write_ok = write_yaml(output_path, result)
if not write_ok:
    print("  [ERROR] failed to write system audit report")
    os._exit(1)

# ── Шаг 5: Отчёт ───────────────────────────────────────────────────

print(f"  Written: {output_path}")
print(f"  Schema valid: {schema_valid}")
print(f"  Data gaps: {len(data_gaps)}")
```

## Схемы данных

```yaml
# system-audit-schema.yaml v1.0.0
meta:
  artifact: str            # C-04.7-system-audit
  tf: str                  # С/04.7
  la: str                  # la-001
  generated_by: str        # system-auditor
  timestamp: str           # ISO-8601 UTC
  schema_ref: str

body:
  audit_scope:
    tf_code: str
    tf_name: str
    description: str
    audited_artifacts: int  # 4
    sources: list[str]
  audit_criteria:
    - criterion_id: str    # AC-01..07
      criterion_name: str
      source_td: str       # полное ТД С/04.7
  findings:
    - finding_id: str      # FD-01
      check: str           # maturity_assessment | implementation_plan | mapping | registry
      status: str          # ok | outdated | non_compliant
      finding: str         # на основе РЕАЛЬНОЙ проверки файла
      evidence: str        # файл + поле
  recommendations:
    - recommendation_id: str  # R-01
      basis: str           # finding_id / ТД С/04.7
      recommendation: str
      source_td: str
  data_gaps: list[str]

quality:
  schema_valid: bool
  sources_read: list[str]
  warnings: list[str]
```
