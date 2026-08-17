# ADR-004: Skill Naming Refactoring — удаление префиксов профилей из имён навыков

**Дата:** 2026-07-31
**Статус:** **Superseded by ADR-008/014** (топология исполнителей изменилась)
**Профстандарт:** 07.007 «Специалист по процессному управлению»

---

## Контекст

Навыки (SKILL.md) создавались с префиксом профиля в имени: `regulator-info-gatherer`,
`analyst-crossfunction-analyzer`, `architect-pdca`. Это нарушает принцип
«навык — атомарная функция, профиль — контейнер»:

- **Жёсткая связность (coupling):** имя навыка фиксирует принадлежность к одному
  профилю. Перенос навыка в другой профиль требует переименования всех ссылок.
- **Дублирование:** для переиспользования навыка между профилями приходится копировать
  его (копии `architect-*` vs `regulator-*`).
- **Метаданные уже есть:** принадлежность профилю хранится в пути
  `profiles/<profile>/skills/<skill>/` и в `labor-coverage-registry.yaml`
  (`executed_by`, `skill_path`). Имя навыка не должно дублировать эту информацию.

## Решение

**Имя навыка = функция. Путь = контекст (профиль).**

Схема переименования — снятие префикса профиля, имя отражает только функцию:

| Профиль | Было | Стало |
|---------|------|-------|
| regulator | `regulator-info-gatherer` | `info-gatherer` |
| regulator | `regulator-regulation-writer` | `regulation-writer` |
| regulator | `regulator-deployment-planner` | `deployment-planner` |
| analyst | `analyst-crossfunction-analyzer` | `crossfunction-analyzer` |
| analyst | `analyst-crossfunction-graph-builder` | `crossfunction-graph-builder` |
| architect | `architect-pdca` | `pdca-reporter` |

Примечание по `architect-pdca`: имя заменено не только снятием префикса, но и
уточнением функции (`pdca-reporter` — формирует PDCA-отчёт), т.к. голое `pdca`
не выражает функции.

## Изменяемые файлы

1. **Директории навыков** — `profiles/<profile>/skills/<skill>/` (6 штук)
2. **`outputs/07.007/block-D/labor-function-to-skill-mapping.yaml`** — все `skill_path`
3. **`outputs/07.007/labor-coverage-registry.yaml`** — все `skill_path`
4. **Внутренние ссылки** в SKILL.md: frontmatter `name`, заголовок `#`, `meta.generated_by`,
   упоминания соседних навыков
5. **Сгенерированные артефакты** — `meta.generated_by` (пересоздаются при исполнении)

## Что НЕ делаем в этом ADR

- Не создаём новых навыков (В/03.6 `crossfunction-designer` — следующий шаг)
- Не трогаем `architect-coverage`, `architect-executor`, `architect-monitor`,
  `architect-seeder`, `architect-selfheal` (блок D — отдельный шаг, если потребуется)
- Не удаляем старые `architect-*` копии в `profiles/architect/skills/` (backward compat)

## Последствия

- **Плюс:** имена навыков уникальны без контекста профиля, переиспользование без копирования
- **Минус:** требуется синхронизация всех ссылок (mapping, registry, артефакты) за один проход
