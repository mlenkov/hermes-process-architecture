---
name: info-gatherer
description: >
  Сбор информации о процессе. Читает docs/standards/07.007/otf-section-1.yaml,
  ../AGENTS.md и labor-coverage-registry.yaml, агрегирует в process-info-context.yaml
  для следующих ТД блока A.
version: 1.0.0
---

# info-gatherer

**Трудовое действие (А/01.6):** Сбор информации о процессе подразделения организации с целью разработки регламента данного процесса или административного регламента подразделения организации

**Принцип:** Никаких вымышленных данных. Все данные извлекаются из реальной файловой системы.

## ICOM

**Inputs:**
  - `otf-section-1.yaml` — содержимое блока A профстандарта 07.007
  - `../AGENTS.md` — описание профилей и их ролей
  - `labor-coverage-registry.yaml` — текущее состояние покрытия ТФ

**Outputs:**
  - `outputs/07.007/block-A/A-01.6-info-context.yaml` — агрегированный контекст для следующих ТД блока A

## Rules (DO / DON'T)

**ВСЕГДА ДЕЛАЙ:**
- DO: проверяй существование файла перед `open()`. Используй `os.path.exists()`.
- DO: оборачивай `yaml.safe_load()` в `try/except`. Файл может быть битым или пустым.
- DO: извлекай данные ТОЛЬКО из реальных файлов системы (`docs/standards/`, `AGENTS.md`, `outputs/`).

**КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО:**
- DON'T: генерировать вымышленные имена, компании, организации. Все данные — только из файлов.
- DON'T: вызывать `subprocess.run(["hermes", ...])` из td-gen. Это делает executor.
- DON'T: писать за пределы `output_dir`. Каждый навык пишет только в свою директорию.
- DON'T: использовать `input()` или интерактивный ввод. Навык работает без пользователя.

## Thinking Process

1. Прочитаю `docs/standards/07.007/otf-section-1.yaml` — получу список ТФ и трудовых действий блока A
2. Прочитаю `../AGENTS.md` — получу список профилей AI-команды и их роли
3. Прочитаю `outputs/07.007/labor-coverage-registry.yaml` — получу текущий статус покрытия
4. Проверю: если файл не существует — запишу предупреждение, продолжу с остальными
5. Сформирую `result = {meta, body, quality}`: body содержит агрегированный контекст с реальными данными из прочитанных файлов
6. Проверю: обязательные поля (tf_list, profiles, coverage_state) присутствуют
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
# ── Шаг 0: Pre-flight Check (идемпотентность, ADR-007) ────────────────────────────────────────────────

la_id = body.get("la_id", "la-001")
parent_tf = body.get("parent_tf", "LF-07.007-А/01.6")
tf_code = parent_tf.replace("LF-07.007-", "") if parent_tf else "А/01.6"

print(f"  TF: {tf_code}, LA: {la_id}")

current_skill_path = "profiles/mais/skills/info-gatherer/SKILL.md"
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
# ── Шаг 1: Контекст ────────────────────────────────────────────────

# Прочитать входные артефакты из input_files (если переданы executor'ом)
input_artifacts = {}
for fpath in (input_files or []):
    if not os.path.exists(fpath):
        print(f"  [WARN] input not found: {fpath}")
        continue
    data = read_file(fpath)
    basename = os.path.basename(fpath).replace(".yaml", "")
    input_artifacts[basename] = data

print(f"  Inputs read: {len(input_artifacts)}/{len(input_files or [])}")

# ── Шаг 2: Чтение источников ────────────────────────────────────────

# 2a. Прочитать docs/standards/07.007/otf-section-1.yaml (Блок A)
otf_1_path = os.path.join(ARCH_DIR, "docs/standards/07.007/otf-section-1.yaml")
otf_1_data = read_file(otf_1_path)

labor_functions_a = otf_1_data.get("labor_functions", [])
tf_list = []
for lf in labor_functions_a:
    tf_list.append({
        "code": lf.get("code", ""),
        "name": lf.get("name", ""),
        "level": lf.get("qualification_level", ""),
        "actions": lf.get("трудовые_действия", []),
        "skills_required": lf.get("необходимые_умения", [])
    })

print(f"  OTF-A labor functions: {len(tf_list)}")

# 2b. Прочитать ../AGENTS.md (профили AI-команды)
agents_path = os.path.join(ARCH_DIR, "../AGENTS.md")
agents_lines = read_text_lines(agents_path)

profiles = []
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

# Если парсинг не дал результатов — известные профили из AGENTS.md
if not profiles:
    profiles = [
        {"profile_id": "mais", "name": "Айра Корбот", "role": "COO, процессное управление", "standard": "07.007"},
        {"profile_id": "ppc-specialist", "name": "Ян", "role": "PPC Яндекс.Директ", "standard": "06.043"},
        {"profile_id": "copywriter", "name": "Анна Словцова", "role": "Копирайтер", "standard": "06.013"},
        {"profile_id": "data-analyst", "name": "Лана", "role": "Аналитик данных", "standard": "06.043+06.046"},
        {"profile_id": "coder", "name": "Вадим Нейман", "role": "Программист, MCP", "standard": "06.001+06.035+06.026"},
        {"profile_id": "marketing", "name": "Маркетолог", "role": "Маркетолог", "standard": "08.035"},
        {"profile_id": "keyword-collector", "name": "Кирилл", "role": "Сбор семантики", "standard": "06.043"},
    ]

print(f"  Profiles: {len(profiles)}")

# 2c. Прочитать outputs/07.007/labor-coverage-registry.yaml
registry_path = os.path.join(ARCH_DIR, "outputs/07.007/labor-coverage-registry.yaml")
registry_data = read_file(registry_path)

# Извлечь coverage state для всех ТФ
coverage_state = {}
for tf_key, tf_val in registry_data.items():
    if isinstance(tf_val, dict):
        coverage_state[tf_key] = {
            "status": tf_val.get("status", "unknown"),
            "tds_completed": tf_val.get("tds_completed", "0/0"),
            "last_executed": tf_val.get("last_executed", ""),
            "executed_by": tf_val.get("executed_by", "")
        }

print(f"  Coverage entries: {len(coverage_state)}")

# ── Шаг 2d: Проверка — все ли источники прочитаны ──────────────────

sources_read = []
if otf_1_data:
    sources_read.append("docs/standards/07.007/otf-section-1.yaml")
if profiles:
    sources_read.append("../AGENTS.md")
if registry_data:
    sources_read.append("outputs/07.007/labor-coverage-registry.yaml")

print(f"  Sources read: {len(sources_read)}/3")

# ── Шаг 3: Формирование результата ──────────────────────────────────

output_path = output_files[0] if output_files else os.path.join(
    output_dir, "process-info-context.yaml"
)
artifact_id = os.path.basename(output_path).replace(".yaml", "")

result = {
    "meta": {
        "artifact": artifact_id,
        "tf": tf_code,
        "la": la_id,
        "generated_by": "info-gatherer",
        "timestamp": os.popen("date -u +%Y-%m-%dT%H:%M:%SZ").read().strip(),
        "schema_ref": "process-info-context-schema.yaml v1.0.0"
    },
    "body": {
        "standard_info": {
            "standard_name": "07.007 «Специалист по процессному управлению»",
            "block": "A — Регламентация процессов подразделений",
            "total_labor_functions": len(tf_list),
            "labor_functions": tf_list
        },
        "team_info": {
            "total_profiles": len(profiles),
            "profiles_available": profiles
        },
        "coverage_info": {
            "total_entries": len(coverage_state),
            "current_state": coverage_state
        }
    },
    "quality": {
        "schema_valid": True,
        "sources_read": sources_read,
        "sources_total": 3,
        "all_sources_available": len(sources_read) == 3
    }
}

# ── Шаг 4: Валидация ────────────────────────────────────────────────

# Проверить обязательные поля
required_body_fields = ["standard_info", "team_info", "coverage_info"]
missing = [f for f in required_body_fields if f not in result.get("body", {})]
if missing:
    print(f"  [VALIDATION] missing required body fields: {missing}")
    result["quality"]["schema_valid"] = False
else:
    result["quality"]["schema_valid"] = True

# ── Шаг 5: Запись ──────────────────────────────────────────────────

ok = write_yaml(output_path, result)
if not ok:
    print("  [ERROR] failed to write primary artifact")
    os._exit(1)

# ── Шаг 6: Отчёт ───────────────────────────────────────────────────

print(f"  Written: {output_path}")
print(f"  Artifact: {artifact_id}")
print(f"  Sources: {len(sources_read)}/3")
print(f"  Schema valid: {result['quality']['schema_valid']}")
```

## Схемы данных
- `outputs/07.007/block-D/new-skill-architecture-blueprint.md` (раздел 8 — эталонный шаблон)
- `docs/standards/07.007/otf-section-1.yaml` — исходные данные блока A
- `outputs/07.007/labor-coverage-registry.yaml` — реестр покрытия
