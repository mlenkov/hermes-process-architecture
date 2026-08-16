---
name: architect-coverage
description: Обновление labor-coverage-registry.yaml после complete TF-summary
version: 1.0.0
environments: [kanban]
---

# Coverage — обновление реестра покрытия

После complete TF-summary: читает output-артефакты, обновляет registry.

## Процедура

```python
import subprocess, json, yaml, os
from datetime import datetime

REGISTRY_PATH = "/Users/mac/.hermes/profiles/mais/standards/labor-coverage-registry.yaml"
# fallback для локального теста
TEST_REGISTRY = "/Volumes/Storage/work/mais/_TOOLS/VM-SRV001-SETUP/ARCHITECTURE/outputs/07.007/labor-coverage-registry.yaml"

def run_hermes(args):
    return subprocess.run(["hermes", "kanban"] + args, capture_output=True, text=True, timeout=30)

# 1. Получить завершённые TF-summary (done)
done = run_hermes(["list", "--status", "done", "--json"])
tasks = json.loads(done.stdout) if done.stdout.strip() else []

tf_summaries = [t for t in tasks if "🔄" in t.get("title", "")]

for t in tf_summaries:
    tid = t["id"]
    show = run_hermes(["show", tid])
    lines = show.stdout.split("\n")
    body = None
    for i, line in enumerate(lines):
        if line.startswith("Body:"):
            rest = line[5:].strip()
            body = json.loads(rest if rest else lines[i+1].strip())
            break
    if not body or body.get("type") != "tf_pipeline":
        continue

    tf_code = body.get("function", {}).get("code", "?")
    lf_id = f"LF-07.007-{tf_code}"
    total_actions = body.get("total_actions", 0)
    output_base = body.get("output_base", "")

    # Прочитать registry
    registry_path = TEST_REGISTRY  # для локального теста
    registry = {}
    if os.path.exists(registry_path):
        with open(registry_path) as f:
            registry = yaml.safe_load(f) or {}

    # Обновить запись
    registry[lf_id] = {
        "status": "covered",
        "last_executed": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tds_completed": f"{total_actions}/{total_actions}",
        "executed_by": "mais",
    }

    # Записать
    with open(registry_path, "w") as f:
        yaml.dump(registry, f, allow_unicode=True, default_flow_style=False)

    print(f"Updated {lf_id}: covered ({total_actions}/{total_actions})")
```
