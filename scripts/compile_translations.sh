#!/bin/bash
# scripts/compile_translations.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$ROOT_DIR"

shopt -s nullglob
po_files=(code/locales/*/LC_MESSAGES/messages.po)

if [ ${#po_files[@]} -eq 0 ]; then
    echo "No .po files found — run scripts/init_language.sh <lang_code> first."
    exit 1
fi

pybabel compile -d code/locales
echo "Compiled ${#po_files[@]} language(s)."