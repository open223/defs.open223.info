.PHONY: serve

serve: static/index.html
	cd static && python3 -m http.server --bind 0.0.0.0 8000

static/index.html: ontologies/223p.ttl generate_interactive_doc.py
	python3 generate_interactive_doc.py ontologies/223p.ttl
