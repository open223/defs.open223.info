#!/bin/bash
# Rebuild the 223standard publication markdown and verify that every anchor it
# links to on defs.open223.info actually exists in the generated index.html.
set -euo pipefail

STANDARD_REPO="https://bas-im.emcs.cornell.edu/223/223standard.git"
STANDARD_DIR="223standard"

if [ ! -d "$STANDARD_DIR" ]; then
  git clone "$STANDARD_REPO" "$STANDARD_DIR"
else
  git -C "$STANDARD_DIR" pull
fi

# Build 223p_publication.md in an isolated venv owned by the publication dir.
# Activate it rather than using `uv run`: uv would walk up to this repo's
# pyproject.toml and run the publication scripts against the wrong interpreter.
(
  cd "$STANDARD_DIR/publication"
  uv venv --seed --allow-existing
  set +u
  . .venv/bin/activate
  set -u
  uv pip install -r requirements.txt
  bash build-documentation.sh
)

uv run python check-links.py \
  "$STANDARD_DIR/publication/223p_publication.md" index.html
