---
name: crossfunction-designer
description: >
  Разработка и усовершенствование кросс-функционального процесса (В/03.6).
  Превращает IDEF0-граф ТФ (B-02.6-graph-consistency.yaml) в исполняемую
  спецификацию: process definition, handoff contracts, control points,
  profile responsibilities, efficiency proposals.
version: 1.0.0
---

# crossfunction-designer

**Трудовое действие (В/03.6):** Разработка исполняемого кросс-функционального процесса и его контрольных точек

**Принцип:** Исполняемая спецификация строится ТОЛЬКО из данных графа, mapping и профстандарта. Никаких вымышленных процессов, контрактов и контрольных точек.

## ICOM

**Inputs:**
  - `outputs/07.007/block-B/B-02.6-graph-consistency.yaml` — IDEF0-граф ТФ (tf_nodes, handoff_edges, mechanisms)
  - `outputs/07.007/block-D/labor-function-to-skill-mapping.yaml` — ТФ → навык, статус покрытия
  - `docs/standards/07.007/otf-section-2.yaml` — блок B профстандарта (ТД В/03.6)
  - `docs/standards/07.007/otf-section-1.yaml`, `otf-section-3.yaml`, `otf-section-4.yaml` — ТД блоков A, C, D (для responsibilities)

**Outputs:**
  - `outputs/07.007/block-B/B-03.6-crossfunction-spec.yaml` — исполняемая спецификация кросс-функционального процесса

**Controls:**
  - `07.007` — профстандарт
  - `new-skill-architecture-blueprint.md` — архитектурный шаблон

**Mechanisms:**
  - `crossfunction-designer` (навык)

## Rules (DO / DON'T)

**ВСЕГДА ДЕЛАЙ:**
- DO: проверяй существование файла перед `open()`. Используй `os.path.exists()`.
- DO: оборачивай `yaml.safe_load()` в `try/except`.
- DO: извлекай данные ТОЛЬКО из реальных файлов (граф, mapping, otf-section).
- DO: для каждой ТФ без данных в графе явно указывай `data_gaps` — не выдумывай.
- DO: конвертируй node_id графа (`TF-07.007-A-01.6`) в tf_code формата профстандарта (`А/01.6`).

**КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО:**
- DON'T: генерировать вымышленные процессы, контракты, контрольные точки.
- DON'T: выдумывать timeout / временные параметры — их нет в графе, помечай как отсутствующие.
- DON'T: вызывать `subprocess.run(["hermes", ...])`.
- DON'T: использовать `input()` или интерактивный ввод.
- DON'T: писать за пределы `output_dir`.

## Thinking Process

1. Прочитаю `B-02.6-graph-consistency.yaml` — получу tf_nodes (mechanisms, inputs, outputs) и handoff_edges
2. Прочитаю `labor-function-to-skill-mapping.yaml` — получу статус покрытия и skill_path каждой ТФ
3. Прочитаю `otf-section-2.yaml` (блок B) — извлеку ТД В/03.6 для process_definition, control_points, efficiency_proposals
4. Прочитаю `otf-section-1/3/4.yaml` — извлеку ТД остальных ТФ для profile_responsibilities
5. Проверю: есть ли в графе секция gates для control_points? Если нет — зафиксирую data_gap
6. Сформирую result = {meta, body, quality} по шаблону blueprint
7. Проверю схему: все tf_code существуют в графе, все artifacts реальные
8. Запишу в output_files[0] (meta уже внутри файла)

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
def node_to_tf(node_id):
    """Конвертирует node_id графа 'TF-07.007-A-01.6' в tf_code 'А/01.6'."""
    prefix = "TF-07.007-"
    if not node_id.startswith(prefix):
        return node_id
    rest = node_id[len(prefix):]
    parts = rest.split("-", 1)
    lat_block = parts[0]
    num = parts[1] if len(parts) > 1 else ""
    lat_map = {'A': 'А', 'B': 'В', 'C': 'С'}
    block = lat_map.get(lat_block, lat_block)
    return f"{block}/{num}"

def split_td(text):
    """Разбивает длинное ТД на компактные пункты по смыслу."""
    return [text]

# ── Шаг 0: Pre-flight Check (идемпотентность, ADR-007) ────────────

la_id = body.get("la_id", "la-001")
parent_tf = body.get("parent_tf", "LF-07.007-В/03.6")
tf_code = parent_tf.replace("LF-07.007-", "") if parent_tf else "В/03.6"

print(f"  TF: {tf_code}, LA: {la_id}")

current_skill_path = "profiles/analyst/skills/crossfunction-designer/SKILL.md"
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
graph_data = read_file(os.path.join(
    ARCH_DIR, "outputs/07.007/block-B/B-02.6-graph-consistency.yaml"))
mapping_data = read_file(os.path.join(
    ARCH_DIR, "outputs/07.007/block-D/labor-function-to-skill-mapping.yaml"))
otf2 = read_file(os.path.join(ARCH_DIR, "docs/standards/07.007/otf-section-2.yaml"))
otf1 = read_file(os.path.join(ARCH_DIR, "docs/standards/07.007/otf-section-1.yaml"))
otf3 = read_file(os.path.join(ARCH_DIR, "docs/standards/07.007/otf-section-3.yaml"))
otf4 = read_file(os.path.join(ARCH_DIR, "docs/standards/07.007/otf-section-4.yaml"))

graph_body = graph_data.get("body", {})
graph_edges = graph_body.get("handoff_edges", [])
graph_nodes = {n["tf_code"]: n for n in graph_body.get("tf_nodes", [])}
mappings = mapping_data.get("mappings", [])

print(f"  Graph edges: {len(graph_edges)}, TF nodes: {len(graph_nodes)}")

# ТД из профстандарта: tf_code -> трудовые_действия
all_td = {}
for otf in (otf1, otf2, otf3, otf4):
    for lf in otf.get("labor_functions", []):
        code = lf.get("code", "")
        all_td[code] = lf.get("трудовые_действия", [])

td_v036 = all_td.get("В/03.6", [])
if not td_v036:
    print("  [WARN] ТД В/03.6 не найдено в otf-section-2.yaml — используем только данные графа")

# ── process_definition: из ТД В/03.6 ────────────────────────────────

def td_short(text):
    """Компактная формулировка ТД (до первого символа '(', убирает суффикс контекста)."""
    s = text.split("(")[0].strip()
    s = s.replace("организации", "").replace(" организации", "").strip()
    s = s.replace(" в соответствии с требованиями нормативно-методической документации", "").strip()
    s = re.sub(r"\s+", " ", s).strip()
    s = s.rstrip(",").strip()
    return s if s else text

process_steps = [td_short(t) for t in td_v036] if td_v036 else []
process_definition = {
    "tf_code": tf_code,
    "tf_name": "Разработка и усовершенствование кросс-функционального процесса",
    "description": (
        "Исполняемая спецификация кросс-функционального процесса, построенная из "
        "IDEF0-графа B-02.6 и ТД В/03.6 профстандарта 07.007."
    ) if td_v036 else (
        "ТД В/03.6 не найдено в otf-section-2.yaml. Спецификация построена только по данным графа."
    ),
    "steps": process_steps,
    "source_tf": tf_code,
    "source_actions": [t for t in td_v036],
}

# ── handoff_contracts: из handoff_edges графа ───────────────────────

handoff_contracts = []
for i, e in enumerate(graph_edges, 1):
    source_tf = node_to_tf(e.get("source", ""))
    target_tf = node_to_tf(e.get("target", ""))
    artifact = e.get("artifact", "")
    contract = {
        "contract_id": f"HO-{i:02d}",
        "source_tf": source_tf,
        "target_tf": target_tf,
        "artifact": artifact,
        "validation_rules": {
            "schema_valid": True,
        },
    }
    # В графе нет данных о timeout — не выдумываем, помечаем явно
    contract["timeout"] = None
    contract["data_gap"] = "timeout не задан в графе B-02.6"
    handoff_contracts.append(contract)

print(f"  Handoff contracts: {len(handoff_contracts)}")

# ── control_points: из ТД В/03.6 «Разработка контрольных точек» ────

# Проверяем наличие gates в графе (в B-02.6 их нет — фиксируем data_gap)
gates_found = bool(graph_body.get("gates"))
control_td = next((t for t in td_v036 if "контрольн" in t.lower()), "") if td_v036 else ""

control_points = []
for i, e in enumerate(graph_edges, 1):
    source_tf = node_to_tf(e.get("source", ""))
    target_tf = node_to_tf(e.get("target", ""))
    # auto_proceed: True, если у target есть навык (механизм в графе)
    target_node = graph_nodes.get(target_tf, {})
    auto_proceed = bool(target_node.get("mechanisms"))
    cp = {
        "checkpoint_id": f"CP-{i:02d}",
        "tf_code": target_tf,
        "checkpoint_name": (
            f"Контрольная точка приёмки артефакта от {source_tf}"
        ),
        "criteria": (
            [f"schema_valid: true для артефакта {e.get('artifact')}"]
            if not gates_found else graph_body["gates"]
        ),
        "auto_proceed": auto_proceed,
    }
    if gates_found:
        cp["gate_source"] = "graph B-02.6 gates"
    else:
        cp["gate_source"] = "derived from handoff edge"
        cp["data_gap"] = "gates не заданы в графе B-02.6 — критерии выведены из handoff-контракта"
    control_points.append(cp)

if not control_td:
    print("  [WARN] ТД «Разработка контрольных точек» не найдено — контрольные точки из рёбер графа")

print(f"  Control points: {len(control_points)}")

# ── profile_responsibilities: из mechanisms графа + ТД стандарта ────

profile_responsibilities = []
for m in mappings:
    m_tf = m.get("tf_code", "")
    skill_path = m.get("skill_path") or ""
    node = graph_nodes.get(m_tf, {})
    mechanisms = node.get("mechanisms", [])
    if not mechanisms:
        continue
    for mech in mechanisms:
        profile_responsibilities.append({
            "tf_code": m_tf,
            "tf_name": m.get("tf_name", ""),
            "profile": mech.get("profile", ""),
            "skill": mech.get("skill", ""),
            "skill_path": mech.get("skill_path", skill_path),
            "responsibilities": all_td.get(m_tf, []) or m.get("tf_actions", []),
            "source": "otf-section (ТД)" if m_tf in all_td else "mapping tf_actions (fallback)",
        })

print(f"  Profile responsibilities: {len(profile_responsibilities)}")

# ── efficiency_proposals: из ТД В/03.6 «Разработка предложений» ─────

eff_td = next((t for t in td_v036 if "предложений по повышению эффективности" in t.lower()), "") if td_v036 else ""
efficiency_proposals = []
if eff_td:
    # Из реальных данных графа: у ТФ без навыка — предложение их закрыть
    missing_tfs = [m.get("tf_code") for m in mappings
                   if m.get("coverage_status") == "missing_skill"]
    for mtf in missing_tfs:
        efficiency_proposals.append({
            "proposal_id": f"EP-{len(efficiency_proposals)+1:02d}",
            "tf_code": mtf,
            "proposal": (
                f"Создать навык для {mtf} — закрыть разрыв в кросс-функциональном pipeline"
            ),
            "basis": "pipeline_breaks в B-02.6",
            "source_td": eff_td,
        })
    # Из pipeline_breaks: неиспользуемые выходы
    for pb in graph_body.get("consistency", {}).get("pipeline_breaks", []):
        if len(efficiency_proposals) >= 3:
            break
        efficiency_proposals.append({
            "proposal_id": f"EP-{len(efficiency_proposals)+1:02d}",
            "tf_code": pb.get("tf", ""),
            "proposal": (
                f"Потреблять выход {pb.get('artifact')} — устранить разрыв pipeline"
            ),
            "basis": pb.get("issue", "pipeline_break"),
            "source_td": eff_td,
        })
else:
    print("  [WARN] ТД «Разработка предложений по повышению эффективности» не найдено")

print(f"  Efficiency proposals: {len(efficiency_proposals)}")

# ── data_gaps: что отсутствует в источниках ─────────────────────────

data_gaps = []
if not gates_found:
    data_gaps.append("gates не найдены в B-02.6 — контрольные точки выведены из рёбер")
if not td_v036:
    data_gaps.append("ТД В/03.6 не найдено в otf-section-2.yaml")
for c in handoff_contracts:
    if c.get("timeout") is None:
        data_gaps.append(f"timeout не задан для {c['contract_id']} ({c['artifact']})")
if not efficiency_proposals:
    data_gaps.append("ТД «Разработка предложений по повышению эффективности» не найдено в стандарте")

# ── Шаг 3: Валидация ───────────────────────────────────────────────

errors = []
if not process_definition["steps"]:
    errors.append("process_definition.steps пуст — нет ТД В/03.6")
if not handoff_contracts and graph_edges:
    errors.append("handoff_contracts пуст при наличии рёбер в графе")
for c in handoff_contracts:
    if c["source_tf"] not in graph_nodes and c["source_tf"] not in all_td:
        errors.append(f"handoff {c['contract_id']}: source {c['source_tf']} не найден в графе/стандарте")
    if c["target_tf"] not in graph_nodes and c["target_tf"] not in all_td:
        errors.append(f"handoff {c['contract_id']}: target {c['target_tf']} не найден в графе/стандарте")

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
        "generated_by": "crossfunction-designer",
        "timestamp": os.popen("date -u +%Y-%m-%dT%H:%M:%SZ").read().strip(),
        "schema_ref": "crossfunction-spec-schema.yaml v1.0.0",
    },
    "body": {
        "process_definition": process_definition,
        "handoff_contracts": handoff_contracts,
        "control_points": control_points,
        "profile_responsibilities": profile_responsibilities,
        "efficiency_proposals": efficiency_proposals,
        "data_gaps": data_gaps,
    },
    "quality": {
        "schema_valid": schema_valid,
        "sources_read": [
            "outputs/07.007/block-B/B-02.6-graph-consistency.yaml",
            "outputs/07.007/block-D/labor-function-to-skill-mapping.yaml",
            "docs/standards/07.007/otf-section-1.yaml",
            "docs/standards/07.007/otf-section-2.yaml",
            "docs/standards/07.007/otf-section-3.yaml",
            "docs/standards/07.007/otf-section-4.yaml",
        ],
        "warnings": [],
    },
}

write_ok = write_yaml(output_path, result)
if not write_ok:
    print("  [ERROR] failed to write spec")
    os._exit(1)

# ── Шаг 5: Отчёт ───────────────────────────────────────────────────

print(f"  Written: {output_path}")
print(f"  Schema valid: {schema_valid}")
print(f"  Data gaps: {len(data_gaps)}")
```

## Схемы данных

```yaml
# crossfunction-spec-schema.yaml v1.0.0
meta:
  artifact: str            # B-03.6-crossfunction-spec
  tf: str                  # В/03.6
  la: str                  # la-001
  generated_by: str        # crossfunction-designer
  timestamp: str           # ISO-8601 UTC
  schema_ref: str

body:
  process_definition:
    tf_code: str
    tf_name: str
    description: str
    steps: list[str]           # ТД В/03.6 (компактные)
    source_tf: str
    source_actions: list[str]  # полные ТД В/03.6
  handoff_contracts:
    - contract_id: str         # HO-01
      source_tf: str           # А/01.6
      target_tf: str           # А/02.6
      artifact: str            # полный путь артефакта
      validation_rules:
        schema_valid: bool     # всегда true
      timeout: null            # не задан в графе — data_gap
      data_gap: str
  control_points:
    - checkpoint_id: str       # CP-01
      tf_code: str
      checkpoint_name: str
      criteria: list[str]      # из gates графа или derived
      auto_proceed: bool
      gate_source: str         # graph gates | derived from handoff edge
      data_gap: str            # если gates отсутствуют
  profile_responsibilities:
    - tf_code: str
      tf_name: str
      profile: str             # regulator/architect/analyst
      skill: str
      skill_path: str
      responsibilities: list[str]   # ТД из otf-section
      source: str              # otf-section | mapping fallback
  efficiency_proposals:
    - proposal_id: str         # EP-01
      tf_code: str
      proposal: str
      basis: str               # pipeline_breaks | ТД
      source_td: str
  data_gaps: list[str]

quality:
  schema_valid: bool
  sources_read: list[str]
  warnings: list[str]
```
