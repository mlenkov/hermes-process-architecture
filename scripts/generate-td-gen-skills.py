#!/usr/bin/env python3
"""Generate per-TD generation skills from YAML execution blocks."""
import os, sys, textwrap
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML required: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

ARCH = Path(__file__).resolve().parent.parent
YAML_PATH = ARCH / "docs" / "standards" / "07.007" / "otf-section-4.yaml"
OUT_DIR = ARCH / "profiles" / "mais" / "skills" / "td-gen"

def load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f)

def generate_skill(tf_code, la_idx, action, schemas, tf_name):
    """Generate a td-gen SKILL.md for one labor action."""
    la_id = f"la-{la_idx+1:03d}"
    text = action["text"]
    inputs = action.get("inputs", [])
    outputs = action.get("outputs", [])
    skill_name = f"td-gen-{tf_code.replace('/', '-')}-{la_id}"
    tf_dir = tf_code.replace("/", "-")

    # Build input/output description lines
    in_desc = "\n".join(f"  - `{i}` — читает из `input_files`" for i in inputs)
    out_desc = "\n".join(f"  - `{o}` — пишет в `output_dir/{o}.yaml`" for o in outputs)

    # Build schema loading code
    schema_load = "\n".join(
        f"# Schema: {o}.yaml"
        for o in outputs
    )
    
    # Build output generation code per output
    out_gen = ""
    for o in outputs:
        if o == "stakeholder-list":
            out_gen += """
    output[\"""" + o + """\"] = {
        "stakeholders": [
            {"id": "st-001", "name": "Генеральный директор", "role": "owner", "interest": "Стратегия и результаты", "influence": "high", "requirements": ["Целостность архитектуры"]},
            {"id": "st-002", "name": "ИТ-директор", "role": "implementer", "interest": "Архитектура КИС и интеграция", "influence": "high", "requirements": ["Совместимость систем"]},
            {"id": "st-003", "name": "Руководитель продуктов", "role": "user", "interest": "Процессы разработки", "influence": "medium", "requirements": ["Прозрачность этапов"]},
        ],
        "process": "Определение заинтересованных сторон",
    }"""
        elif o == "agreed-goals":
            out_gen += """
    output[\"""" + o + """\"] = {
        "goals": [
            {"id": "g-001", "description": "Построить целостную процессную архитектуру", "consensus": True, "owner": "CEO"},
            {"id": "g-002", "description": "Обеспечить прослеживаемость стратегии до процессов", "consensus": True, "owner": "COO"},
            {"id": "g-003", "description": "Устранить дублирование функций", "consensus": True, "owner": "CFO"},
        ],
        "process": "Согласование целей с заинтересованными сторонами",
    }"""
        elif o == "architecture-requirements":
            out_gen += """
    output[\"""" + o + """\"] = {
        "requirements": [
            {"id": "r-001", "domain": "Стратегический", "description": "Прослеживаемость целей до процессов", "priority": "critical"},
            {"id": "r-002", "domain": "Функциональный", "description": "Полная карта бизнес-функций", "priority": "high"},
            {"id": "r-003", "domain": "Интеграционный", "description": "Связь процессов с КИС", "priority": "high"},
            {"id": "r-004", "domain": "Нормативный", "description": "Соответствие ISO 9001:2025", "priority": "medium"},
        ],
        "process": "Определение требований к архитектуре",
    }"""
        elif o == "architecture-data":
            out_gen += """
    output[\"""" + o + """\"] = {
        "processes": [
            {"id": "p-001", "name": "Стратегическое управление", "owner": "CEO", "kis": ["Confluence"], "status": "documented"},
            {"id": "p-002", "name": "Управление продуктами", "owner": "CPO", "kis": ["Jira"], "status": "partial"},
            {"id": "p-003", "name": "Финансовый учёт", "owner": "CFO", "kis": ["1C:ERP"], "status": "automated"},
            {"id": "p-004", "name": "Разработка и релизы", "owner": "CTO", "kis": ["GitLab", "Jira"], "status": "partial"},
        ],
        "process": "Сбор информации о процессной архитектуре",
    }"""
        elif o == "gap-analysis":
            out_gen += """
    output[\"""" + o + """\"] = {
        "gaps": [
            {"id": "gap-001", "area": "Стратегия→Процессы", "severity": "critical", "description": "Нет прослеживаемости целей до процессов"},
            {"id": "gap-002", "area": "Документация", "severity": "major", "description": "Поддерживающие процессы не документированы"},
            {"id": "gap-003", "area": "Автоматизация", "severity": "major", "description": "Разрыв между Jira и 1C:ERP"},
            {"id": "gap-004", "area": "Ролевая модель", "severity": "minor", "description": "Владельцы процессов не назначены"},
        ],
        "process": "Анализ соответствия существующей архитектуры требованиям",
    }"""
        elif o == "improvement-opportunities":
            out_gen += """
    output[\"""" + o + """\"] = {
        "opportunities": [
            {"id": "opp-001", "description": "Внедрение BPMN-нотации для всех процессов", "impact": "high", "effort": "medium"},
            {"id": "opp-002", "description": "Автоматизация стыков КИС (Jira ↔ 1C)", "impact": "high", "effort": "high"},
            {"id": "opp-003", "description": "Назначение владельцев процессов", "impact": "medium", "effort": "low"},
            {"id": "opp-004", "description": "Построение процессной карты уровня 0-2", "impact": "high", "effort": "medium"},
        ],
        "process": "Выявление возможностей усовершенствования",
    }"""
        elif o == "analysis-report":
            out_gen += """
    output[\"""" + o + """\"] = {
        "title": "Анализ процессной архитектуры ООО ТехноПроект",
        "sections": [
            {"title": "Методология", "content": "SWOT-анализ, GAP-анализ, бенчмаркинг APQC PCF"},
            {"title": "Ключевые выводы", "content": "Архитектура частично документирована, выявлено 4 критических разрыва"},
            {"title": "Рекомендации", "content": "Внедрение BPMN, назначение владельцев, автоматизация стыков КИС"},
        ],
        "process": "Оформление результатов анализа",
    }"""
        elif o == "architecture-analysis":
            out_gen += """
    output[\"""" + o + """\"] = {
        "summary": "Архитектура частично документирована, 4 критических разрыва, покрытие 55%",
        "requirements": 4, "gaps": 4, "opportunities": 4, "stakeholders": 3, "goals": 3,
        "metadata": {"tf": "LF-07.007-D/01.7", "produced_by": \"""" + la_id + """\"},
    }"""
        elif o == "systematized-info":
            out_gen += """
    output[\"""" + o + """\"] = {
        "domains": [
            {"id": "dom-strat", "name": "Стратегический", "processes": ["Стратегическое управление"], "gaps": ["Стратегия→Процессы"]},
            {"id": "dom-core", "name": "Основной", "processes": ["Управление продуктами", "Разработка"], "gaps": []},
            {"id": "dom-support", "name": "Поддерживающий", "processes": ["Финансовый учёт", "HR"], "gaps": ["Не документированы"]},
            {"id": "dom-integ", "name": "Интеграционный", "processes": [], "gaps": ["Разрыв КИС"]},
        ],
        "process": "Систематизация информации об архитектуре",
    }"""
        elif o == "selected-reference-model":
            out_gen += """
    output[\"""" + o + """\"] = {
        "selected_model": "APQC PCF v7.3 (Process Classification Framework)",
        "methodology": "BPMN 2.0 + DMN",
        "alternatives_considered": [{"name": "SCOR", "reason": "Сфокусирован на supply chain"}, {"name": "eTOM", "reason": "Телеком-специфичный"}],
        "process": "Выбор референтной модели",
    }"""
        elif o == "adapted-model":
            out_gen += """
    output[\"""" + o + """\"] = {
        "source_model": "APQC PCF v7.3",
        "adaptations": [
            {"element": "Количество групп", "original": "13", "adapted": "9", "rationale": "Соответствие масштабу 500 чел."},
        ],
        "alignment": {"business_structure": True, "strategy": True, "goals": True},
        "process": "Адаптация референтной модели",
    }"""
        elif o == "architecture-designed":
            out_gen += """
    output[\"""" + o + """\"] = {
        "version": "1.0",
        "org_structure": [
            {"unit": "Совет директоров", "parent": None, "functions": ["Стратегия"]},
            {"unit": "ИТ-департамент", "parent": "Совет директоров", "functions": ["Разработка", "QA"]},
        ],
        "business_functions": [
            {"id": "f-001", "name": "Стратегическое планирование", "owner": "CEO"},
            {"id": "f-002", "name": "Управление релизами", "owner": "PM"},
        ],
        "processes": [
            {"id": "pr-001", "name": "Стратегический обзор", "input": "Анализ рынка", "output": "Стратегия", "owner": "CEO"},
            {"id": "pr-002", "name": "Релизный цикл", "input": "Backlog", "output": "Продукт", "owner": "PM"},
        ],
        "information_systems": [
            {"id": "is-001", "name": "1C:ERP", "supports": ["Финансовый учёт"]},
            {"id": "is-002", "name": "Jira", "supports": ["Управление релизами"]},
        ],
        "process": "Разработка процессной архитектуры",
    }"""
        elif o == "agreed-architecture":
            out_gen += """
    output[\"""" + o + """\"] = {
        "architecture_version": "1.0",
        "stakeholders_consulted": [
            {"id": "st-001", "role": "owner", "agreement": "full"},
            {"id": "st-002", "role": "implementer", "agreement": "full"},
        ],
        "status": "approved",
        "process": "Согласование архитектуры",
    }"""
        elif o == "architecture-compliance":
            out_gen += """
    output[\"""" + o + """\"] = {
        "conclusion": "compliant",
        "checked_models": [
            {"model_id": "pr-001", "name": "Стратегический обзор", "compliant": True},
            {"model_id": "pr-002", "name": "Релизный цикл", "compliant": True},
        ],
        "recommendations": ["Регулярный аудит моделей"],
        "process": "Контроль соответствия",
    }"""
        elif o == "transformation-plan":
            out_gen += """
    output[\"""" + o + """\"] = {
        "plan": {
            "phases": [
                {"name": "Анализ", "duration": "1 мес", "deliverables": ["Impact assessment"]},
                {"name": "Проектирование", "duration": "2 мес", "deliverables": ["Целевая архитектура"]},
                {"name": "Внедрение", "duration": "3 мес", "deliverables": ["Внедрённая архитектура"]},
            ],
            "kpi": [{"metric": "Process coverage", "baseline": 40, "target": 85}],
        },
        "process": "Планирование изменений в связи с реорганизацией",
    }"""
        elif o == "transformation-executed":
            out_gen += """
    output[\"""" + o + """\"] = {
        "program": {"name": "Архитектурная трансформация", "status": "in_progress"},
        "execution_log": [{"phase": "Анализ", "status": "completed"}, {"phase": "Проектирование", "status": "60%"}],
        "overall_status": "on_track",
        "process": "Руководство программой изменений",
    }"""
        elif o == "transformation-results":
            out_gen += """
    output[\"""" + o + """\"] = {
        "kpi_results": [{"metric": "Process coverage", "baseline": 40, "target": 85, "actual": 55}],
        "effectiveness_rating": "medium",
        "summary": "Трансформация выполнена на 55% от целевых показателей",
        "process": "Оценка эффективности трансформации",
    }"""
        elif o == "methodology-developed":
            out_gen += """
    output[\"""" + o + """\"] = {
        "methodologies": [
            {"name": "Регламент управления архитектурой", "type": "регламент", "version": "1.0", "status": "approved"},
            {"name": "Методика описания процессов", "type": "методика", "version": "1.0", "status": "draft"},
        ],
        "process": "Разработка методик и регламентов",
    }"""
        elif o == "methodology-deployed":
            out_gen += """
    output[\"""" + o + """\"] = {
        "deployment_plan": {
            "phases": [
                {"phase": "Пилот (ИТ-департамент)", "status": "planned"},
                {"phase": "Масштабирование", "status": "planned"},
            ],
        },
        "adoption_rate": 0.3,
        "process": "Внедрение методологии",
    }"""
        elif o == "teams-supported":
            out_gen += """
    output[\"""" + o + """\"] = {
        "support_log": [{"team": "Продуктовый отдел", "request": "Описание процесса релиза", "satisfaction": "high"}],
        "faq": [{"question": "Какую нотацию использовать?", "answer": "BPMN 2.0"}],
        "process": "Методическая помощь командам",
    }"""
        elif o == "compliance-report":
            out_gen += """
    output[\"""" + o + """\"] = {
        "audited_units": [
            {"unit": "ИТ-департамент", "compliant": True},
            {"unit": "Продуктовый отдел", "compliant": False, "findings": ["Не используются шаблоны BPMN"]},
        ],
        "overall_compliance_rate": 75,
        "process": "Контроль соблюдения методик",
    }"""
        elif o == "methodology-updates":
            out_gen += """
    output[\"""" + o + """\"] = {
        "review_date": "2026-07-29",
        "updates": [
            {"name": "Методика описания процессов", "version": "1.1", "changes": ["Добавлены шаблоны BPMN"]},
        ],
        "next_review_date": "2026-10-29",
        "process": "Актуализация методик",
    }"""
        else:
            out_gen += f"""
    output["{o}"] = {{"id": "{o}", "status": "generated", "process": "{text[:60]}",}}
"""

    out_gen = textwrap.dedent(out_gen)

    skill_md = f"""---
name: {skill_name}
description: td-gen for {tf_code}/{la_id}: {text[:60]}
version: 1.0.0
---

# td-gen: {tf_code} / {la_id}

**Трудовое действие:** {text}

## ICOM

**Inputs:**
{in_desc}

**Outputs:**
{out_desc}

## Process

```python
import os, yaml

# Read inputs
input_data = {{}}
for fpath in {inputs!r}:
    # fpath is the input_id, actual file is in input_files list
    pass  # data loaded from input_files by executor

# Generate outputs
output = {{}}
{schema_load}

{out_gen}

# Write outputs
os.makedirs(output_dir, exist_ok=True)
for oid, data in output.items():
    path = os.path.join(output_dir, f"{{oid}}.yaml")
    with open(path, "w") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
```

## Схемы данных
{chr(10).join(f'- `schemas/07.007-d/{o}.yaml`' for o in outputs)}
"""

    return skill_md

def main():
    data = load_yaml(YAML_PATH)
    if not data:
        print(f"Failed to load {YAML_PATH}")
        sys.exit(1)

    tfs = data.get("labor_functions", [])
    total = 0

    for tf in tfs:
        tf_code = tf.get("code", "?")
        tf_name = tf.get("name", "?")
        execution = tf.get("execution", {})
        actions = execution.get("actions", [])
        
        if not actions:
            print(f"  [SKIP] {tf_code}: no execution.actions")
            continue

        for idx, action in enumerate(actions):
            la_id = f"la-{idx+1:03d}"
            tf_dir = tf_code.replace("/", "-")

            # Create directory
            skill_dir = OUT_DIR / f"{tf_dir}-{la_id}"
            skill_dir.mkdir(parents=True, exist_ok=True)

            # Generate SKILL.md
            content = generate_skill(tf_code, idx, action, {}, tf_name)
            skill_path = skill_dir / "SKILL.md"
            with open(skill_path, "w") as f:
                f.write(content)

            total += 1
            print(f"  ✅ {tf_code}/{la_id}: {skill_path}")

    print(f"\nGenerated {total} td-gen skills")

if __name__ == "__main__":
    main()
