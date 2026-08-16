#!/usr/bin/env bash
# Деплой навыков профиля mais в локальную установку Hermes (~/.hermes).
#
# ADR-008: единственный исполнитель 07.007 — профиль mais.
# Для каждой директории в profiles/mais/skills/:
#   - если в ~/.hermes/profiles/mais/skills/ уже есть одноимённая директория — WARN и пропуск;
#   - иначе rsync -a только этой директории (без --delete).
#
# Использование:
#   ./scripts/deploy-to-hermes.sh            # деплой всех навыков
#   ./scripts/deploy-to-hermes.sh <skill>    # деплой одного навыка
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/profiles/mais/skills"
DEST="${HERMES_PROFILE_DIR:-$HOME/.hermes/profiles/mais/skills}"

if [[ ! -d "$SRC" ]]; then
  echo "[ERROR] Нет директории навыков: $SRC" >&2
  exit 1
fi

mkdir -p "$DEST"

deploy_one() {
  local skill="$1"
  local src_dir="$SRC/$skill"
  local dest_dir="$DEST/$skill"

  if [[ ! -d "$src_dir" ]]; then
    echo "[WARN] Навык не найден: $skill (пропуск)"
    return 0
  fi

  if [[ -e "$dest_dir" ]]; then
    echo "[WARN] Коллизия: $dest_dir уже существует (пропуск)"
    return 0
  fi

  rsync -a "$src_dir/" "$dest_dir/"
  echo "[OK]   $skill → $dest_dir"
}

if [[ $# -gt 0 ]]; then
  for skill in "$@"; do
    deploy_one "$skill"
  done
else
  for skill in "$SRC"/*/; do
    deploy_one "$(basename "$skill")"
  done
fi

echo "Готово. Навыки развёрнуты в $DEST"
