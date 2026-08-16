---
name: crossfunction-analyzer
description: >
  Анализ кросс-функционального процесса. Читает AGENTS.md,
  labor-function-to-skill-mapping.yaml, labor-coverage-registry.yaml
  и A-01.6-info-context.yaml, генерирует карту взаимодействий профилей.
version: 1.0.0
---

# crossfunction-analyzer

**Трудовое действие (В/01.6):** Анализ кросс-функционального процесса в рамках системы процессного управления

**Принцип:** Никаких вымышленных данных. Все данные извлекаются из реальной файловой системы.

## ICOM

**Inputs:**
  - `../AGENTS.md` — список профилей AI-команды
  - `block-D/labor-function-to-skill-mapping.yaml` — ТФ и навыки
  - `labor-coverage-registry.yaml` — состояние покрытия
  - `block-A/A-01.6-info-context.yaml` — контекст от regulator

**Outputs:**
  - `outputs/07.007/block-B/B-01.6-crossfunction-flow.yaml` — карта взаимодействий профилей

## Rules (DO / DON'T)

**ВСЕГДА ДЕЛАЙ:**
- DO: проверяй существование файла перед `open()`. Используй `os.path.exists()`.
- DO: оборачивай `yaml.safe_load()` в `try/except`. Файл может быть битым или пустым.
- DO: извлекай данные ТОЛЬКО из реальных файлов системы.
- DO: если данных о профиле нет — явно указывай это в `data_gaps`.

**КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО:**
- DON'T: генерировать вымышленные взаимодействия или процессы.
- DON'T: вызывать `subprocess.run(["hermes", ...])` из навыка. Это делает executor.
- DON'T: писать за пределы `output_dir`. Каждый навык пишет только в свою директорию.
- DON'T: использовать `input()` или интерактивный ввод.

## Thinking Process

1. Прочитаю `../AGENTS.md` — получу список всех профилей, их роли и стандарты
2. Прочитаю `outputs/07.007/block-D/labor-function-to-skill-mapping.yaml` — получу карту ТФ→навык
3. Прочитаю `outputs/07.007/labor-coverage-registry.yaml` — текущее покрытие
4. Прочитаю `outputs/07.007/block-A/A-01.6-info-context.yaml` — контекст от regulator
5. Сформирую inventory всех профилей с их стандартами
6. Построю матрицу потенциальных взаимодействий на основе общих стандартов
7. Выявлю gaps — профили, для которых нет данных о покрытии
8. Сформирую рекомендации по сбору данных
9. Запишу в `output_files[0]`

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

def read_text_lines(path):
    if not os.path.exists(path):
        print(f"  [WARN] file not found: {path}")
        return []
    try:
        with open(path) as f:
            return f.readlines()
    except Exception as e:
        print(f"  [WARN] read error: {path}: {e}")
        return []

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
parent_tf = body.get("parent_tf", "LF-07.007-В/01.6")
tf_code = parent_tf.replace("LF-07.007-", "") if parent_tf else "В/01.6"

print(f"  TF: {tf_code}, LA: {la_id}")

current_skill_path = "profiles/analyst/skills/crossfunction-analyzer/SKILL.md"
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

# 2a. AGENTS.md — список профилей
agents_path = os.path.join(ARCH_DIR, "../AGENTS.md")
agents_lines = read_text_lines(agents_path)

profiles_inventory = []
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
            standard_raw = parts[4]
            standards = [s.strip() for s in standard_raw.replace(" + ", "+").replace(" ,", ",").replace(" +", "+").replace("+ ", "+").split("+")]
            standards = [s for s in standards if s]
            profiles_inventory.append({
                "profile_id": parts[1].lower().replace(" ", "-"),
                "name": parts[2] if parts[2] else "-",
                "role": parts[3],
                "standards": standards,
                "standards_raw": standard_raw
            })

print(f"  Profiles in AGENTS.md: {len(profiles_inventory)}")

# 2b. labor-function-to-skill-mapping.yaml
mapping_path = os.path.join(ARCH_DIR, "outputs/07.007/block-D/labor-function-to-skill-mapping.yaml")
mapping_data = read_file(mapping_path)
mappings = mapping_data.get("mappings", [])
print(f"  Mapping entries: {len(mappings)}")

# 2c. labor-coverage-registry.yaml
registry_path = os.path.join(ARCH_DIR, "outputs/07.007/labor-coverage-registry.yaml")
registry_data = read_file(registry_path)

# Определяем профили с данными: кто реально исполнял ТФ
# (skill_path вида profiles/regulator/skills/regulator-... даёт profile_id="regulator")
coverage_by_profile = {}
profiles_with_data = set()
for tf_key, tf_val in registry_data.items():
    if isinstance(tf_val, dict):
        profile = tf_val.get("executed_by", "unknown")
        coverage_by_profile.setdefault(profile, []).append({
            "tf": tf_key,
            "status": tf_val.get("status"),
            "tds_completed": tf_val.get("tds_completed")
        })
    # Определяем profile_id из skill_path
    sp = tf_val.get("skill_path", "")
    if sp:
        parts = sp.split("/")
        if len(parts) >= 3:
            pdir = parts[1]  # profiles/<profile>/skills/...
            if pdir in ("regulator", "architect", "analyst", ".default"):
                profiles_with_data.add(pdir)

print(f"  Registry entries: {len(registry_data)}")
print(f"  Profiles with coverage data: {sorted(profiles_with_data)}")

# 2d. A-01.6-info-context.yaml — контекст от regulator
context_path = os.path.join(ARCH_DIR, "outputs/07.007/block-A/A-01.6-info-context.yaml")
context = read_file(context_path)
context_found = bool(context)
print(f"  Context from regulator: {'found' if context_found else 'NOT FOUND'}")

# ── Шаг 3: Формирование карты взаимодействий ───────────────────────

output_path = output_files[0] if output_files else os.path.join(
    output_dir, "B-01.6-crossfunction-flow.yaml"
)
artifact_id = os.path.basename(output_path).replace(".yaml", "")

# 3a. profiles_inventory — добавляем информацию о покрытии
for p in profiles_inventory:
    pid = p["profile_id"]
    has_data = pid in profiles_with_data
    p["coverage_entries"] = len(coverage_by_profile.get(pid, []))
    p["coverage_status"] = "has_data" if has_data else "no_data"

# 3b. potential_interactions — матрица на основе общих стандартов
potential_interactions = []
for i, p1 in enumerate(profiles_inventory):
    for j, p2 in enumerate(profiles_inventory):
        if j <= i:
            continue
        shared = set(p1["standards"]) & set(p2["standards"])
        if shared:
            potential_interactions.append({
                "profile_a": p1["profile_id"],
                "profile_b": p2["profile_id"],
                "shared_standards": sorted(shared),
                "interaction_type": "cross_functional",
                "data_available": p1["coverage_status"] == "has_data" or p2["coverage_status"] == "has_data"
            })

# Явные связи на основе 07.007 (общий стандарт)
interactions_07_007 = [
    i for i in potential_interactions if "07.007" in i["shared_standards"]
]

print(f"  Potential interactions (all): {len(potential_interactions)}")
print(f"  Via 07.007: {len(interactions_07_007)}")

# 3c. data_gaps — профили без данных о покрытии
data_gaps = []
for p in profiles_inventory:
    if p["coverage_status"] == "no_data":
        data_gaps.append({
            "profile_id": p["profile_id"],
            "name": p["name"],
            "standard": p["standards_raw"],
            "reason": f"Нет записей в labor-coverage-registry.yaml для профиля {p['profile_id']}",
            "needed_for_tfs": [
                m["tf_code"] for m in mappings
                if m.get("coverage_status") in ("missing_skill", "partially_covered")
            ]
        })

print(f"  Data gaps: {len(data_gaps)}")

# 3d. recommendations
recommendations = []
if data_gaps:
    recommendations.append({
        "priority": "high",
        "what": "Сбор данных о работе профилей без покрытия",
        "profiles_affected": [g["profile_id"] for g in data_gaps],
        "action": "Создать skills для каждого профиля в соответствии с их профстандартами",
        "estimated_impact": f"Покрытие 07.007 увеличится с {len(registry_data)} до {len(registry_data) + len(data_gaps)} ТФ"
    })

recommendations.append({
    "priority": "medium",
    "what": "Уточнение кросс-функциональных связей",
    "profiles_affected": [i["profile_a"] for i in interactions_07_007] + [i["profile_b"] for i in interactions_07_007],
    "action": "Документировать handoff-точки между профилями, использующими 07.007",
    "estimated_impact": "Позволит переместить В/01.6 из partially_covered в covered"
})

recommendations.append({
    "priority": "low",
    "what": "Мониторинг появления новых профилей",
    "profiles_affected": [],
    "action": "При добавлении нового профиля в AGENTS.md — перезапустить crossfunction-analyzer",
    "estimated_impact": "Автоматическое обновление карты взаимодействий"
})

# ── Шаг 4: Сборка результата ───────────────────────────────────────

result = {
    "meta": {
        "artifact": artifact_id,
        "tf": tf_code,
        "la": la_id,
        "generated_by": "crossfunction-analyzer",
        "timestamp": os.popen("date -u +%Y-%m-%dT%H:%M:%SZ").read().strip(),
        "schema_ref": "crossfunction-flow-schema.yaml v1.0.0"
    },
    "body": {
        "profiles_inventory": profiles_inventory,
        "potential_interactions": potential_interactions,
        "data_gaps": data_gaps,
        "recommendations": recommendations
    },
    "quality": {
        "schema_valid": True,
        "sources_read": [],
        "context_available": context_found,
        "total_profiles": len(profiles_inventory),
        "profiles_with_data": sum(1 for p in profiles_inventory if p["coverage_status"] == "has_data"),
        "profiles_without_data": len(data_gaps)
    }
}

# ── Шаг 5: Валидация ───────────────────────────────────────────────

sources = []
if profiles_inventory:
    sources.append("../AGENTS.md")
if mapping_data:
    sources.append("outputs/07.007/block-D/labor-function-to-skill-mapping.yaml")
if registry_data:
    sources.append("outputs/07.007/labor-coverage-registry.yaml")
if context_found:
    sources.append("outputs/07.007/block-A/A-01.6-info-context.yaml")

required_fields = ["profiles_inventory", "potential_interactions", "data_gaps", "recommendations"]
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
print(f"  Profiles: {len(profiles_inventory)} ({result['quality']['profiles_with_data']} with data, {result['quality']['profiles_without_data']} gaps)")
print(f"  Interactions: {len(potential_interactions)}")
print(f"  Recommendations: {len(recommendations)}")
print(f"  Sources: {len(sources)}")
print(f"  Schema valid: {result['quality']['schema_valid']}")
```

## Схемы данных
- `../AGENTS.md` — список профилей AI-команды
- `outputs/07.007/block-D/labor-function-to-skill-mapping.yaml` — карта ТФ→навык
- `outputs/07.007/labor-coverage-registry.yaml` — реестр покрытия
- `outputs/07.007/block-A/A-01.6-info-context.yaml` — контекст блока A
- `outputs/07.007/block-D/new-skill-architecture-blueprint.md` (раздел 8 — эталонный шаблон)
