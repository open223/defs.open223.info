.PHONY: serve

serve: index.html
	python3 -m http.server --bind 0.0.0.0 8000

index.html: ontologies/223p.ttl generate_interactive_doc.py templates/index.html templates/static/app.js
	python3 generate_interactive_doc.py ontologies/223p.ttl
