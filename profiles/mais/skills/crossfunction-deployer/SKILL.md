---
name: crossfunction-deployer
description: >
  Внедрение кросс-функционального процесса (В/04.6). Читает исполняемую
  спецификацию (B-03.6-crossfunction-spec.yaml), labour-function-to-skill
  mapping и ТД В/04.6 профстандарта, генерирует план внедрения:
  deployment phases, kanban tasks, handoff triggers, stakeholder
  notifications, success criteria.
version: 1.0.0
---

# crossfunction-deployer

**Трудовое действие (В/04.6):** Внедрение кросс-функционального процесса

**Принцип:** План внедрения строится ТОЛЬКО из спецификации B-03.6, mapping и ТД В/04.6. Никаких вымышленных задач, триггеров и уведомлений.

## ICOM

**Inputs:**
  - `outputs/07.007/block-B/B-03.6-crossfunction-spec.yaml` — исполняемая спецификация (handoff_contracts, control_points, profile_responsibilities)
  - `outputs/07.007/block-D/labor-function-to-skill-mapping.yaml` — ТФ → навык, статус покрытия
  - `docs/standards/07.007/otf-section-2.yaml` — блок B профстандарта (ТД В/04.6)

**Outputs:**
  - `outputs/07.007/block-B/B-04.6-crossfunction-deployment.yaml` — план внедрения кросс-функционального процесса

**Controls:**
  - `07.007` — профстандарт
  - `new-skill-architecture-blueprint.md` — архитектурный шаблон

**Mechanisms:**
  - `crossfunction-deployer` (навык)

## Rules (DO / DON'T)

**ВСЕГДА ДЕЛАЙ:**
- DO: проверяй существование файла перед `open()`. Используй `os.path.exists()`.
- DO: оборачивай `yaml.safe_load()` в `try/except`.
- DO: извлекай данные ТОЛЬКО из реальных файлов (B-03.6, mapping, otf-section-2).
- DO: каждая kanban-задача = профиль + действие из handoff_contracts спецификации B-03.6.
- DO: каждый handoff trigger = контракт из B-03.6 (source/target/artifact) + время из control_points.

**КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО:**
- DON'T: генерировать вымышленные задачи, триггеры, уведомления.
- DON'T: выдумывать timeout / расписания — их нет в B-03.6, помечай как отсутствующие.
- DON'T: вызывать `subprocess.run(["hermes", ...])`.
- DON'T: использовать `input()` или интерактивный ввод.
- DON'T: писать за пределы `output_dir`.

## Thinking Process

1. Прочитаю `B-03.6-crossfunction-spec.yaml` — получу handoff_contracts, control_points, profile_responsibilities
2. Прочитаю `labor-function-to-skill-mapping.yaml` — получу статус покрытия и skill_path каждой ТФ
3. Прочитаю `otf-section-2.yaml` — извлеку ТД В/04.6 для deployment_phases и success_criteria
4. Соберу deployment_phases из 4 ТД В/04.6 (планирование, внедрение, оценка эффективности, инструктаж)
5. Построю kanban_tasks: для каждого handoff-контракта — задача профилю-target (приёмка артефакта)
6. Построю handoff_triggers из контрактов + контрольных точек спецификации
7. Построю stakeholder_notifications из profile_responsibilities (профиль приёмщика уведомляется при передаче)
8. Сформирую success_criteria из ТД В/04.6 (критерии для каждой фазы)
9. Проверю: все профили/навыки существуют в mapping, все артефакты реальные
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
parent_tf = body.get("parent_tf", "LF-07.007-В/04.6")
tf_code = parent_tf.replace("LF-07.007-", "") if parent_tf else "В/04.6"

print(f"  TF: {tf_code}, LA: {la_id}")

current_skill_path = "profiles/mais/skills/crossfunction-deployer/SKILL.md"
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
spec_data = read_file(os.path.join(
    ARCH_DIR, "outputs/07.007/block-B/B-03.6-crossfunction-spec.yaml"))
mapping_data = read_file(os.path.join(
    ARCH_DIR, "outputs/07.007/block-D/labor-function-to-skill-mapping.yaml"))
otf2 = read_file(os.path.join(ARCH_DIR, "docs/standards/07.007/otf-section-2.yaml"))

spec_body = spec_data.get("body", {})
contracts = spec_body.get("handoff_contracts", [])
checkpoints = spec_body.get("control_points", [])
responsibilities = spec_body.get("profile_responsibilities", [])
mappings = mapping_data.get("mappings", [])

print(f"  Contracts: {len(contracts)}, Checkpoints: {len(checkpoints)}, Responsibilities: {len(responsibilities)}")

# ТД В/04.6 из профстандарта
td_v046 = []
for lf in otf2.get("labor_functions", []):
    if lf.get("code") == "В/04.6":
        td_v046 = lf.get("трудовые_действия", [])
        break
if not td_v046:
    print("  [WARN] ТД В/04.6 не найдено в otf-section-2.yaml — используем только данные спецификации")

# ── deployment_phases: из ТД В/04.6 ────────────────────────────────

def td_short(text):
    s = text.split("(")[0].strip()
    s = s.replace(" организации", "").replace("организации", "").strip()
    s = re.sub(r"\s+", " ", s).strip()
    s = s.rstrip(",").strip()
    return s if s else text

phase_names = [
    "Планирование внедрения",
    "Внедрение",
    "Оценка эффективности внедрения",
    "Инструктаж персонала",
]

deployment_phases = []
for i, td in enumerate(td_v046, 1):
    deployment_phases.append({
        "phase_id": f"PH-{i:02d}",
        "phase_name": phase_names[i-1] if i <= len(phase_names) else td_short(td),
        "source_td": td,
    })

if not deployment_phases:
    # Fallback: фазы из имён ТД В/04.6 (из mapping tf_actions)
    for m in mappings:
        if m.get("tf_code") == "В/04.6":
            for action in m.get("tf_actions", []):
                deployment_phases.append({
                    "phase_id": f"PH-{len(deployment_phases)+1:02d}",
                    "phase_name": action,
                    "source_td": action,
                })
            break

print(f"  Deployment phases: {len(deployment_phases)}")

# ── profile_responsibilities → карта профилей ──────────────────────

# target_tf → (profile, skill) из ответственностей спецификации
target_info = {}
for r in responsibilities:
    target_info[r.get("tf_code")] = {
        "profile": r.get("profile", ""),
        "skill": r.get("skill", ""),
        "tf_name": r.get("tf_name", ""),
    }

# ── kanban_tasks: из handoff_contracts ─────────────────────────────

kanban_tasks = []
for i, c in enumerate(contracts, 1):
    target_tf = c.get("target_tf", "")
    info = target_info.get(target_tf, {})
    kanban_tasks.append({
        "task_id": f"KT-{i:02d}",
        "tf_code": target_tf,
        "profile": info.get("profile", ""),
        "skill": info.get("skill", ""),
        "action": (
            f"Принять артефакт {c.get('artifact')} от {c.get('source_tf')} "
            f"(контракт {c.get('contract_id')})"
        ),
        "source_contract": c.get("contract_id", ""),
        "status": "pending",
    })

print(f"  Kanban tasks: {len(kanban_tasks)}")

# ── handoff_triggers: контракты + контрольные точки ────────────────

handoff_triggers = []
for i, c in enumerate(contracts, 1):
    target_tf = c.get("target_tf", "")
    source_tf = c.get("source_tf", "")
    # контрольная точка, соответствующая источнику и получателю (по имени CP)
    cp = next((cp_ for cp_ in checkpoints
               if cp_.get("tf_code") == target_tf
               and source_tf in cp_.get("checkpoint_name", "")), None)
    if cp is None:
        # fallback: любая контрольная точка целевой ТФ
        cp = next((cp_ for cp_ in checkpoints if cp_.get("tf_code") == target_tf), None)
    trigger = {
        "trigger_id": f"HT-{i:02d}",
        "source_tf": source_tf,
        "target_tf": target_tf,
        "artifact": c.get("artifact", ""),
        "condition": "schema_valid",
        "timeout": None,
        "data_gap": "timeout не задан в спецификации B-03.6",
    }
    if cp:
        trigger["checkpoint_id"] = cp.get("checkpoint_id", "")
        trigger["auto_proceed"] = cp.get("auto_proceed", False)
    handoff_triggers.append(trigger)

print(f"  Handoff triggers: {len(handoff_triggers)}")

# ── stakeholder_notifications: из profile_responsibilities ─────────

# Уведомляем профиль-приёмщик при передаче артефакта (по контрактам)
notified_tfs = set()
stakeholder_notifications = []
for c in contracts:
    target_tf = c.get("target_tf", "")
    if target_tf in notified_tfs:
        continue
    notified_tfs.add(target_tf)
    info = target_info.get(target_tf, {})
    if info.get("profile"):
        stakeholder_notifications.append({
            "notification_id": f"SN-{len(stakeholder_notifications)+1:02d}",
            "tf_code": target_tf,
            "profile": info["profile"],
            "skill": info["skill"],
            "event": f"Артефакт от {c.get('source_tf')} готов к приёмке",
            "channel": "kanban-task",
        })

print(f"  Stakeholder notifications: {len(stakeholder_notifications)}")

# ── success_criteria: из ТД В/04.6 ─────────────────────────────────

# Критерий на каждую фазу: успех = фаза завершена (источник — ТД В/04.6)
success_criteria = []
for i, phase in enumerate(deployment_phases, 1):
    success_criteria.append({
        "criterion_id": f"SC-{i:02d}",
        "phase_id": phase["phase_id"],
        "phase_name": phase["phase_name"],
        "criterion": f"Фаза «{phase['phase_name']}» выполнена",
        "source_td": phase["source_td"],
    })

print(f"  Success criteria: {len(success_criteria)}")

# ── data_gaps ──────────────────────────────────────────────────────

data_gaps = []
if not td_v046:
    data_gaps.append("ТД В/04.6 не найдено в otf-section-2.yaml — фазы из mapping")
for t in handoff_triggers:
    if t.get("timeout") is None:
        data_gaps.append(f"timeout не задан для {t['trigger_id']}")
if not stakeholder_notifications:
    data_gaps.append("profile_responsibilities пусты — уведомления не построены")

# ── Шаг 3: Валидация ───────────────────────────────────────────────

errors = []
if not deployment_phases:
    errors.append("deployment_phases пуст")
if not contracts:
    errors.append("handoff_contracts пусты — kanban_tasks и triggers не из чего строить")
for t in kanban_tasks:
    if not t["profile"]:
        errors.append(f"kanban {t['task_id']}: профиль не найден для {t['tf_code']}")
for t in handoff_triggers:
    if t["source_tf"] not in target_info and t["source_tf"] not in [m.get("tf_code") for m in mappings]:
        errors.append(f"trigger {t['trigger_id']}: source {t['source_tf']} не найден в mapping")

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
        "generated_by": "crossfunction-deployer",
        "timestamp": os.popen("date -u +%Y-%m-%dT%H:%M:%SZ").read().strip(),
        "schema_ref": "crossfunction-deployment-schema.yaml v1.0.0",
    },
    "body": {
        "deployment_phases": deployment_phases,
        "kanban_tasks": kanban_tasks,
        "handoff_triggers": handoff_triggers,
        "stakeholder_notifications": stakeholder_notifications,
        "success_criteria": success_criteria,
        "data_gaps": data_gaps,
    },
    "quality": {
        "schema_valid": schema_valid,
        "sources_read": [
            "outputs/07.007/block-B/B-03.6-crossfunction-spec.yaml",
            "outputs/07.007/block-D/labor-function-to-skill-mapping.yaml",
            "docs/standards/07.007/otf-section-2.yaml",
        ],
        "warnings": [],
    },
}

write_ok = write_yaml(output_path, result)
if not write_ok:
    print("  [ERROR] failed to write deployment plan")
    os._exit(1)

# ── Шаг 5: Отчёт ───────────────────────────────────────────────────

print(f"  Written: {output_path}")
print(f"  Schema valid: {schema_valid}")
print(f"  Data gaps: {len(data_gaps)}")
```

## Схемы данных

```yaml
# crossfunction-deployment-schema.yaml v1.0.0
meta:
  artifact: str            # B-04.6-crossfunction-deployment
  tf: str                  # В/04.6
  la: str                  # la-001
  generated_by: str        # crossfunction-deployer
  timestamp: str           # ISO-8601 UTC
  schema_ref: str

body:
  deployment_phases:
    - phase_id: str        # PH-01
      phase_name: str
      source_td: str       # полное ТД В/04.6
  kanban_tasks:
    - task_id: str         # KT-01
      tf_code: str         # целевая ТФ
      profile: str         # профиль-исполнитель
      skill: str
      action: str          # приёмка артефакта по контракту
      source_contract: str # HO-01
      status: str          # pending
  handoff_triggers:
    - trigger_id: str      # HT-01
      source_tf: str
      target_tf: str
      artifact: str
      condition: str       # schema_valid
      timeout: null        # не задан — data_gap
      data_gap: str
      checkpoint_id: str   # из control_points спецификации (если есть)
      auto_proceed: bool
  stakeholder_notifications:
    - notification_id: str # SN-01
      tf_code: str
      profile: str
      skill: str
      event: str
      channel: str         # kanban-task
  success_criteria:
    - criterion_id: str    # SC-01
      phase_id: str
      phase_name: str
      criterion: str
      source_td: str
  data_gaps: list[str]

quality:
  schema_valid: bool
  sources_read: list[str]
  warnings: list[str]
```
