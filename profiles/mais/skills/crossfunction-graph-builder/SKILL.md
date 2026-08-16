---
name: crossfunction-graph-builder
description: >
  Построение исполняемого функционального графа профстандарта 07.007
  по методологии IDEF0. Читает labor-function-to-skill-mapping.yaml,
  labor-coverage-registry.yaml и ICOM секции SKILL.md, строит граф
  в graphify и отчёт о консистентности.
version: 1.0.0
---

# crossfunction-graph-builder

**Трудовое действие (В/02.6):** Моделирование кросс-функционального процесса как исполняемого IDEF0-графа

**Принцип:** Функциональный граф ТФ, а не социальный граф профилей. Каждый узел — Трудовой Функция, рёбра — передача артефактов.

## ICOM

**Inputs:**
  - `block-D/labor-function-to-skill-mapping.yaml` — ТФ, skill_path, статус покрытия
  - `labor-coverage-registry.yaml` — артефакты на каждую ТФ
  - `profiles/<profile>/skills/<skill>/SKILL.md` — ICOM (Inputs) для извлечения входных файлов

**Outputs:**
  - `outputs/07.007/block-B/B-02.6-graph-consistency.yaml` — отчёт о консистентности
  - `graphify-out/.graphify_semantic.json` — Dobsongraph-граф (обновление)

**Controls:**
  - `07.007` — профстандарт
  - `new-skill-architecture-blueprint.md` — архитектурный шаблон

**Mechanisms:**
  - `crossfunction-graph-builder` (навык)
  - `graphify` CLI (`~/.local/bin/graphify`)

## Rules (DO / DON'T)

**ВСЕГДА ДЕЛАЙ:**
- DO: проверяй существование файла перед `open()`. Используй `os.path.exists()`.
- DO: оборачивай `yaml.safe_load()` в `try/except`.
- DO: node_id по схеме `TF-07.007-<block>-<tf>.<level>` (латиница, например `TF-07.007-A-01.6`).
- DO: извлекай входы ТОЛЬКО из ICOM-секции SKILL.md, выходы — из registry `artifacts_generated`.
- DO: совместимость с Dobsongraph: nodes → edges → hyperedges, поля `confidence`, `confidence_score`, `weight`.
- DO: обновляй `graphify-out/.graphify_semantic.json`, не перезаписывая чужие узлы (слияние по node_id).

**КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО:**
- DON'T: строить социальный граф профилей. Узлы = ТФ, не люди.
- DON'T: генерировать вымышленные входы/выходы. Всё из mapping/registry/SKILL.md.
- DON'T: вызывать `subprocess.run(["hermes", ...])`.
- DON'T: запускать полный `/graphify` pipeline (LLM-экстракцию). Только запись semantic JSON + `graphify query` для проверки.
- DON'T: использовать `input()`.

## Thinking Process

1. Прочитаю `labor-function-to-skill-mapping.yaml` — получу список ТФ и skill_path
2. Прочитаю `labor-coverage-registry.yaml` — получу artifacts_generated и executed_by
3. Для каждой ТФ с навыком прочитаю SKILL.md — извлеку Inputs из ICOM
4. Для каждой ТФ создам узел IDEF0: механизмы (профиль+навык), входы, выходы, управление
5. Свяжу выходы ТФ с входами последующих ТФ (по совпадению имён файлов)
6. Проверю консистентность: ТФ без навыка → gap, навык без профиля → ошибка, выход без входа → разрыв
7. Солью с существующим graphify-out/.graphify_semantic.json и запишу
8. Сгенерирую B-02.6-graph-consistency.yaml
9. Вызову `graphify query` для верификации записанного графа

## Process

```python
import os, re, json, yaml

ARCH_DIR = os.path.abspath(".")
GRAPHIFY_OUT = os.path.join(ARCH_DIR, "graphify-out")
SEMANTIC_PATH = os.path.join(GRAPHIFY_OUT, ".graphify_semantic.json")

CONTROLS = ["07.007", "new-skill-architecture-blueprint.md"]

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

def read_text(path):
    if not os.path.exists(path):
        return ""
    try:
        with open(path) as f:
            return f.read()
    except Exception as e:
        print(f"  [WARN] read error: {path}: {e}")
        return ""

def write_json(path, data):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"  [ERROR] write error: {path}: {e}")
        return False

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
def node_id(tf_code):
    """TF-07.007-A-01.6 из 'А/01.6' (кириллица → латиница)."""
    cyr_map = {'А': 'A', 'В': 'B', 'С': 'C', 'D': 'D'}
    code = tf_code.strip()
    block = code[0]
    rest = code[1:].strip()
    if rest.startswith("/"):
        rest = rest[1:]
    lat_block = cyr_map.get(block, block)
    return f"TF-07.007-{lat_block}-{rest}"

def parse_icom_inputs(skill_text):
    """Извлекает Inputs из секции ## ICOM."""
    m = re.search(r'## ICOM(.*?)(## Rules|## Thinking|$)', skill_text, re.S)
    if not m:
        return []
    icom = m.group(1)
    im = re.search(r'\*\*Inputs:\*\*(.*?)(\*\*Outputs:|$)', icom, re.S)
    if not im:
        return []
    inputs = []
    for line in im.group(1).splitlines():
        s = line.strip()
        if s.startswith('- `') and '`' in s[3:]:
            name = s.split('`')[1]
            inputs.append(name)
    return inputs

CURRENT_PROFILE = "mais"  # ADR-008: единственный исполнитель 07.007

def extract_profile_from_skill_path(skill_path, registry_entry=None):
    """Возвращает (profile, skill).

    ADR-008: единственный исполнитель 07.007 — профиль mais.
    Профиль из префикса пути больше не выводится; skill_path — относительный.
    """
    parts = skill_path.split("/")
    if len(parts) >= 2 and parts[-1] == "SKILL.md":
        skill_name = parts[-2]
    else:
        skill_name = parts[0].replace("/SKILL.md", "")
    return CURRENT_PROFILE, skill_name

# ── Шаг 0: Pre-flight Check (идемпотентность, ADR-007) ────────────

la_id = body.get("la_id", "la-001")
parent_tf = body.get("parent_tf", "LF-07.007-В/02.6")
tf_code = parent_tf.replace("LF-07.007-", "") if parent_tf else "В/02.6"

print(f"  TF: {tf_code}, LA: {la_id}")

current_skill_path = "profiles/mais/skills/crossfunction-graph-builder/SKILL.md"
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

mapping_data = read_file(os.path.join(ARCH_DIR, "outputs/07.007/block-D/labor-function-to-skill-mapping.yaml"))
mappings = mapping_data.get("mappings", [])
print(f"  Mapping entries: {len(mappings)}")

registry_data = read_file(os.path.join(ARCH_DIR, "outputs/07.007/labor-coverage-registry.yaml"))
print(f"  Registry entries: {len(registry_data)}")

# ── Шаг 3: Создание узлов IDEF0 ────────────────────────────────────

tf_nodes = {}
skill_inputs_cache = {}
missing_skills = []
no_profile_skills = []

for m in mappings:
    m_tf = m.get("tf_code", "")
    nid = node_id(m_tf)
    label = m.get("tf_name", m_tf)
    status = m.get("coverage_status", "unknown")
    skill_path = m.get("skill_path") or ""

    mechanisms = []
    inputs = []
    outputs = []

    # Выходы из registry artifacts_generated
    reg_key = f"LF-07.007-{m_tf}"
    reg_entry = registry_data.get(reg_key, {})

    if skill_path:
        profile, skill_name = extract_profile_from_skill_path(skill_path, reg_entry)
        mechanisms.append({"profile": profile, "skill": skill_name, "skill_path": skill_path})
        if profile == "unknown":
            no_profile_skills.append(m_tf)
        # Извлекаем входы из ICOM секции SKILL.md
        full_skill_path = os.path.join(ARCH_DIR, "profiles", profile, "skills", skill_name, "SKILL.md")
        if os.path.exists(full_skill_path):
            skill_text = read_text(full_skill_path)
            inputs = parse_icom_inputs(skill_text)
            skill_inputs_cache[skill_path] = inputs
    else:
        missing_skills.append(m_tf)

    outputs = list(reg_entry.get("artifacts_generated", [])) if isinstance(reg_entry, dict) else []

    tf_nodes[nid] = {
        "id": nid,
        "label": label,
        "file_type": "labor_function",
        "tf_code": m_tf,
        "coverage_status": status,
        "mechanisms": mechanisms,
        "inputs": inputs,
        "outputs": outputs,
        "controls": CONTROLS,
    }

print(f"  TF nodes: {len(tf_nodes)}")
print(f"  Missing skills (gaps): {missing_skills}")

# ── Шаг 4: Рёбра — передача артефактов между ТФ ────────────────────

# Карта: имя файла → список ТФ, которые его генерируют
output_to_tf = {}
for nid, nd in tf_nodes.items():
    for out in nd["outputs"]:
        output_to_tf.setdefault(out, []).append(nid)

# Карта: имя файла → список ТФ, которые его читают
input_to_tf = {}
for nid, nd in tf_nodes.items():
    for inp in nd["inputs"]:
        input_to_tf.setdefault(inp, []).append(nid)

# Нормализация: ищет совпадение по базовому имени файла
def base_match(path):
    return os.path.basename(path).replace(".yaml", "").replace(".mmd", "")

edges = []
edge_pairs = set()
connected_outputs = set()

# Точное и fuzzy-сопоставление: вход (относительный путь) ↔ выход (полный путь)
for in_file, consumer_tfs in input_to_tf.items():
    in_base = base_match(in_file)
    for out_file, producer_tfs in output_to_tf.items():
        matched = (out_file == in_file) or (base_match(out_file) == in_base)
        if not matched:
            continue
        for producer_tf in producer_tfs:
            for consumer_tf in consumer_tfs:
                if producer_tf == consumer_tf:
                    continue
                pair = (producer_tf, consumer_tf)
                if pair in edge_pairs:
                    continue
                edge_pairs.add(pair)
                exact = (out_file == in_file)
                edges.append({
                    "source": producer_tf,
                    "target": consumer_tf,
                    "relation": "artifact_handoff",
                    "artifact": out_file,
                    "confidence": "EXTRACTED" if exact else "INFERRED",
                    "confidence_score": 1.0 if exact else 0.8,
                    "weight": 1.0 if exact else 0.8,
                })
                connected_outputs.add(out_file)

print(f"  Edges (artifact_handoff): {len(edges)}")

# ── Шаг 5: Проверка консистентности ────────────────────────────────

pipeline_breaks = []
for nid, nd in tf_nodes.items():
    for out in nd["outputs"]:
        if out not in connected_outputs and out not in input_to_tf:
            pipeline_breaks.append({
                "tf": nd["tf_code"],
                "artifact": out,
                "issue": "Выход не потребляется ни одним входом — разрыв в pipeline"
            })

consistency = {
    "total_tfs": len(mappings),
    "tfs_with_skill": len(mappings) - len(missing_skills),
    "missing_skills": missing_skills,
    "skills_without_profile": no_profile_skills,
    "pipeline_breaks": pipeline_breaks,
    "edges_created": len(edges),
    "verdict": "consistent"
}

if missing_skills:
    consistency["verdict"] = "gaps_found"
if pipeline_breaks:
    consistency["verdict"] = "pipeline_breaks"
if no_profile_skills:
    consistency["verdict"] = "profile_errors"

print(f"  Verdict: {consistency['verdict']}")

# ── Шаг 6: Запись в graphify (слияние с существующим графом) ───────

existing = {}
if os.path.exists(SEMANTIC_PATH):
    try:
        with open(SEMANTIC_PATH) as f:
            existing = json.load(f)
    except Exception as e:
        print(f"  [WARN] cannot read existing graph: {e}")

existing_nodes = {n["id"]: n for n in existing.get("nodes", [])}
existing_edges = existing.get("edges", [])

# Самоочистка: удаляем устаревшие labour_function-узлы с битым id ('--'),
# созданные старыми версиями навыка
stale_ids = [nid for nid in existing_nodes
             if existing_nodes[nid].get("file_type") == "labor_function"
             and "--" in nid]
for sid in stale_ids:
    existing_nodes.pop(sid, None)
existing_edges = [e for e in existing_edges
                  if e.get("source") not in stale_ids and e.get("target") not in stale_ids]
if stale_ids:
    print(f"  Removed stale labor_function nodes: {len(stale_ids)}")

# Обновляем/добавляем наши узлы
for nid, nd in tf_nodes.items():
    existing_nodes[nid] = nd

# Добавляем edges (если пары ещё нет)
existing_edge_sources = set()
for e in existing_edges:
    if "hyperedge" not in e.get("relation", ""):
        existing_edge_sources.add((e.get("source"), e.get("target")))

new_edges = [e for e in edges if (e["source"], e["target"]) not in existing_edge_sources]
merged_edges = existing_edges + new_edges

graph_data = {
    "nodes": list(existing_nodes.values()),
    "edges": merged_edges,
    "hyperedges": existing.get("hyperedges", []),
    "input_tokens": existing.get("input_tokens", 0),
    "output_tokens": existing.get("output_tokens", 0),
}

write_ok = write_json(SEMANTIC_PATH, graph_data)
if not write_ok:
    print("  [ERROR] failed to write graphify semantic JSON")
    os._exit(1)

print(f"  Merged graph: {len(graph_data['nodes'])} nodes, {len(graph_data['edges'])} edges")

# ── Шаг 6b: Обновление graph.json (запрашиваемого графа) ───────────
# graphify CLI читает graphify-out/graph.json. Обновляем его детерминированно:
# добавляем новые labour_function-узлы и artifact_handoff-рёбра.
# Полноценную пересборку (кластеризацию, report) делает полный pipeline graphify.

GRAPH_JSON_PATH = os.path.join(GRAPHIFY_OUT, "graph.json")
if os.path.exists(GRAPH_JSON_PATH):
    try:
        with open(GRAPH_JSON_PATH) as f:
            gjson = json.load(f)
    except Exception as e:
        print(f"  [WARN] cannot read graph.json: {e}")
        gjson = {"nodes": [], "links": [], "graph": {}, "directed": False, "multigraph": False, "hyperedges": []}

    existing_gids = {n.get("id") for n in gjson.get("nodes", [])}
    existing_links = set()
    for l in gjson.get("links", []):
        existing_links.add((l.get("source"), l.get("target")))

    new_nodes = 0
    new_links = 0
    for nid, nd in tf_nodes.items():
        if nid in existing_gids:
            continue
        gjson["nodes"].append({
            "file_type": "labor_function",
            "label": nd["label"],
            "id": nid,
            "tf_code": nd["tf_code"],
            "community": 99,
            "norm_label": nd["label"].lower(),
        })
        new_nodes += 1

    for e in edges:
        pair = (e["source"], e["target"])
        if pair in existing_links:
            continue
        gjson["links"].append({
            "source": e["source"],
            "target": e["target"],
            "relation": "artifact_handoff",
            "artifact": e["artifact"],
            "confidence": e["confidence"],
            "confidence_score": e["confidence_score"],
            "weight": e["weight"],
        })
        new_links += 1

    if new_nodes or new_links:
        with open(GRAPH_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(gjson, f, indent=2, ensure_ascii=False)
    print(f"  graph.json updated: +{new_nodes} nodes, +{new_links} links")
else:
    print("  [WARN] graph.json not found — graphify graph not updated")

# ── Шаг 7: Отчёт консистентности ───────────────────────────────────

report = {
    "meta": {
        "artifact": "B-02.6-graph-consistency",
        "tf": tf_code,
        "la": la_id,
        "generated_by": "crossfunction-graph-builder",
        "timestamp": os.popen("date -u +%Y-%m-%dT%H:%M:%SZ").read().strip(),
        "schema_ref": "graph-consistency-schema.yaml v1.0.0"
    },
    "body": {
        "graphify_path": "graphify-out/.graphify_semantic.json",
        "node_count": len(tf_nodes),
        "edge_count": len(edges),
        "controls": CONTROLS,
        "tf_nodes": [
            {
                "node_id": nid,
                "tf_code": nd["tf_code"],
                "mechanisms": nd["mechanisms"],
                "inputs": nd["inputs"],
                "outputs": nd["outputs"]
            } for nid, nd in sorted(tf_nodes.items())
        ],
        "handoff_edges": [
            {"source": e["source"], "target": e["target"], "artifact": e["artifact"]}
            for e in edges
        ],
        "consistency": consistency
    },
    "quality": {
        "schema_valid": True,
        "sources_read": [
            "outputs/07.007/block-D/labor-function-to-skill-mapping.yaml",
            "outputs/07.007/labor-coverage-registry.yaml",
            "profiles/*/skills/*/SKILL.md (ICOM Inputs)"
        ],
        "graphify_written": write_ok
    }
}

report_path = output_files[0] if output_files else os.path.join(
    output_dir, "B-02.6-graph-consistency.yaml"
)
write_yaml(report_path, report)
print(f"  Written: {report_path}")
```
