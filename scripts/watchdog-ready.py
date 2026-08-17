#!/usr/bin/env python3
"""Watchdog: алерт на ready-задачи старше N минут (ADR-017).

Сканирует борды Kanban std-7007/std-0643/std-0613, находит задачи в статусе
'ready', замороженные дольше порога (по умолчанию 30 мин), и выводит алерт.

Скрипт без side-effect'ов: только диагностика. Вызывается cron'ом каждую
минуту; непингующий вывод (нет проблем) — пустой, чтобы cron молчал
(паттерн watchdog).

Usage:
    python3 scripts/watchdog-ready.py                 # борды по умолчанию
    python3 scripts/watchdog-ready.py --boards std-0643 std-0613 --minutes 60

Exit codes:
    0 — вовремя; 1 — есть замороженные ready (алерт).
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone

DEFAULT_BOARDS = ["std-0643", "std-0613", "default"]  # 07.007 исполняется на default; std-7007 не создан
DEFAULT_MINUTES = 30


def _ts(tasks_json: str):
    return json.loads(tasks_json)


def scan_board(board: str, minutes: int) -> list:
    """Возвращает список замороженных ready-задач на борде."""
    try:
        r = subprocess.run(
            ["hermes", "kanban", "--board", board, "list", "--json"],
            capture_output=True, text=True, timeout=60,
        )
        tasks = json.loads(r.stdout) if r.stdout.strip() else []
    except Exception as e:  # борд может не существовать / недоступен
        return [{"board": board, "error": str(e)}]

    frozen = []
    now = time.time()
    for t in tasks:
        if t.get("status") != "ready":
            continue
        # время появления: то, что доступно в JSON (created_at или similar)
        created = t.get("created_at") or t.get("started_at")
        age_min = None
        if created:
            try:
                dt = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
                age_min = (now - dt.timestamp()) / 60
            except Exception:
                pass
        if age_min is not None and age_min > minutes:
            frozen.append({
                "board": board, "task_id": t.get("id"),
                "title": (t.get("title") or "")[:60], "age_min": round(age_min, 1),
                "assignee": t.get("assignee"),
            })
    return frozen


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--boards", nargs="*", default=DEFAULT_BOARDS)
    ap.add_argument("--minutes", type=float, default=DEFAULT_MINUTES)
    args = ap.parse_args()

    all_frozen = []
    for b in args.boards:
        all_frozen.extend(scan_board(b, args.minutes))

    if all_frozen:
        print("⚠ WATCHDOG: замороженные ready-задачи (older than %s min):" % args.minutes)
        for f in all_frozen:
            if "error" in f:
                print(f"  [{f['board']}] ошибка сканирования: {f['error']}")
            else:
                print(f"  [{f['board']}] {f['task_id']} | {f['title']} "
                      f"(age={f['age_min']} min, assignee={f.get('assignee')})")
        return 1
    # нет проблем — молчим (watchdog-паттерн)
    return 0


if __name__ == "__main__":
    sys.exit(main())
