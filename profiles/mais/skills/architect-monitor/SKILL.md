---
name: architect-monitor
description: Мониторинг kanban — проверка ready/blocked, запуск executor/selfheal
version: 1.0.0
environments: [kanban]
---

# Monitor — проверка состояния pipeline

Периодически (cron */15 или по запросу) проверяет состояние kanban.

## Процедура

```python
import subprocess, json

def run_hermes(args):
    result = subprocess.run(
        ["hermes", "kanban"] + args,
        capture_output=True, text=True, timeout=30
    )
    return result

# 1. Stats
stats = run_hermes(["stats"])
print(stats.stdout)

# 2. Ready tasks
ready = run_hermes(["list", "--status", "ready", "--json"])
ready_tasks = json.loads(ready.stdout) if ready.stdout.strip() else []

# 3. Blocked tasks
blocked = run_hermes(["list", "--status", "blocked", "--json"])
blocked_tasks = json.loads(blocked.stdout) if blocked.stdout.strip() else []

# 4. Action
if ready_tasks:
    print(f"Ready: {len(ready_tasks)} → запуск executor")
    hermes_exec_profile("mais", "architect-executor")

if blocked_tasks:
    print(f"Blocked: {len(blocked_tasks)} → запуск selfheal")
    hermes_exec_profile("mais", "architect-selfheal")
```

## Выходные данные
Пишет отчёт в `outputs/07.007/monitor/{date}.yaml`:
```yaml
timestamp: 2026-07-29T12:00:00
stats:
  ready: 4
  running: 0
  blocked: 0
  done: 22
actions:
  - executor: triggered (4 tasks)
  - selfheal: none
```

## Триггеры
- cron `*/15 * * * *` (на сервере)
- `hermes profile exec architect architect-monitor` (вручную)
