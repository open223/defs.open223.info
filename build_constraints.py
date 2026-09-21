"""Build constraints.json from the checked-in ontology.

Usage: python build_constraints.py [ontology.ttl] [constraints.json]

Every named subject in the ontology becomes a concept, and every SHACL
constraint or rule reachable from a concept is added as well so that the
site can define an anchor for each stable ID.  Blank-node IDs are derived
from RDFC-1.0 canonicalization (see constraints.py), so rebuilding from an
equivalent graph reproduces the same IDs.

The output is:

    {
        "ontology": {"uri": ..., "version": ..., "source": ...},
        "concepts": {<concept>: {...}, ...}
    }

where "version" is the owl:versionInfo of the ontology declaration.
"""

import hashlib
import json
import sys
from pathlib import Path

from rdflib import OWL, RDF, Graph, URIRef

from constraints import ConstraintExtractor

ONTOLOGY_FILE = "ontologies/223p.ttl"
OUTPUT_FILE = "constraints.json"


def ontology_metadata(graph: Graph, source: str) -> dict:
    """Describe the ontology this site was built from.

    A graph compiled by tools/compile-223p.py declares a single owl:Ontology
    carrying a real owl:versionInfo, and that is what gets reported.

    The publication's canonical graph is a merge of 19 source files: it
    declares 18 ontologies, nine of which are never owl:imports-ed, so there
    is no root to name and their versionInfo is boilerplate.  Fall back to a
    digest of the file, which is what actually determines the anchors anyway.
    """
    ontologies = sorted(graph.subjects(RDF.type, OWL.Ontology))
    if not ontologies:
        sys.exit(f"{source} does not declare an owl:Ontology")

    if len(ontologies) == 1:
        version = graph.value(ontologies[0], OWL.versionInfo)
        if version is None:
            sys.exit(f"{ontologies[0]} has no owl:versionInfo in {source}")
        return {"uri": str(ontologies[0]), "version": str(version), "source": source}

    digest = hashlib.sha256(Path(source).read_bytes()).hexdigest()[:12]
    return {
        "uri": None,
        "version": f"sha256:{digest}",
        "source": source,
        "ontologies": len(ontologies),
    }


def build(ontology_file: str) -> dict:
    graph = Graph().parse(ontology_file, format="turtle")
    metadata = ontology_metadata(graph, ontology_file)

    extractor = ConstraintExtractor(graph)
    for subject in sorted({s for s in graph.subjects() if isinstance(s, URIRef)}):
        extractor.get_constraints(subject)

    return {"ontology": metadata, "concepts": extractor.as_dict()}


def main():
    ontology_file = sys.argv[1] if len(sys.argv) > 1 else ONTOLOGY_FILE
    output_file = sys.argv[2] if len(sys.argv) > 2 else OUTPUT_FILE

    data = build(ontology_file)
    with open(output_file, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    print(
        f"Wrote {output_file} with {len(data['concepts'])} concepts "
        f"from {data['ontology']['uri']} ({data['ontology']['version']})"
    )


if __name__ == "__main__":
    main()
