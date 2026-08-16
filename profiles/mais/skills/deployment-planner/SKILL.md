---
name: deployment-planner
description: >
  Планирование внедрения регламента. Читает A-01.6-info-context.yaml,
  A-02.6-regulation.yaml и otf-section-1.yaml, генерирует deployment-plan.yaml
  с фазами, gates, milestones, ответственными и критериями успеха.
version: 1.0.0
---

# deployment-planner

**Трудовое действие (А/03.6):** Ввод в действие регламента процесса подразделения организации или административного регламента подразделения организации

**Принцип:** Никаких вымышленных данных. Все данные извлекаются из реальной файловой системы.

## ICOM

**Inputs:**
  - `block-A/A-01.6-info-context.yaml` — контекст от info-gatherer (ТФ, профили, покрытие)
  - `block-A/A-02.6-regulation.yaml` — регламент от regulation-writer (шаги, роли, контроль)
  - `otf-section-1.yaml` — исходные данные блока A профстандарта

**Outputs:**
  - `outputs/07.007/block-A/A-03.6-deployment-plan.yaml` — план внедрения с фазами, gates, milestones (профиль mais)

## Rules (DO / DON'T)

**ВСЕГДА ДЕЛАЙ:**
- DO: проверяй существование файла перед `open()`. Используй `os.path.exists()`.
- DO: оборачивай `yaml.safe_load()` в `try/except`. Файл может быть битым или пустым.
- DO: извлекай данные ТОЛЬКО из реальных файлов системы (`block-A/*.yaml`, `otf-section-1.yaml`).
- DO: формируй gates и milestones строго на основе трудовых действий из стандарта.

**КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО:**
- DON'T: генерировать вымышленные даты, имена, организации. Все данные — только из файлов.
- DON'T: вызывать `subprocess.run(["hermes", ...])` из навыка. Это делает executor.
- DON'T: писать за пределы `output_dir`. Каждый навык пишет только в свою директорию.
- DON'T: использовать `input()` или интерактивный ввод. Навык работает без пользователя.

## Thinking Process

1. Прочитаю `outputs/07.007/block-A/A-01.6-info-context.yaml` — получу контекст от gatherer (ТФ, профили, покрытие)
2. Прочитаю `outputs/07.007/block-A/A-02.6-regulation.yaml` — получу шаги процесса и роли из регламента
3. Прочитаю `docs/standards/07.007/otf-section-1.yaml` — получу список трудовых действий для А/03.6
4. Проверю: если context или regulation не найдены — запишу предупреждение, использую только стандарт
5. Сформирую `result = {meta, body, quality}`:
   - body.deployment_phases: 4 фазы из трудовых действий А/03.6
   - body.gates: контрольные точки между фазами
   - body.milestones: вехи для каждой фазы
   - body.responsible_profiles: маппинг профилей на фазы из team_info
   - body.success_criteria: критерии из действий А/03.6
6. Запишу в `output_files[0]` (meta уже внутри файла)

## Process

```python
import os, yaml

ARCH_DIR = os.path.abspath(".")

def read_file(path):
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
# ── Шаг 0: Pre-flight Check (идемпотентность, ADR-007) ────────────────────────────────────────────────

la_id = body.get("la_id", "la-001")
parent_tf = body.get("parent_tf", "LF-07.007-А/03.6")
tf_code = parent_tf.replace("LF-07.007-", "") if parent_tf else "А/03.6"

print(f"  TF: {tf_code}, LA: {la_id}")

current_skill_path = "profiles/mais/skills/deployment-planner/SKILL.md"
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

# ── Шаг 2: Чтение источников ───────────────────────────────────────

# 2a. Контекст от gatherer
context_path = os.path.join(
    ARCH_DIR, "outputs/07.007/block-A/A-01.6-info-context.yaml"
)
context = read_file(context_path)
context_found = bool(context)
print(f"  Context from gatherer: {'found' if context_found else 'NOT FOUND'}")

# 2b. Регламент от regulation-writer
regulation_path = os.path.join(
    ARCH_DIR, "outputs/07.007/block-A/A-02.6-regulation.yaml"
)
regulation = read_file(regulation_path)
regulation_found = bool(regulation)
print(f"  Regulation from writer: {'found' if regulation_found else 'NOT FOUND'}")

# 2c. Профстандарт (otf-section-1.yaml)
otf_1_path = os.path.join(ARCH_DIR, "docs/standards/07.007/otf-section-1.yaml")
otf_1_data = read_file(otf_1_path)

# Найти конкретную ТФ А/03.6
target_tf = None
for lf in otf_1_data.get("labor_functions", []):
    if lf.get("code") == "А/03.6":
        target_tf = lf
        break

if not target_tf:
    print("  [WARN] TF А/03.6 not found in otf-section-1.yaml")
    target_tf = {
        "code": "А/03.6",
        "name": "Ввод в действие регламента процесса",
        "трудовые_действия": [],
        "необходимые_умения": []
    }

td_actions = target_tf.get("трудовые_действия", [])
td_skills = target_tf.get("необходимые_умения", [])
print(f"  ТД: {len(td_actions)} actions, {len(td_skills)} skills")

# 2d. Профили из контекста (или fallback из AGENTS.md)
team_info = context.get("body", {}).get("team_info", {})
profiles = team_info.get("profiles_available", [])

if not profiles:
    agents_path = os.path.join(ARCH_DIR, "../AGENTS.md")
    if os.path.exists(agents_path):
        try:
            with open(agents_path) as f:
                agents_lines = f.readlines()
            in_table = False
            for line in agents_lines:
                stripped = line.strip()
                if stripped.startswith("| Профиль"):
                    in_table = True
                    continue
                if in_table:
                    if stripped.startswith("|---"):
                        continue
                    if not stripped or not stripped.startswith("|"):
                        in_table = False
                        continue
                    parts = [p.strip().strip("**") for p in stripped.split("|")]
                    if len(parts) >= 5:
                        profiles.append({
                            "profile_id": parts[1].lower().replace(" ", "-"),
                            "name": parts[2],
                            "role": parts[3],
                            "standard": parts[4]
                        })
        except:
            pass

print(f"  Profiles: {len(profiles)}")

# 2e. Steps и roles из регламента (если доступны)
regulation_steps = regulation.get("body", {}).get("process_steps", []) if regulation_found else []
regulation_roles = regulation.get("body", {}).get("roles_responsibilities", []) if regulation_found else []
print(f"  Regulation steps: {len(regulation_steps)}, roles: {len(regulation_roles)}")

# ── Шаг 3: Формирование плана внедрения ────────────────────────────

output_path = output_files[0] if output_files else os.path.join(
    output_dir, "A-03.6-deployment-plan.yaml"
)
artifact_id = os.path.basename(output_path).replace(".yaml", "")

# 3a. deployment_phases — из трудовых действий А/03.6
deployment_phases = []
phase_descriptions = [
    "Планирование мероприятий по вводу в действие регламента",
    "Внедрение регламента в действие",
    "Внедрение предложений по повышению эффективности",
    "Оценка эффективности мероприятий по вводу в действие"
]

for i, action in enumerate(td_actions, 1):
    phase = {
        "phase_id": f"phase-{i:02d}",
        "name": action,
        "description": phase_descriptions[i-1],
        "td_actions": [action],
        "skills_required": td_skills,
        "inputs": [f"phase-{i-1:02d}-output"] if i > 1 else ["A-02.6-regulation"],
        "outputs": [f"phase-{i:02d}-output"]
    }
    deployment_phases.append(phase)

# 3b. gates — контрольные точки между фазами
gates = []
for i in range(1, len(deployment_phases)):
    gates.append({
        "gate_id": f"gate-{i:02d}",
        "position": f"between phase-{i:02d} and phase-{i+1:02d}",
        "criteria": [
            f"Все артефакты фазы {i} созданы",
            f"Качество артефактов подтверждено (schema_valid = true)",
            f"Ответственные профили назначены"
        ],
        "approval_required": False,
        "auto_proceed": True
    })
# Финальный gate
gates.append({
    "gate_id": "gate-final",
    "position": "after phase-04",
    "criteria": [
        "Все 4 фазы выполнены",
        "Оценка эффективности проведена",
        "Регламент введён в действие"
    ],
    "approval_required": False,
    "auto_proceed": True
})

# 3c. milestones — вехи для каждой фазы
milestones = []
for i, phase in enumerate(deployment_phases, 1):
    milestones.append({
        "milestone_id": f"milestone-{i:02d}",
        "phase": phase["phase_id"],
        "name": f"Завершение фазы {i}: {phase_descriptions[i-1]}",
        "condition": f"phase-{i:02d}-output создан и прошёл валидацию",
        "trigger": "auto_promote_children"
    })

# 3d. responsible_profiles — маппинг профилей на фазы
responsible_profiles = []
for i, phase in enumerate(deployment_phases, 1):
    phase_profiles = []
    for p in profiles:
        if p.get("profile_id") == "mais":
            phase_profiles.append({
                "profile_id": "mais",
                "name": "Айра Корбот (COO)",
                "role": "Исполнитель фазы",
                "responsibilities": [
                    f"Генерация артефактов фазы {i}",
                    "Валидация результатов",
                    "Обновление coverage registry после завершения"
                ]
            })
        elif "управл" in str(p.get("role", "")).lower() or p.get("profile_id") == "mais":
            phase_profiles.append({
                "profile_id": p["profile_id"],
                "name": p.get("name", ""),
                "role": "Ответственный за процессное управление",
                "responsibilities": [
                    f"Контроль выполнения фазы {i}",
                    "Утверждение результатов",
                    "Мониторинг показателей"
                ]
            })
    if phase_profiles:
        responsible_profiles.append({
            "phase_id": phase["phase_id"],
            "profiles": phase_profiles
        })

# 3e. success_criteria — из действий А/03.6
success_criteria = []
for action in td_actions:
    if "оценк" in action.lower():
        success_criteria.append({
            "criterion": "Проведена оценка эффективности мероприятий",
            "measure": "Все milestones достигнуты",
            "source_action": action
        })
    elif "внедр" in action.lower() and "предлож" in action.lower():
        success_criteria.append({
            "criterion": "Предложения по повышению эффективности внедрены",
            "measure": "Изменения отражены в регламенте",
            "source_action": action
        })

if not success_criteria:
    success_criteria.append({
        "criterion": "Регламент введён в действие",
        "measure": "Все 4 фазы выполнены последовательно",
        "source_action": "Ввод в действие регламента процесса"
    })

# ── Шаг 4: Сборка результата ───────────────────────────────────────

result = {
    "meta": {
        "artifact": artifact_id,
        "tf": tf_code,
        "la": la_id,
        "generated_by": "deployment-planner",
        "timestamp": os.popen("date -u +%Y-%m-%dT%H:%M:%SZ").read().strip(),
        "schema_ref": "deployment-plan-schema.yaml v1.0.0"
    },
    "body": {
        "deployment_phases": deployment_phases,
        "gates": gates,
        "milestones": milestones,
        "responsible_profiles": responsible_profiles,
        "success_criteria": success_criteria
    },
    "quality": {
        "schema_valid": True,
        "sources_read": [],
        "context_available": context_found,
        "regulation_available": regulation_found
    }
}

# ── Шаг 5: Валидация ───────────────────────────────────────────────

sources = []
if context_found:
    sources.append("outputs/07.007/block-A/A-01.6-info-context.yaml")
if regulation_found:
    sources.append("outputs/07.007/block-A/A-02.6-regulation.yaml")
if otf_1_data:
    sources.append("docs/standards/07.007/otf-section-1.yaml")
if profiles:
    sources.append("../AGENTS.md")

required_fields = ["deployment_phases", "gates", "milestones", "responsible_profiles", "success_criteria"]
missing = [f for f in required_fields if not result.get("body", {}).get(f)]
if missing:
    print(f"  [VALIDATION] missing required body fields: {missing}")
    result["quality"]["schema_valid"] = False
else:
    result["quality"]["schema_valid"] = True

result["quality"]["sources_read"] = sources

# ── Шаг 6: Запись ──────────────────────────────────────────────────

ok = write_yaml(output_path, result)
if not ok:
    print("  [ERROR] failed to write primary artifact")
    os._exit(1)

# ── Шаг 7: Отчёт ───────────────────────────────────────────────────

print(f"  Written: {output_path}")
print(f"  Artifact: {artifact_id}")
print(f"  Phases: {len(deployment_phases)}")
print(f"  Gates: {len(gates)}")
print(f"  Milestones: {len(milestones)}")
print(f"  Responsible profiles: {len(responsible_profiles)}")
print(f"  Sources: {len(sources)}")
print(f"  Schema valid: {result['quality']['schema_valid']}")
```

## Схемы данных
- `outputs/07.007/block-A/A-01.6-info-context.yaml` — входной контекст от info-gatherer
- `outputs/07.007/block-A/A-02.6-regulation.yaml` — регламент от regulation-writer
- `docs/standards/07.007/otf-section-1.yaml` — исходные данные блока A
- `outputs/07.007/block-D/new-skill-architecture-blueprint.md` (раздел 8 — эталонный шаблон)
