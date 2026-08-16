# ADR-001: Интеграция standalone-навыков в pipeline

**Статус:** Предложено
**Дата:** 2026-07-29
**Контекст:** D/03.7 — Руководство трансформацией

---

## Проблема

`architect-executor` ищет навыки только в `td-gen/` директории. Созданный `architect-info-gatherer` (standalone-навык) недоступен для pipeline, хотя замаплен в `labor-function-to-skill-mapping.yaml`.

Текущий алгоритм поиска:
1. Вычислить имя директории: `{tf_code}-{la_id}` (например `А-01.6-la-001`)
2. Искать в `profiles/architect/skills/td-gen/{dir}/SKILL.md`
3. Не найдено → generic fallback (минимальный YAML)

Проблема: новый навык лежит в `profiles/architect/skills/architect-info-gatherer/SKILL.md`, но executor его не видит.

---

## Варианты

### А: Обёртка td-gen

Создать `profiles/architect/skills/td-gen/А-01.6-la-001/SKILL.md`, который импортирует и вызывает `architect-info-gatherer`.

**Плюсы:** Минимальные изменения в коде executor'а.
**Минусы:** N обёрток на N навыков. Дублирование. Навык не живёт сам по себе.

### Б: Расширить executor через mapping (ВЫБРАН)

В `get_td_gen_skill()` добавить второй шаг: если td-gen не найден — прочитать `labor-function-to-skill-mapping.yaml`, найти ТФ по коду, взять `skill_path`.

**Плюсы:** 
- Универсально: работает для всех 12 недостающих навыков без создания обёрток
- Использует существующий mapping — единая точка истины
- Не требует изменений в seeder'е (body задачи не меняется)
- Обратная совместимость: td-gen по-прежнему в приоритете

**Минусы:** Одноразовое изменение executor'а (нужно обновить 2 файла: `td_runner.py` и `architect-executor/SKILL.md`).

### В: Отдельный оркестратор блока A

Создать `architect-block-a-executor`, который знает только про блок A.

**Плюсы:** Изоляция логики.
**Минусы:** Дублирование кода с executor'ом. Нарушение DRY. Требует создания оркестратора на каждый блок.

---

## Решение

**Выбран вариант Б.** Обоснование:
1. Единая точка истины: `labor-function-to-skill-mapping.yaml` уже содержит все связи ТФ→skill
2. Нулевая стоимость масштабирования: следующий навык достаточно добавить в mapping
3. Обратная совместимость: существующие td-gen продолжают работать
4. Соответствует архитектуре Hermes: resolver pattern — executor решает, какой skill загрузить

## План реализации

1. `scripts/td_runner.py`: в `generate()` добавить fallback на mapping
2. `profiles/architect/skills/architect-executor/SKILL.md`: то же изменение для Hermes-пути
3. `outputs/07.007/D/labor-function-to-skill-mapping.yaml`: обновить skill_path для А/01.6
4. Тест: запустить `architect.py execute` с задачей А/01.6 la-001
