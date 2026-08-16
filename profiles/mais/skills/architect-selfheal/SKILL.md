---
name: architect-selfheal
description: Восстановление blocked/timed-out задач — reclaim, retry, escalate
version: 1.0.0
environments: [kanban]
---

# Selfheal — восстановление pipeline

Обрабатывает задачи в статусе `blocked` или зависшие `running`.

## Процедура

```python
import subprocess, json

def run_hermes(args):
    return subprocess.run(["hermes", "kanban"] + args, capture_output=True, text=True, timeout=30)

# 1. Получить список blocked
blocked = run_hermes(["list", "--status", "blocked", "--json"])
tasks = json.loads(blocked.stdout) if blocked.stdout.strip() else []

# 2. Получить список running (проверить timeout)
running = run_hermes(["list", "--status", "running", "--json"])
running_tasks = json.loads(running.stdout) if running.stdout.strip() else []

# 3. Для каждой blocked: reclaim → retry
for t in tasks:
    tid = t["id"]
    title = t.get("title", "?")

    # Проверить количество попыток из Events
    # Если >= 2 → escalate, иначе reclaim
    run_hermes(["reclaim", tid])
    
    # Повторная попытка — задача переходит в ready
    print(f"Reclaimed {tid}: {title[:50]}")

# 4. Для каждой running: проверить timeout
import time
for t in running_tasks:
    tid = t["id"]
    # Проверить время старта из Events
    # Если running > 30 мин → reclaim
```

## Если задача не восстанавливается

```yaml
# escalate-report.yaml
task_id: t_xxxx
tf_code: D/01.7
la_id: la-003
failures: 3
reason: "LLM generation timeout"
action: "requires OpenCode intervention"
```

Пишет в `outputs/07.007/escalate/{date}-{task_id}.yaml`.

## Лимиты
- Max retries per task: 2
- Max running time: 30 min
