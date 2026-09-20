#!/bin/bash
# scripts/init_language.sh
# Usage: init_language.sh <lang_code>
# Example: init_language.sh de

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$ROOT_DIR"

if [ -z "$1" ]; then
    echo "Usage: $0 <lang_code>"
    echo "Example: $0 de"
    exit 1
fi

LANG_CODE="$1"
POT_FILE="code/locales/messages.pot"
PO_FILE="code/locales/$LANG_CODE/LC_MESSAGES/messages.po"

if [ ! -f "$POT_FILE" ]; then
    echo "Error: $POT_FILE not found. Run scripts/extract_translations.sh first."
    exit 1
fi

if [ -f "$PO_FILE" ]; then
    echo "Language '$LANG_CODE' already initialized at $PO_FILE"
    exit 0
fi

pybabel init -i "$POT_FILE" -d code/locales -l "$LANG_CODE"
echo "Initialized $PO_FILE — edit it, then run scripts/compile_translations.sh"