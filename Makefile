.PHONY: all sync constraints check check-anchors dist test serve clean

# Local checkout of the 223standard repository.
STANDARD ?= ../223standard
PUBLICATION := $(STANDARD)/publication

# Everything the deployed site consists of, assembled by 'make dist'.
DIST := site

all: index.html

# Copy the canonical graph from a 223standard publication build, produced by
# 'bash build-publication.sh' in that repo.
#
# This must be publication/223p_publication.ttl, the graph ttl2md.py minted the
# document's links from -- NOT the compiled 223p.ttl, which is a different
# graph and resolves only a fraction of the document's links. Blank-node IDs
# are canonical labels over a whole graph, so only the graph that produced the
# links can define their anchors. publication-anchors.txt records what the
# document expects so 'make check-anchors' can catch the wrong graph.
sync:
	cp $(PUBLICATION)/223p_publication.ttl ontologies/223p.ttl
	uv run python anchors.py extract \
	    $(PUBLICATION)/223p_publication.md publication-anchors.txt
	@echo "Synced from $(PUBLICATION); run 'make && make check-anchors' next"

# Regenerate the site from constraints.json.
index.html: constraints.json make_site.py templates/index.html templates/static/*
	uv run python make_site.py

# Extract concept definitions and stable IDs from the checked-in ontology.
constraints.json: ontologies/223p.ttl build_constraints.py constraints.py
	uv run python build_constraints.py

constraints: constraints.json

# Verify the built page defines every anchor the publication links. Needs no
# 223standard checkout, so this is the check CI runs.
check-anchors: index.html publication-anchors.txt
	uv run python anchors.py check publication-anchors.txt index.html

# Verify the publication's defs.open223.info anchors resolve in index.html,
# against the markdown from the build that ontologies/223p.ttl came from.
check: index.html check-links.sh check-links.py
	PUBLICATION_MD="$(PUBLICATION)/223p_publication.md" bash check-links.sh

# Assemble the publishable site. This directory is what CI uploads, both as a
# downloadable artifact and as the GitHub Pages deployment.
dist: index.html
	rm -rf $(DIST)
	mkdir -p $(DIST)
	cp index.html CNAME $(DIST)/
	cp -R ontologies $(DIST)/
	@echo "Assembled $(DIST)/ for upload"

test:
	uv run pytest -q tests

serve: index.html
	python3 -m http.server --bind 0.0.0.0 8000

clean:
	rm -rf constraints.json index.html $(DIST)
