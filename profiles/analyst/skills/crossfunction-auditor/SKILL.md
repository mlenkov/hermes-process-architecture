---
name: crossfunction-auditor
description: >
  Аудит деятельности в рамках кросс-функционального процесса (В/05.6).
  Читает план внедрения (B-04.6-crossfunction-deployment.yaml),
  labour-function-to-skill mapping и ТД В/05.6 профстандарта, проверяет
  файловую систему (os.path.exists + валидность YAML) для каждой
  handoff-точки и генерирует отчёт аудита с recommendations.
version: 1.0.0
---

# crossfunction-auditor

**Трудовое действие (В/05.6):** Аудит деятельности в рамках кросс-функционального процесса

**Принцип:** Все findings основаны ТОЛЬКО на реальных проверках файлов (существование, валидность YAML, задан ли timeout). Никаких выдуманных задержек, latency или логов исполнения.

## ICOM

**Inputs:**
  - `outputs/07.007/block-B/B-04.6-crossfunction-deployment.yaml` — план внедрения (handoff_triggers, kanban_tasks)
  - `outputs/07.007/block-D/labor-function-to-skill-mapping.yaml` — ТФ → навык, статус покрытия
  - `docs/standards/07.007/otf-section-2.yaml` — блок B профстандарта (ТД В/05.6)

**Outputs:**
  - `outputs/07.007/block-B/B-05.6-crossfunction-audit.yaml` — отчёт аудита кросс-функциональных handoff-точек

**Controls:**
  - `07.007` — профстандарт
  - `new-skill-architecture-blueprint.md` — архитектурный шаблон

**Mechanisms:**
  - `crossfunction-auditor` (навык)

## Rules (DO / DON'T)

**ВСЕГДА ДЕЛАЙ:**
- DO: проверяй существование файла через `os.path.exists()` — это единственный источник `artifact_exists`.
- DO: при существовании файла проверяй `quality.schema_valid` внутри YAML — это `artifact_valid`.
- DO: оборачивай `yaml.safe_load()` в `try/except` — битый YAML = artifact_valid false.
- DO: `timeout_defined` бери из data_gap триггера B-04.6 (timeout задан ↔ data_gap отсутствует).
- DO: извлекай рекомендации из ТД В/05.6 и реальных findings.

**КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО:**
- DON'T: выдумывать latency, задержки, логи исполнения. Их нет в источниках.
- DON'T: генерировать вымышленные findings — только результат реальных проверок.
- DON'T: вызывать `subprocess.run(["hermes", ...])`.
- DON'T: использовать `input()` или интерактивный ввод.
- DON'T: писать за пределы `output_dir`.

## Thinking Process

1. Прочитаю `B-04.6-crossfunction-deployment.yaml` — получу handoff_triggers (HT-01..04), kanban_tasks, deployment_phases
2. Прочитаю `labor-function-to-skill-mapping.yaml` — получу статус покрытия и skill_path каждой ТФ
3. Прочитаю `otf-section-2.yaml` — извлеку ТД В/05.6 для audit_criteria и recommendations
4. Соберу audit_scope: что аудируется (handoff-точки, профили-исполнители из B-04.6)
5. Для каждого триггера проверю файловую систему: os.path.exists(artifact), затем quality.schema_valid
6. Сформулирую finding для каждого триггера на основе реальных результатов
7. Сформирую recommendations из ТД В/05.6 + findings (закрыть timeout, создать недостающий артефакт)
8. Проверю: каждый finding соответствует реальной проверке, рекомендации обоснованы
9. Запишу в output_files[0] (meta уже внутри файла)

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
def check_artifact(path):
    """Проверка артефакта: существует + валиден YAML (schema_valid в quality)."""
    if not os.path.exists(path):
        return False, False
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except Exception:
        return True, False
    if not isinstance(data, dict):
        return True, False
    quality = data.get("quality", {})
    schema_valid = quality.get("schema_valid", False) if isinstance(quality, dict) else False
    return True, bool(schema_valid)

# ── Шаг 0: Pre-flight Check (идемпотентность, ADR-007) ────────────

la_id = body.get("la_id", "la-001")
parent_tf = body.get("parent_tf", "LF-07.007-В/05.6")
tf_code = parent_tf.replace("LF-07.007-", "") if parent_tf else "В/05.6"

print(f"  TF: {tf_code}, LA: {la_id}")

current_skill_path = "profiles/analyst/skills/crossfunction-auditor/SKILL.md"
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
deploy_data = read_file(os.path.join(
    ARCH_DIR, "outputs/07.007/block-B/B-04.6-crossfunction-deployment.yaml"))
mapping_data = read_file(os.path.join(
    ARCH_DIR, "outputs/07.007/block-D/labor-function-to-skill-mapping.yaml"))
otf2 = read_file(os.path.join(ARCH_DIR, "docs/standards/07.007/otf-section-2.yaml"))

deploy_body = deploy_data.get("body", {})
triggers = deploy_body.get("handoff_triggers", [])
kanban_tasks = deploy_body.get("kanban_tasks", [])
phases = deploy_body.get("deployment_phases", [])
mappings = mapping_data.get("mappings", [])

print(f"  Triggers: {len(triggers)}, Kanban tasks: {len(kanban_tasks)}, Phases: {len(phases)}")

# ТД В/05.6 из профстандарта
td_v056 = []
for lf in otf2.get("labor_functions", []):
    if lf.get("code") == "В/05.6":
        td_v056 = lf.get("трудовые_действия", [])
        break
if not td_v056:
    print("  [WARN] ТД В/05.6 не найдено в otf-section-2.yaml — используем только данные плана внедрения")

# ── audit_scope ────────────────────────────────────────────────────

audit_scope = {
    "tf_code": tf_code,
    "tf_name": "Аудит деятельности в рамках кросс-функционального процесса",
    "description": (
        "Аудит кросс-функциональных handoff-точек из плана внедрения B-04.6: "
        "существование артефактов, валидность YAML, заданность timeout."
    ),
    "audited_triggers": len(triggers),
    "source_plan": "outputs/07.007/block-B/B-04.6-crossfunction-deployment.yaml",
}

# ── audit_criteria: из ТД В/05.6 ───────────────────────────────────

audit_criteria = []
for i, td in enumerate(td_v056, 1):
    audit_criteria.append({
        "criterion_id": f"AC-{i:02d}",
        "criterion_name": td.split(" ")[0] + " " + td.split(" ")[1] if len(td.split(" ")) > 1 else td[:40],
        "source_td": td,
    })

print(f"  Audit criteria: {len(audit_criteria)}")

# ── handoff_audit: проверка файловой системы ───────────────────────

handoff_audit = []
for t in triggers:
    trigger_id = t.get("trigger_id", "")
    source_tf = t.get("source_tf", "")
    target_tf = t.get("target_tf", "")
    artifact = t.get("artifact", "")

    # timeout_defined: в B-04.6 timeout = null + data_gap → не задан
    data_gap = t.get("data_gap", "")
    timeout_defined = not data_gap and t.get("timeout") is not None

    artifact_exists, artifact_valid = check_artifact(artifact)

    if not artifact_exists:
        finding = f"Артефакт не найден на файловой системе"
    elif not artifact_valid:
        finding = f"Артефакт существует, но YAML невалиден или schema_valid=false"
    else:
        if timeout_defined:
            finding = "Артефакт существует и валиден, timeout задан"
        else:
            finding = "Артефакт существует и валиден, но timeout не задан"

    handoff_audit.append({
        "trigger_id": trigger_id,
        "source_tf": source_tf,
        "target_tf": target_tf,
        "artifact": artifact,
        "artifact_exists": artifact_exists,
        "artifact_valid": artifact_valid,
        "timeout_defined": timeout_defined,
        "finding": finding,
    })

print(f"  Handoff audit: {len(handoff_audit)}")

# ── recommendations: из ТД В/05.6 + findings ───────────────────────

recommendations = []
for h in handoff_audit:
    if not h["artifact_exists"]:
        recommendations.append({
            "recommendation_id": f"R-{len(recommendations)+1:02d}",
            "trigger_id": h["trigger_id"],
            "recommendation": (
                f"Создать недостающий артефакт {h['artifact']} "
                f"(источник {h['source_tf']}) — найти и устранить причину отсутствия"
            ),
            "basis": "artifact_exists=false",
            "source_td": next((c["source_td"] for c in audit_criteria if "Анализ документов" in c["source_td"]), ""),
        })
    elif not h["artifact_valid"]:
        recommendations.append({
            "recommendation_id": f"R-{len(recommendations)+1:02d}",
            "trigger_id": h["trigger_id"],
            "recommendation": (
                f"Исправить валидность артефакта {h['artifact']} — schema_valid=false или битый YAML"
            ),
            "basis": "artifact_valid=false",
            "source_td": next((c["source_td"] for c in audit_criteria if "Анализ документов" in c["source_td"]), ""),
        })
    if not h["timeout_defined"]:
        recommendations.append({
            "recommendation_id": f"R-{len(recommendations)+1:02d}",
            "trigger_id": h["trigger_id"],
            "recommendation": (
                f"Задать timeout для {h['trigger_id']} ({h['source_tf']} → {h['target_tf']}) "
                f"в спецификации B-03.6 и плане B-04.6"
            ),
            "basis": "timeout_defined=false",
            "source_td": next((c["source_td"] for c in audit_criteria if "рекомендаций" in c["source_td"]), ""),
        })

# Если все артефакты валидны — рекомендация из ТД В/05.6 (инструктаж участников)
if not recommendations:
    recommendations.append({
        "recommendation_id": "R-01",
        "trigger_id": "",
        "recommendation": (
            "Все handoff-артефакты существуют и валидны. Провести инструктаж участников "
            "кросс-функционального процесса (ТД В/05.6)"
        ),
        "basis": "all artifacts valid",
        "source_td": next((c["source_td"] for c in audit_criteria if "Инструктаж" in c["source_td"]), ""),
    })

print(f"  Recommendations: {len(recommendations)}")

# ── Шаг 3: Валидация ───────────────────────────────────────────────

errors = []
if not handoff_audit:
    errors.append("handoff_audit пуст — нет триггеров в B-04.6")
for h in handoff_audit:
    if not h["trigger_id"]:
        errors.append("trigger_id пуст в handoff_audit")
for h in handoff_audit:
    if h["artifact_exists"] is None:
        errors.append(f"artifact_exists не определён для {h['trigger_id']}")

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
        "generated_by": "crossfunction-auditor",
        "timestamp": os.popen("date -u +%Y-%m-%dT%H:%M:%SZ").read().strip(),
        "schema_ref": "crossfunction-audit-schema.yaml v1.0.0",
    },
    "body": {
        "audit_scope": audit_scope,
        "audit_criteria": audit_criteria,
        "handoff_audit": handoff_audit,
        "recommendations": recommendations,
        "data_gaps": [],
    },
    "quality": {
        "schema_valid": schema_valid,
        "sources_read": [
            "outputs/07.007/block-B/B-04.6-crossfunction-deployment.yaml",
            "outputs/07.007/block-D/labor-function-to-skill-mapping.yaml",
            "docs/standards/07.007/otf-section-2.yaml",
        ],
        "warnings": [],
    },
}

write_ok = write_yaml(output_path, result)
if not write_ok:
    print("  [ERROR] failed to write audit report")
    os._exit(1)

# ── Шаг 5: Отчёт ───────────────────────────────────────────────────

print(f"  Written: {output_path}")
print(f"  Schema valid: {schema_valid}")
```

## Схемы данных

```yaml
# crossfunction-audit-schema.yaml v1.0.0
meta:
  artifact: str            # B-05.6-crossfunction-audit
  tf: str                  # В/05.6
  la: str                  # la-001
  generated_by: str        # crossfunction-auditor
  timestamp: str           # ISO-8601 UTC
  schema_ref: str

body:
  audit_scope:
    tf_code: str
    tf_name: str
    description: str
    audited_triggers: int
    source_plan: str
  audit_criteria:
    - criterion_id: str    # AC-01
      criterion_name: str
      source_td: str       # полное ТД В/05.6
  handoff_audit:
    - trigger_id: str      # HT-01
      source_tf: str
      target_tf: str
      artifact: str
      artifact_exists: bool    # os.path.exists()
      artifact_valid: bool     # quality.schema_valid внутри YAML
      timeout_defined: bool    # из data_gap в B-04.6
      finding: str
  recommendations:
    - recommendation_id: str   # R-01
      trigger_id: str
      recommendation: str
      basis: str               # artifact_exists=false | artifact_valid=false | timeout_defined=false
      source_td: str
  data_gaps: list[str]

quality:
  schema_valid: bool
  sources_read: list[str]
  warnings: list[str]
```
