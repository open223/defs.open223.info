.PHONY: all constraints check test serve clean

all: index.html

# Regenerate the site from constraints.json.
index.html: constraints.json make_site.py templates/index.html templates/static/*
	uv run python make_site.py

# Extract concept definitions and stable IDs from the checked-in ontology.
constraints.json: ontologies/223p.ttl build_constraints.py constraints.py
	uv run python build_constraints.py

constraints: constraints.json

# Verify the publication's defs.open223.info anchors resolve in index.html.
check: index.html check-links.sh check-links.py
	bash check-links.sh

test:
	uv run pytest -q tests

serve: index.html
	python3 -m http.server --bind 0.0.0.0 8000

clean:
	rm -rf 223standard
