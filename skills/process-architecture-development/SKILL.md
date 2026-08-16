---
name: process-architecture-development
description: D/02.7 — Разработка и усовершенствование процессной архитектуры организации
version: 1.0.0
environments: [kanban]
metadata:
  hermes:
    tags: [profstandart, 07.007, architecture, development]
    related_skills: [stakeholder-mapping, requirements-analysis]
---

# Process Architecture Development — D/02.7

6 трудовых действий по разработке и усовершенствованию процессной архитектуры.

## File-based handoff

Читает входные YAML-файлы из `input_files`, пишет выходные YAML в `output_dir`.

## la-001: Систематизация информации о процессной архитектуре

**Input:** `architecture-analysis` (из D/01.7)
**Output:** `systematized-info`

1. Проанализировать входные данные анализа архитектуры
2. Классифицировать информацию по процессным доменам
3. Выявить дублирующиеся и противоречивые элементы
4. Структурировать в систематизированный каталог

Схема: `schemas/07.007-d/systematized-info.yaml`

## la-002: Выбор референтной модели и методологии

**Input:** `systematized-info`
**Output:** `selected-reference-model`

1. Определить критерии выбора референтной модели
2. Рассмотреть применимые референтные модели (SCOR, eTOM, APQC PCF, иные)
3. Обосновать выбор методологии проектирования

Схема: `schemas/07.007-d/selected-reference-model.yaml`

## la-003: Адаптация референтной модели

**Input:** `selected-reference-model`
**Output:** `adapted-model`

1. Сопоставить референтную модель со структурой бизнеса
2. Адаптировать к целям и стратегии организации
3. Документировать адаптации с обоснованием

Схема: `schemas/07.007-d/adapted-model.yaml`

## la-004: Разработка процессной архитектуры

**Input:** `adapted-model`
**Output:** `architecture-designed`

1. Отрисовать целевую процессную архитектуру: оргструктура, бизнес-функции, процессы/регламенты, КИС
2. Описать взаимосвязи элементов
3. Зафиксировать версию

Схема: `schemas/07.007-d/architecture-designed.yaml`

## la-005: Согласование с заинтересованными сторонами

**Input:** `architecture-designed`
**Output:** `agreed-architecture`

1. Провести рабочее совещание с ключевыми стейкхолдерами
2. Зафиксировать замечания и предложения
3. Достичь консенсуса, подписать протокол согласования

Схема: `schemas/07.007-d/agreed-architecture.yaml`

## la-006: Контроль соответствия

**Input:** `architecture-designed`
**Output:** `architecture-compliance`

1. Сверить разработанные модели с утверждённой архитектурой
2. Выявить отклонения
3. Оформить заключение о соответствии

Схема: `schemas/07.007-d/architecture-compliance.yaml`
