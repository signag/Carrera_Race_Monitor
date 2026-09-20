#!/bin/bash
# scripts/extract_translations.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$ROOT_DIR"

PROJECT=$(python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['name'])")
VERSION=$(python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")
AUTHOR=$(python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['authors'][0]['name'])")
ISSUES=$(python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['urls']['Issues'])")

pybabel extract -F code/babel.cfg \
    --project="$PROJECT" \
    --version="$VERSION" \
    --copyright-holder="$AUTHOR" \
    --msgid-bugs-address="$ISSUES" \
    -o code/locales/messages.pot code

shopt -s nullglob
po_files=(code/locales/*/LC_MESSAGES/messages.po)

if [ ${#po_files[@]} -eq 0 ]; then
    echo "No .po files found — initializing German..."
    pybabel init -i code/locales/messages.pot -d code/locales -l de
else
    for po in "${po_files[@]}"; do
        pybabel update -i code/locales/messages.pot -d code/locales
    done
fi