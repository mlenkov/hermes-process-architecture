---
name: methodology-development-implementation
description: D/04.7 — Разработка и внедрение методик и регламентов трансформации процессной архитектуры
version: 1.0.0
environments: [kanban]
metadata:
  hermes:
    tags: [profstandart, 07.007, methodology, implementation]
    related_skills: [process-architecture-development, transformation-program-management]
---

# Methodology Development & Implementation — D/04.7

5 трудовых действий по методологии трансформации.

## File-based handoff

Читает входные YAML-файлы из `input_files`, пишет выходные YAML в `output_dir`.

## la-001: Разработка или доработка методик и регламентов

**Input:** `transformation-results` (из D/03.7), `architecture-analysis` (из D/01.7)
**Output:** `methodology-developed`

1. Проанализировать результаты трансформации как основу для методологии
2. Разработать/доработать методики и регламенты
3. Оформить как локальные нормативные акты

Схема: `schemas/07.007-d/methodology-developed.yaml`

## la-002: Внедрение методологии

**Input:** `methodology-developed`
**Output:** `methodology-deployed`

1. Разработать план внедрения
2. Провести обучение и разъяснение
3. Ввести методики в операционную деятельность

Схема: `schemas/07.007-d/methodology-deployed.yaml`

## la-003: Методическая помощь проектным командам

**Input:** `methodology-deployed`
**Output:** `teams-supported`

1. Организовать консультационную поддержку
2. Ответить на запросы проектных команд
3. Зафиксировать типовые вопросы и решения

Схема: `schemas/07.007-d/teams-supported.yaml`

## la-004: Контроль соблюдения методик

**Input:** `methodology-deployed`
**Output:** `compliance-report`

1. Провести аудит соблюдения методик и регламентов
2. Выявить отклонения
3. Составить отчёт

Схема: `schemas/07.007-d/compliance-report.yaml`

## la-005: Контроль актуальности методик

**Input:** `compliance-report`, `transformation-results`
**Output:** `methodology-updates`

1. Оценить актуальность методик в контексте новых данных
2. Инициировать обновление устаревших положений
3. Опубликовать актуальные версии

Схема: `schemas/07.007-d/methodology-updates.yaml`
