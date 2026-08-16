---
name: architect-seeder
description: Создание pipeline из YAML профстандарта — seed-tf-pipeline.py
version: 1.0.0
environments: [kanban]
---

# Seeder — создание pipeline

Создаёт kanban-цепочку ТД для указанной ТФ из YAML профстандарта.

## Процедура

```python
import subprocess

ARCH = "/Volumes/Storage/work/mais/_TOOLS/VM-SRV001-SETUP/ARCHITECTURE"

# Все ТФ
subprocess.run(["python3", f"{ARCH}/scripts/seed-tf-pipeline.py"], cwd=ARCH)

# Или по блоку
subprocess.run(["python3", f"{ARCH}/scripts/seed-tf-pipeline.py", "--otf", "D"], cwd=ARCH)

# Или по одной ТФ
subprocess.run(["python3", f"{ARCH}/scripts/seed-tf-pipeline.py", "--tf", "D/02.7"], cwd=ARCH)

# С очисткой
subprocess.run(["python3", f"{ARCH}/scripts/seed-tf-pipeline.py", "--otf", "D", "--clean"], cwd=ARCH)
```

## Триггеры
- Вручную: при добавлении новой ТФ или обновлении YAML
- Через monitor: если ready=0 и есть неисполненные ТФ
