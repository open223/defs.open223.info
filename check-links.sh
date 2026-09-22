#!/bin/bash
# Verify that every defs.open223.info anchor the publication links to exists in
# the generated index.html.
#
# ontologies/223p.ttl is copied from a 223standard publication build, and only
# the markdown from *that same build* carries matching blank-node IDs: they are
# canonical labels over a whole graph, so a different build means different
# anchors. There is therefore nothing useful to check against without a local
# publication build -- rebuilding master here would just report every link as
# broken.
set -euo pipefail

PUBLICATION_MD="${PUBLICATION_MD:-}"

if [ -z "$PUBLICATION_MD" ]; then
  echo "Set PUBLICATION_MD to the 223p_publication.md from the same build as" >&2
  echo "ontologies/223p.ttl, or run 'make check STANDARD=/path/to/223standard'." >&2
  exit 1
fi

if [ ! -f "$PUBLICATION_MD" ]; then
  echo "No such file: $PUBLICATION_MD" >&2
  echo "Run 'bash build-publication.sh' in the 223standard checkout first." >&2
  exit 1
fi

uv run python check-links.py "$PUBLICATION_MD" index.html
