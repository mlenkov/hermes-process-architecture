#!/usr/bin/env bash
# =============================================================================
# deploy-to-hermes.sh — деплой навыков профиля mais в локальную установку Hermes
#
# Правила (ADR-008):
#   1. Для каждой директории в profiles/mais/skills/ выполняется проверка
#      коллизии с ~/.hermes/profiles/mais/skills/<name>.
#   2. Если целевая директория УЖЕ существует — WARN и пропуск,
#      НЕ перезаписывать (существующие навыки Hermes не трогаем).
#   3. rsync -a только этой директории (без --delete).
#
# Usage:
#   bash scripts/deploy-to-hermes.sh
# =============================================================================
set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_DIR="$REPO_ROOT/profiles/mais/skills"
DST_ROOT="${HERMES_PROFILE_DIR:-$HOME/.hermes/profiles/mais/skills}"

if [ ! -d "$SRC_DIR" ]; then
    echo "[ERROR] Исходная директория не найдена: $SRC_DIR"
    exit 1
fi

mkdir -p "$DST_ROOT"

COLLISIONS=0
DEPLOYED=0

echo "=== Деплой навыков профиля mais → $DST_ROOT ==="
for skill_dir in "$SRC_DIR"/*/; do
    [ -d "$skill_dir" ] || continue
    name="$(basename "$skill_dir")"
    dst="$DST_ROOT/$name"

    if [ -e "$dst" ]; then
        echo "[WARN] Коллизия: $dst уже существует — пропуск (не перезаписываю)."
        COLLISIONS=$((COLLISIONS + 1))
        continue
    fi

    # rsync -a, а при его отсутствии — cp -a (функциональный эквивалент
    # рекурсивного копирования с атрибутами; --delete не используется).
    if command -v rsync >/dev/null 2>&1; then
        rsync -a "$skill_dir" "$dst"
    else
        echo "  [WARN] rsync не найден — использую cp -a"
        cp -a "$skill_dir" "$dst"
    fi

    if [ ! -d "$dst" ] || [ -z "$(find "$dst" -name SKILL.md | head -1)" ]; then
        echo "[ERROR] Копирование $name не удалось — выход."
        exit 2
    fi
    echo "[OK]   $name → $dst"
    DEPLOYED=$((DEPLOYED + 1))
done

echo ""
echo "=== Итог: развёрнуто $DEPLOYED, пропущено (коллизии) $COLLISIONS ==="

if [ "$COLLISIONS" -gt 0 ]; then
    echo "[WARN] Обнаружены коллизии — требуется ручная проверка (правило ADR-008: не перезаписывать)."
    exit 1
fi

exit 0