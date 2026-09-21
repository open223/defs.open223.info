.PHONY: all sync constraints check test serve clean

# Local checkout of the 223standard repository.
STANDARD ?= ../223standard
PUBLICATION := $(STANDARD)/publication

all: index.html

# Copy the canonical graph from a 223standard publication build.
#
# This must be publication/223p_publication.ttl, the graph ttl2md.py minted the
# document's links from -- NOT the compiled 223p.ttl, which is a different
# graph and resolves only 205 of the document's links. Blank-node IDs are
# canonical labels over a whole graph, so only the graph that produced the
# links can define their anchors.
sync:
	cp $(PUBLICATION)/223p_publication.ttl ontologies/223p.ttl
	@echo "Synced from $(PUBLICATION); run 'make && make check' next"

# Regenerate the site from constraints.json.
index.html: constraints.json make_site.py templates/index.html templates/static/*
	uv run python make_site.py

# Extract concept definitions and stable IDs from the checked-in ontology.
constraints.json: ontologies/223p.ttl build_constraints.py constraints.py
	uv run python build_constraints.py

constraints: constraints.json

# Verify the publication's defs.open223.info anchors resolve in index.html.
# Only the markdown from the same build as ontologies/223p.ttl shares its IDs,
# so prefer the local checkout and fall back to cloning master.
check: index.html check-links.sh check-links.py
	@if [ -f "$(PUBLICATION)/223p_publication.md" ]; then \
		PUBLICATION_MD="$(PUBLICATION)/223p_publication.md" bash check-links.sh; \
	else \
		bash check-links.sh; \
	fi

test:
	uv run pytest -q tests

serve: index.html
	python3 -m http.server --bind 0.0.0.0 8000

clean:
	rm -rf 223standard
