# Contributing

Спасибо за интерес к проекту! Здесь описаны правила добавления навыков, трудовых
функций и архитектурных решений. Всё исполнение построено на принципах
**ADR-001…ADR-007** — отклонения от них ломают автономность.

---

## 1. Как добавить новый навык

1. Прочитай **`outputs/07.007/block-D/new-skill-architecture-blueprint.md`** — это эталон
   структуры SKILL.md (frontmatter, ICOM, Rules, Thinking Process, Process).
2. Создай `profiles/<profile>/skills/<skill-name>/SKILL.md`.
3. Обязательные требования к коду `## Process`:
   - **Шаг 0 (ADR-007)** — pre-flight check идемпотентности ДО бизнес-шагов:
     ```python
     # ── Шаг 0: Pre-flight Check (идемпотентность, ADR-007) ────────────
     la_id = body.get("la_id", "la-001")
     parent_tf = body.get("parent_tf", "LF-07.007-{TF}")
     tf_code = parent_tf.replace("LF-07.007-", "") if parent_tf else "{TF}"
     current_skill_path = "profiles/<profile>/skills/<skill-name>/SKILL.md"
     ...
     if reg_ok and skill_ok:
         print("[INFO] Artifact already exists and is valid. Registry is up to date. Skipping generation.", flush=True)
         os._exit(0)
     ```
   - **Запрещено** создавать `_meta.yaml` (ADR-002): вся метаинформация — только
     в ключе `meta:` основного артефакта.
   - **Атомарные записи**: используй `write_yaml()` из blueprint (temp-файл +
     `os.rename`, Фаза 2A). Никаких прямых `open(path, "w")`.
   - Бизнес-логика (Шаги 1–5) — только реальные данные из файловой системы,
     без выдуманных сущностей и без `subprocess` к Hermes.
4. Зарегистрируй навык в **mapping** (см. раздел 3).
5. Прогони валидацию:
   ```bash
   python3 scripts/validate-registry.py
   ```

## 2. Обязательные правила (checklist)

| Правило | ADR | Где |
|---------|-----|-----|
| Шаг 0 pre-flight + `flush=True` + `os._exit(0)` | ADR-007 | начало `## Process` |
| Нет `_meta.yaml` — только `meta:` в артефакте | ADR-002 | весь SKILL.md |
| Атомарная запись (temp + rename) | Фаза 2A | `write_yaml()` |
| `skill_path` без префиксов, соответствует реальному пути | ADR-004 | Шаг 0, mapping |
| Один артефакт = один файл | ADR-002 | `output_files[0]` |
| Навык не пишет в registry напрямую | ADR-003 | — |

## 3. Как добавить новую Трудовую Функцию

1. Обнови **`outputs/07.007/block-D/labor-function-to-skill-mapping.yaml`**:
   добавь запись в `mappings`:
   ```yaml
   - tf_code: "Х/00.0"
     tf_name: "..."
     skill_path: "<skill-name>/SKILL.md"
     coverage_status: covered|partially_covered|missing
   ```
2. Убедись, что навык существует и зарегистрирован в `labor-coverage-registry.yaml`
   (или в `documented_gaps` до первого исполнения — без фиктивных записей).
3. Проверь, что `registry` и `mapping` консистентны:
   ```bash
   python3 scripts/validate-registry.py   # → Registry valid: True
   ```

## 4. Процесс принятия ADR

Архитектурные решения фиксируются в **`docs/ADR/`** (в текущей структуре —
`outputs/07.007/block-D/ADR-*.md`):

1. **Proposal** — опиши проблему, варианты, решение; файл `ADR-XXX-<slug>.md`.
2. **Review** — обсуждение в PR; решение не внедряется до утверждения.
3. **Adoption** — статус «Утверждён»; обнови blueprint, навыки, документацию.
4. **Retro** — если решение оказалось неудачным — новый ADR с суперседированием,
   а не правка истории.

Структура ADR: `# ADR-XXX: <название>` → `## Проблема` → `## Решение` →
`## Последствия` → `## Статус`.

---

## Проверки перед PR

```bash
# 1. Консистентность registry
python3 scripts/validate-registry.py

# 2. Синтаксис всех YAML
python3 -c "
import yaml, os
for root, _, files in os.walk('.'):
    if '.git' in root or 'node_modules' in root: continue
    for f in files:
        if f.endswith(('.yaml', '.yml')):
            yaml.safe_load(open(os.path.join(root, f), encoding='utf-8'))
print('YAML OK')
"

# 3. Синтаксис python-блоков навыков (если менял SKILL.md)
# 4. Автономный цикл (опционально, требует локальный Hermes):
#    python3 scripts/seed-tf-pipeline.py --tf "А/01.6"
#    python3 scripts/execute-tf-pipeline.py
```

CI (`.github/workflows/validate.yml`) выполняет пункты 1–2 автоматически на каждый push и pull request.
