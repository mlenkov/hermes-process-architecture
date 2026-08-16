---
name: maturity-assessor
description: >
  Анализ системы процессного управления (С/01.7). Читает
  labor-coverage-registry.yaml, labor-function-to-skill-mapping.yaml
  и ТД С/01.7 профстандарта, генерирует оценку зрелости по
  CMMI-подобной шкале (initial/defined/managed/optimizing)
  с scores, gaps и recommendations.
version: 1.0.0
---

# maturity-assessor

**Трудовое действие (С/01.7):** Анализ системы процессного управления для целей ее проектирования, усовершенствования и внедрения

**Принцип:** Оценка зрелости строится ТОЛЬКО на данных coverage registry и mapping. Никаких вымышленных оценок, моделей и процентов.

## ICOM

**Inputs:**
  - `outputs/07.007/labor-coverage-registry.yaml` — состояние покрытия (status, tds_completed, executed_by)
  - `outputs/07.007/block-D/labor-function-to-skill-mapping.yaml` — ТФ → навык, статус покрытия
  - `docs/standards/07.007/otf-section-3.yaml` — блок C профстандарта (ТД С/01.7)

**Outputs:**
  - `outputs/07.007/block-C/C-01.7-maturity-assessment.yaml` — оценка зрелости системы процессного управления

**Controls:**
  - `07.007` — профстандарт
  - `new-skill-architecture-blueprint.md` — архитектурный шаблон

**Mechanisms:**
  - `maturity-assessor` (навык)

## Rules (DO / DON'T)

**ВСЕГДА ДЕЛАЙ:**
- DO: проверяй существование файла перед `open()`. Используй `os.path.exists()`.
- DO: оборачивай `yaml.safe_load()` в `try/except`.
- DO: maturity_scores считай ТОЛЬКО из реальных статусов registry/mapping (covered/partially/missing).
- DO: gaps выводи из реальных missing_skill и partially_covered ТФ.
- DO: maturity_model описывай как CMMI-подобную шкалу (4 уровня) — фиксированную, не выдумывай.

**КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО:**
- DON'T: генерировать вымышленные проценты, оценки, показатели эффективности.
- DON'T: придумывать «экономическую эффективность» — данных нет, помечай как data_gap.
- DON'T: вызывать `subprocess.run(["hermes", ...])`.
- DON'T: использовать `input()` или интерактивный ввод.
- DON'T: писать за пределы `output_dir`.

## Thinking Process

1. Прочитаю `labor-coverage-registry.yaml` — получу status, tds_completed, executed_by по каждой ТФ
2. Прочитаю `labor-function-to-skill-mapping.yaml` — получу coverage_status, missing_skills, summary
3. Прочитаю `otf-section-3.yaml` — извлеку ТД С/01.7 для recommendations и criteria
4. Опишу maturity_model: CMMI-подобная шкала (initial/defined/managed/optimizing) — фиксированная
5. Соберу current_state из registry: сколько covered/partially/missing, по блокам
6. Посчитаю maturity_scores: % за каждый уровень на основе реальных статусов покрытия
7. Выведу gaps из missing_skill + partially_covered ТФ
8. Сформирую recommendations из ТД С/01.7, привязанные к gaps
9. Проверю: каждый score основан на реальных данных, никаких выдуманных цифр
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
parent_tf = body.get("parent_tf", "LF-07.007-С/01.7")
tf_code = parent_tf.replace("LF-07.007-", "") if parent_tf else "С/01.7"

print(f"  TF: {tf_code}, LA: {la_id}")

current_skill_path = "profiles/mais/skills/maturity-assessor/SKILL.md"
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
registry = read_file(os.path.join(ARCH_DIR, "outputs/07.007/labor-coverage-registry.yaml"))
mapping_data = read_file(os.path.join(
    ARCH_DIR, "outputs/07.007/block-D/labor-function-to-skill-mapping.yaml"))
otf3 = read_file(os.path.join(ARCH_DIR, "docs/standards/07.007/otf-section-3.yaml"))

mappings = mapping_data.get("mappings", [])
summary = mapping_data.get("summary", {})
print(f"  Registry entries: {len(registry)}, Mapping entries: {len(mappings)}")

# ТД С/01.7 из профстандарта
td_s017 = []
for lf in otf3.get("labor_functions", []):
    if lf.get("code") == "С/01.7":
        td_s017 = lf.get("трудовые_действия", [])
        break
if not td_s017:
    print("  [WARN] ТД С/01.7 не найдено в otf-section-3.yaml")

# ── maturity_model: CMMI-подобная шкала (фиксированная) ───────────

maturity_model = {
    "name": "CMMI-подобная шкала зрелости процесса управления",
    "levels": [
        {
            "level_id": "M1",
            "level_name": "initial",
            "description": "Процессы непредсказуемы, слабо документированы",
        },
        {
            "level_id": "M2",
            "level_name": "defined",
            "description": "Процессы стандартизированы и документированы",
        },
        {
            "level_id": "M3",
            "level_name": "managed",
            "description": "Процессы измеряются и контролируются",
        },
        {
            "level_id": "M4",
            "level_name": "optimizing",
            "description": "Процессы непрерывно улучшаются",
        },
    ],
    "scoring_basis": "Покрытие ТФ навыками из labor-coverage-registry.yaml и mapping",
}

# ── current_state: из coverage registry ────────────────────────────

total = len(mappings)
covered = summary.get("covered", 0)
partially = summary.get("partially_covered", 0)
missing = summary.get("missing_skill", 0)
total_tfs = summary.get("total_tfs", total)

# По блокам из mapping
blocks = {}
for m in mappings:
    blk = m["tf_code"].split("/")[0]
    blocks.setdefault(blk, {"total": 0, "covered": 0, "partially": 0, "missing": 0})
    blocks[blk]["total"] += 1
    status = m.get("coverage_status", "")
    if status == "covered":
        blocks[blk]["covered"] += 1
    elif status == "partially_covered":
        blocks[blk]["partially"] += 1
    elif status == "missing_skill":
        blocks[blk]["missing"] += 1

current_state = {
    "total_tfs": total_tfs,
    "covered": covered,
    "partially_covered": partially,
    "missing_skill": missing,
    "coverage_pct": round(covered / total_tfs * 100, 1) if total_tfs else 0.0,
    "by_block": {
        blk: f"{v['covered']}/{v['total']} covered, {v['partially']} partially, {v['missing']} missing"
        for blk, v in sorted(blocks.items())
    },
    "source": "labor-coverage-registry.yaml + labor-function-to-skill-mapping.yaml (summary)",
}

print(f"  Current state: {covered} covered / {partially} partially / {missing} missing (of {total_tfs})")

# ── maturity_scores: % на уровень ─────────────────────────────────

# Логика (детерминированная, из реальных статусов):
#   initial  = 100% всегда (система существует, есть реестр)
#   defined  = доля ТФ с навыком (covered + partially) / total
#   managed  = доля covered ТФ / total (измеряемых, полностью покрытых)
#   optimizing = покрытие PDCA-циклов: доля ТФ блоков A+D (управляемых) или покрытие D-блока
defined_pct = round((covered + partially) / total_tfs * 100, 1) if total_tfs else 0.0
managed_pct = round(covered / total_tfs * 100, 1) if total_tfs else 0.0
block_d = blocks.get("D", {})
optimizing_pct = round(block_d.get("covered", 0) / block_d.get("total", 1) * 100, 1) if block_d.get("total") else 0.0

maturity_scores = [
    {"level_id": "M1", "level_name": "initial", "score_pct": 100.0, "basis": "Система существует: registry и mapping заполнены"},
    {"level_id": "M2", "level_name": "defined", "score_pct": defined_pct, "basis": f"{covered + partially}/{total_tfs} ТФ имеют навык"},
    {"level_id": "M3", "level_name": "managed", "score_pct": managed_pct, "basis": f"{covered}/{total_tfs} ТФ полностью покрыты"},
    {"level_id": "M4", "level_name": "optimizing", "score_pct": optimizing_pct, "basis": f"Блок D (трансформация): {block_d.get('covered', 0)}/{block_d.get('total', 0)} covered"},
]

print(f"  Maturity scores: initial={maturity_scores[0]['score_pct']}, defined={defined_pct}, managed={managed_pct}, optimizing={optimizing_pct}")

# ── gaps: из real missing/partially ────────────────────────────────

gaps = []
for m in mappings:
    status = m.get("coverage_status", "")
    tf = m.get("tf_code", "")
    if status == "missing_skill":
        gaps.append({
            "tf_code": tf,
            "tf_name": m.get("tf_name", ""),
            "type": "missing_skill",
            "description": f"ТФ {tf} не имеет навыка",
        })
    elif status == "partially_covered":
        gaps.append({
            "tf_code": tf,
            "tf_name": m.get("tf_name", ""),
            "type": "partially_covered",
            "description": f"ТФ {tf} покрыта частично: {m.get('coverage_note', '')[:80]}".strip(),
        })

print(f"  Gaps: {len(gaps)}")

# ── recommendations: из ТД С/01.7 + gaps ───────────────────────────

# ТД, из которых берём формулировки рекомендаций
def td_short(text):
    s = text.split("(")[0].strip()
    s = re.sub(r"\s+", " ", s).strip()
    return s

recommendations = []
for g in gaps:
    if g["type"] == "missing_skill":
        rec = (
            f"Создать навык для {g['tf_code']} ({g['tf_name']}) — закрыть разрыв покрытия"
        )
        basis = "missing_skill в mapping"
    else:
        rec = (
            f"Повысить покрытие {g['tf_code']} ({g['tf_name']}) — расширить навык до полного"
        )
        basis = "partially_covered в mapping"
    recommendations.append({
        "recommendation_id": f"R-{len(recommendations)+1:02d}",
        "tf_code": g["tf_code"],
        "recommendation": rec,
        "basis": basis,
        "source_td": next((t for t in td_s017 if "Оценка текущих показателей" in t), "") or "ТД С/01.7",
    })

# Рекомендация про целевые показатели (из ТД «Определение целевых показателей»)
target_td = next((t for t in td_s017 if "Определение целевых показателей" in t), "")
if target_td and total_tfs:
    recommendations.append({
        "recommendation_id": f"R-{len(recommendations)+1:02d}",
        "tf_code": "system",
        "recommendation": (
            f"Определить целевые показатели зрелости (уровень managed >= 80% covered, "
            f"optimizing >= 50% D-блока)"
        ),
        "basis": "targets не определены в registry",
        "source_td": target_td,
    })

print(f"  Recommendations: {len(recommendations)}")

# ── data_gaps ──────────────────────────────────────────────────────

data_gaps = []
if not td_s017:
    data_gaps.append("ТД С/01.7 не найдено в otf-section-3.yaml")
data_gaps.append("Экономическая и функциональная эффективность системы управления не измеряется — данных нет в registry")

# ── Шаг 3: Валидация ───────────────────────────────────────────────

errors = []
if not maturity_scores:
    errors.append("maturity_scores пуст")
for s in maturity_scores:
    if not (0 <= s["score_pct"] <= 100):
        errors.append(f"score {s['level_name']} вне диапазона 0-100: {s['score_pct']}")
if not current_state:
    errors.append("current_state пуст")

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
        "generated_by": "maturity-assessor",
        "timestamp": os.popen("date -u +%Y-%m-%dT%H:%M:%SZ").read().strip(),
        "schema_ref": "maturity-assessment-schema.yaml v1.0.0",
    },
    "body": {
        "maturity_model": maturity_model,
        "current_state": current_state,
        "maturity_scores": maturity_scores,
        "gaps": gaps,
        "recommendations": recommendations,
        "data_gaps": data_gaps,
    },
    "quality": {
        "schema_valid": schema_valid,
        "sources_read": [
            "outputs/07.007/labor-coverage-registry.yaml",
            "outputs/07.007/block-D/labor-function-to-skill-mapping.yaml",
            "docs/standards/07.007/otf-section-3.yaml",
        ],
        "warnings": [],
    },
}

write_ok = write_yaml(output_path, result)
if not write_ok:
    print("  [ERROR] failed to write maturity assessment")
    os._exit(1)

# ── Шаг 5: Отчёт ───────────────────────────────────────────────────

print(f"  Written: {output_path}")
print(f"  Schema valid: {schema_valid}")
```

## Схемы данных

```yaml
# maturity-assessment-schema.yaml v1.0.0
meta:
  artifact: str            # C-01.7-maturity-assessment
  tf: str                  # С/01.7
  la: str                  # la-001
  generated_by: str        # maturity-assessor
  timestamp: str           # ISO-8601 UTC
  schema_ref: str

body:
  maturity_model:
    name: str
    levels:
      - level_id: str      # M1..M4
        level_name: str    # initial/defined/managed/optimizing
        description: str
    scoring_basis: str
  current_state:
    total_tfs: int
    covered: int
    partially_covered: int
    missing_skill: int
    coverage_pct: float
    by_block: dict         # блок → "x/y covered, p partially, m missing"
    source: str
  maturity_scores:
    - level_id: str
      level_name: str
      score_pct: float     # 0-100
      basis: str           # формула из реальных статусов
  gaps:
    - tf_code: str
      tf_name: str
      type: str            # missing_skill | partially_covered
      description: str
  recommendations:
    - recommendation_id: str
      tf_code: str
      recommendation: str
      basis: str
      source_td: str
  data_gaps: list[str]

quality:
  schema_valid: bool
  sources_read: list[str]
  warnings: list[str]
```
