---
name: transformation-program-management
description: D/03.7 — Руководство программами трансформации процессной архитектуры организации
version: 1.0.0
environments: [kanban]
metadata:
  hermes:
    tags: [profstandart, 07.007, transformation, program-management]
    related_skills: [process-architecture-development]
---

# Transformation Program Management — D/03.7

3 трудовых действия по руководству программами трансформации.

## File-based handoff

Читает входные YAML-файлы из `input_files`, пишет выходные YAML в `output_dir`.

## la-001: Планирование изменения процессной архитектуры

**Input:** `architecture-compliance` (из D/02.7), `business-reorg`
**Output:** `transformation-plan`

1. Проанализировать планы реорганизации бизнеса
2. Оценить влияние на процессную архитектуру
3. Разработать план изменений: этапы, сроки, ресурсы, KPI

Схема: `schemas/07.007-d/transformation-plan.yaml`

## la-002: Руководство программами изменения

**Input:** `transformation-plan`
**Output:** `transformation-executed`

1. Сформировать программу проектов изменений
2. Распределить роли и ответственность
3. Координировать исполнение, управлять отклонениями
4. Отчитаться о выполнении

Схема: `schemas/07.007-d/transformation-executed.yaml`

## la-003: Оценка эффективности изменения

**Input:** `transformation-executed`
**Output:** `transformation-results`

1. Сравнить фактические результаты с плановыми KPI
2. Оценить влияние на подразделения, работников, ИС
3. Подготовить отчёт об эффективности трансформации

Схема: `schemas/07.007-d/transformation-results.yaml`
