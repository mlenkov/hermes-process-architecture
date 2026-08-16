---
name: regulation-writer
description: >
  Разработка регламента процесса. Читает process-info-context.yaml (от info-gatherer),
  docs/standards/07.007/otf-section-1.yaml, генерирует process-regulation.yaml
  с областью применения, шагами, ролями и процедурами контроля.
version: 1.0.0
---

# regulation-writer

**Трудовое действие (А/02.6):** Разработка и усовершенствование регламента процесса подразделения организации или административного регламента подразделения организации

**Принцип:** Никаких вымышленных данных. Все данные извлекаются из реальной файловой системы.

## ICOM

**Inputs:**
  - `block-A/A-01.6-info-context.yaml` — контекст от info-gatherer (ТФ блока A, профили, покрытие)
  - `otf-section-1.yaml` — исходные данные блока A профстандарта

**Outputs:**
  - `outputs/07.007/block-A/A-02.6-regulation.yaml` — регламент процесса с метой, шагами, ролями и контролем

## Rules (DO / DON'T)

**ВСЕГДА ДЕЛАЙ:**
- DO: проверяй существование файла перед `open()`. Используй `os.path.exists()`.
- DO: оборачивай `yaml.safe_load()` в `try/except`. Файл может быть битым или пустым.
- DO: извлекай данные ТОЛЬКО из реальных файлов системы (`block-A/A-01.6-info-context.yaml`, `otf-section-1.yaml`).

**КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО:**
- DON'T: генерировать вымышленные имена, компании, организации. Все данные — только из файлов.
- DON'T: вызывать `subprocess.run(["hermes", ...])` из навыка. Это делает executor.
- DON'T: писать за пределы `output_dir`. Каждый навык пишет только в свою директорию.
- DON'T: использовать `input()` или интерактивный ввод. Навык работает без пользователя.

## Thinking Process

1. Прочитаю `outputs/07.007/block-A/A-01.6-info-context.yaml` — получу контекст от gatherer (ТФ, профили, покрытие)
2. Прочитаю `docs/standards/07.007/otf-section-1.yaml` — получу список трудовых действий для А/02.6
3. Прочитаю `outputs/07.007/block-D/labor-function-to-skill-mapping.yaml` — получу статус покрытия А/02.6
4. Извлеку из контекста: labor_functions для А/02.6, team_info.profiles_available
5. Проверю: если context не найден — запишу предупреждение, сформирую регламент только из стандарта
6. Сформирую `result = {meta, body, quality}`:
   - body.regulation: название, область применения, термины (из названия и действий А/02.6)
   - body.process_steps: шаги из трудовых действий (4 шага)
   - body.roles_responsibilities: маппинг ролей на профили из team_info
   - body.control_procedures: процедуры контроля (из действий А/02.6)
7. Запишу в `output_files[0]` (meta уже внутри файла)

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
parent_tf = body.get("parent_tf", "LF-07.007-А/02.6")
tf_code = parent_tf.replace("LF-07.007-", "") if parent_tf else "А/02.6"

print(f"  TF: {tf_code}, LA: {la_id}")

current_skill_path = "profiles/regulator/skills/regulation-writer/SKILL.md"
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

# 2b. Профстандарт (otf-section-1.yaml)
otf_1_path = os.path.join(ARCH_DIR, "docs/standards/07.007/otf-section-1.yaml")
otf_1_data = read_file(otf_1_path)

# Найти конкретную ТФ А/02.6
target_tf = None
for lf in otf_1_data.get("labor_functions", []):
    if lf.get("code") == "А/02.6":
        target_tf = lf
        break

if not target_tf:
    print("  [WARN] TF А/02.6 not found in otf-section-1.yaml")
    target_tf = {
        "code": "А/02.6",
        "name": "Разработка и усовершенствование регламента процесса",
        "трудовые_действия": [],
        "необходимые_умения": []
    }

td_actions = target_tf.get("трудовые_действия", [])
td_skills = target_tf.get("необходимые_умения", [])
print(f"  ТД: {len(td_actions)} actions, {len(td_skills)} skills")

# 2c. Профили из контекста (или fallback из AGENTS.md)
team_info = context.get("body", {}).get("team_info", {})
profiles = team_info.get("profiles_available", [])

# Если контекст не найден — прочитать AGENTS.md напрямую
if not profiles:
    agents_lines = []
    agents_path = os.path.join(ARCH_DIR, "../AGENTS.md")
    if os.path.exists(agents_path):
        try:
            with open(agents_path) as f:
                agents_lines = f.readlines()
        except:
            pass

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

print(f"  Profiles: {len(profiles)}")

# ── Шаг 3: Формирование регламента ─────────────────────────────────

output_path = output_files[0] if output_files else os.path.join(
    output_dir, "process-regulation.yaml"
)
artifact_id = os.path.basename(output_path).replace(".yaml", "")

# 3a. regulation header
regulation_name = target_tf.get("name", "Регламент процесса")
regulation = {
    "name": regulation_name,
    "standard_ref": "07.007",
    "tf_code": tf_code,
    "scope": f"Настоящий регламент определяет порядок выполнения процесса «{regulation_name}» в рамках профстандарта 07.007 «Специалист по процессному управлению», блок A — Регламентация процессов подразделений.",
    "terms": [
        {"term": "Процесс", "definition": "Совокупность последовательных операций, преобразующих входы в выходы"},
        {"term": "Регламент", "definition": "Документ, устанавливающий порядок выполнения процесса"},
        {"term": "Трудовое действие", "definition": "Элементарная операция в составе трудовой функции"},
    ]
}

# 3b. process_steps — из трудовых действий А/02.6
process_steps = []
for i, action in enumerate(td_actions, 1):
    process_steps.append({
        "step_id": f"step-{i:02d}",
        "name": action,
        "description": f"Выполнение трудового действия: {action}",
        "inputs": ["process-info-context"] if i == 1 else [f"step-{i-1:02d}-output"],
        "outputs": [f"step-{i:02d}-output"],
        "skills_required": td_skills
    })

# 3c. roles_responsibilities — из профилей
roles_responsibilities = []
for p in profiles:
    if "управл" in str(p.get("role", "")).lower() or p.get("profile_id") == "mais":
        roles_responsibilities.append({
            "profile_id": p["profile_id"],
            "name": p.get("name", ""),
            "role": "Ответственный за процессное управление",
            "responsibilities": [
                f"Контроль выполнения регламента {regulation_name}",
                "Актуализация документации",
                "Мониторинг показателей процесса"
            ]
        })
    elif p.get("profile_id") == "architect":
        roles_responsibilities.append({
            "profile_id": "architect",
            "name": "Хранитель архитектуры",
            "role": "Исполнитель регламента",
            "responsibilities": [
                "Генерация артефактов регламента",
                "Валидация соответствия стандарту",
                "Обновление coverage registry"
            ]
        })

# 3d. control_procedures — из действий А/02.6 (разработка процедур контроля)
control_procedures = []
for action in td_actions:
    if "контрол" in action.lower():
        control_procedures.append({
            "procedure": action,
            "frequency": "каждый цикл PDCA",
            "responsible": "architect",
            "artifact": "labor-coverage-registry.yaml"
        })

# Если не нашли — минимальная процедура
if not control_procedures:
    control_procedures.append({
        "procedure": "Контроль выполнения регламента процесса",
        "frequency": "каждый цикл PDCA",
        "responsible": "architect",
        "artifact": "process-regulation.yaml"
    })

# ── Шаг 4: Сборка результата ───────────────────────────────────────

result = {
    "meta": {
        "artifact": artifact_id,
        "tf": tf_code,
        "la": la_id,
        "generated_by": "regulation-writer",
        "timestamp": os.popen("date -u +%Y-%m-%dT%H:%M:%SZ").read().strip(),
        "schema_ref": "process-regulation-schema.yaml v1.0.0"
    },
    "body": {
        "regulation": regulation,
        "process_steps": process_steps,
        "roles_responsibilities": roles_responsibilities,
        "control_procedures": control_procedures
    },
    "quality": {
        "schema_valid": True,
        "sources_read": [],
        "context_available": context_found
    }
}

# ── Шаг 5: Валидация ───────────────────────────────────────────────

sources = []
if context_found:
    sources.append("outputs/07.007/block-A/A-01.6-info-context.yaml")
if otf_1_data:
    sources.append("docs/standards/07.007/otf-section-1.yaml")
if profiles:
    sources.append("../AGENTS.md")

required_fields = ["regulation", "process_steps", "roles_responsibilities", "control_procedures"]
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
print(f"  Steps: {len(process_steps)}")
print(f"  Roles: {len(roles_responsibilities)}")
print(f"  Sources: {len(sources)}")
print(f"  Schema valid: {result['quality']['schema_valid']}")
```

## Схемы данных
- `outputs/07.007/block-A/A-01.6-info-context.yaml` — входной контекст от info-gatherer
- `docs/standards/07.007/otf-section-1.yaml` — исходные данные блока A
- `outputs/07.007/block-D/new-skill-architecture-blueprint.md` (раздел 8 — эталонный шаблон)
