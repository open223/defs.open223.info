"""Render index.html from constraints.json using the templates/ directory.

constraints.json is generated from ontologies/223p.ttl by build_constraints.py.
"""

import json

from jinja2 import Environment, FileSystemLoader, select_autoescape

CONSTRAINTS_FILE = "constraints.json"
OUTPUT_FILE = "index.html"


class SiteBuilder:
    def __init__(self, constraints_json_file: str):
        with open(constraints_json_file) as f:
            data = json.load(f)
        self.ontology = data["ontology"]
        self.constraints = data["concepts"]

    def build_definitions(self):
        """One dict per concept, in the shape templates/index.html expects."""
        return [
            {
                "class": concept,
                "name": defn["stable_id"],
                "label": defn["label"],
                "immediate_subgraph": defn["cbd"],
            }
            for concept, defn in self.constraints.items()
        ]

    def build(self):
        env = Environment(
            loader=FileSystemLoader("templates"),
            autoescape=select_autoescape(),
        )
        template = env.get_template("index.html")

        definitions = self.build_definitions()
        with open(OUTPUT_FILE, "w") as f:
            f.write(template.render(concepts=definitions, ontology=self.ontology))
        print(
            f"Wrote {OUTPUT_FILE} with {len(definitions)} concepts "
            f"({self.ontology['uri']} {self.ontology['version']})"
        )


if __name__ == "__main__":
    SiteBuilder(CONSTRAINTS_FILE).build()
