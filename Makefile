.PHONY: serve

serve: index.html
	python3 -m http.server --bind 0.0.0.0 8000

index.html: ontologies/223p.ttl generate_interactive_doc.py templates/index.html templates/static/app.js check-links.sh check-links.py constraints.json
	#. .venv/bin/activate && python3 generate_interactive_doc.py ontologies/223p.ttl ontologies/223standard.ttl ontologies/223enumerations.ttl
	#. .venv/bin/activate && python3 gendoc.py ontologies/223p.ttl ontologies/223standard.ttl ontologies/223enumerations.ttl
	. .venv/bin/activate && python3 make_site.py
	bash check-links.sh
