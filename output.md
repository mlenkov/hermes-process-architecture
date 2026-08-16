# Отчёт: Фаза 2A — Безопасность и стабильность (перед GitHub)

Дата: 2026-08-04

## Задача 1: Секрет-скан — ✅ НАЙДЕНО: 0

Метод: git-secrets/trufflehog недоступны; repo не git (истории нет).
Ручной поиск по паттернам:

| Категория | Паттерн | Результат |
|-----------|---------|-----------|
| API-ключи | sk-, ghp_, AKIA, AIza, Bearer, xox | 0 |
| Файлы | .env, .pem, .key, .p12, .jks, credentials, vault | 0 |
| Ключевые слова | api_key, api_secret, token, password, secret | 0 |
| Webhooks | webhook, BOT_TOKEN, TELEGRAM_TOKEN, discord, slack | 0 |
| Длинные строки | hex/base64 >= 40 | только npm integrity-хеши (sha512) в package-lock.json |
| SSH | ~/.ssh, /Users/*/.ssh | 0 |
| API-ключ из чата | sk-qGEbCi4... | 0 (нигде не записан) |

**Вывод: секретов в репозитории нет. Действий не требуется.**

## Задача 2: Sandbox (RLIMIT) — ✅

В execute-tf-pipeline.py добавлен `build_sandbox_preamble(cfg)` — преамбула
подпроцесса навыка устанавливает:

```python
resource.setrlimit(resource.RLIMIT_CPU, (120, 120))       # CPU секунд
resource.setrlimit(resource.RLIMIT_AS, (512*1024*1024, 512*1024*1024))  # 512 MB
resource.setrlimit(resource.RLIMIT_FSIZE, (10*1024*1024, 10*1024*1024))  # 10 MB
```

**Graceful fallback** (задача требует): `except (resource.error, ValueError, OSError)`
→ печать `[WARN] RLIMIT ... not applied` в stderr, продолжение выполнения.

Результат smoke-теста (macOS): CPU и FSIZE применены — запись файла 30 МБ
упала с exit 1 (ограничение 10 МБ сработало). RLIMIT_AS на этой macOS-сессии
не поддерживается («current limit exceeds maximum limit») — WARN + продолжение,
как и предусмотрено fallback'ом.

## Задача 3: Атомарные записи write_yaml — ✅

Заменено в 12 исполняемых навыках + blueprint (раздел 8):

```python
def write_yaml(path, data):
    """Атомарная запись YAML: temp-файл + os.rename (POSIX)."""
    dir_name = os.path.dirname(path) or "."
    os.makedirs(dir_name, exist_ok=True)
    import tempfile
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".yaml.tmp")
    try:
        with os.fdopen(fd, "w") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        os.rename(tmp_path, path)
        return True
    except Exception as e:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        print(f"  [ERROR] write error: {path}: {e}")
        return False
```

Файлы: 9 analyst + 3 regulator. Все прошли compile(); тест: файл создан,
tmp-мусор отсутствует.

## Задача 4: config.yaml + конфигурируемый timeout — ✅

Создан `config.yaml` в корне:

```yaml
skill_timeout: 120          # секунд, wall-clock timeout для subprocess
cpu_limit_sec: 120          # RLIMIT_CPU
memory_limit_mb: 512        # RLIMIT_AS
file_size_limit_mb: 10      # RLIMIT_FSIZE
```

Executor: `load_sandbox_config()` читает config.yaml, затем env-переменные
(SKILL_TIMEOUT, SKILL_CPU_LIMIT_SEC, SKILL_MEMORY_LIMIT_MB,
SKILL_FILE_SIZE_LIMIT_MB) — env приоритетнее. Fallback на дефолты при
отсутствии файла. TimeoutExpired → reclaim задачи + [ERROR] сообщение.

## Регрессия: автономный цикл А/02.6 — ✅

```
seed: Created: 1/1 TF tasks, 4/4 TD tasks

RUN 1 → la-001: [INFO] Artifact already exists... Skipping generation. → ✅
RUN 2 → la-002: [INFO] ... Skipping generation. → ✅
RUN 3 → la-003: [INFO] ... Skipping generation. → ✅
RUN 4 → la-004: [INFO] ... Skipping generation. → ✅
RUN 5 → TF-summary: [INFO] TF-summary task — skip skill execution → ✅
RUN 6 → No ready tasks.
```

- 21 задача done в kanban (А/01.6, А/02.6, А/03.6 полные цепочки)
- Артефакты не тронуты, registry: 17 записей, валидатор: Registry valid: True, exit 0
- Корень outputs/07.007/ чист (только labor-coverage-registry.yaml)
- .yaml.tmp мусор: 0

## Изменённые файлы

- scripts/execute-tf-pipeline.py — RLIMIT-преамбула, конфигурируемый timeout,
  load_sandbox_config/build_sandbox_preamble
- config.yaml — создан
- 12 × profiles/*/skills/*/SKILL.md — атомарный write_yaml
- outputs/07.007/block-D/new-skill-architecture-blueprint.md — атомарный write_yaml (наследование)
