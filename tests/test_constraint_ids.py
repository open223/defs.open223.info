"""Regression tests for canonical IDs assigned to blank-node constraints."""

import sys
from pathlib import Path

from rdflib import BNode, Graph, Namespace

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from constraints import ConstraintExtractor  # noqa: E402


EX = Namespace("http://example.com/")


def make_graph(reverse=False):
    """Build equivalent graphs whose constraints have distinct RDF paths."""
    graph = Graph()
    constraints = [(BNode(), EX.left), (BNode(), EX.right)]
    if reverse:
        constraints.reverse()
    for constraint, path in constraints:
        graph.add((EX.owner, EX.constraint, constraint))
        graph.add((constraint, EX.path, path))
    return graph


def ids_by_path(graph):
    """Index stable constraint IDs by path so transient blank IDs are ignored."""
    extractor = ConstraintExtractor(graph)
    return {
        extractor.graph.value(constraint, EX.path): extractor.get_constraints(
            constraint
        ).stable_id
        for constraint in extractor.graph.objects(EX.owner, EX.constraint)
    }


def test_constraint_ids_survive_reserialization():
    """Serialization and parsing must not change a constraint's generated ID."""
    original = make_graph()
    # RDFLib assigns new blank-node labels while parsing the Turtle output.
    # Canonicalization should recover the same structural IDs regardless.
    reparsed = Graph().parse(
        data=original.serialize(format="turtle"),
        format="turtle",
    )

    assert ids_by_path(original) == ids_by_path(reparsed)


def test_constraint_ids_do_not_depend_on_insertion_order():
    """Triple insertion order must not affect the generated constraint IDs."""
    assert ids_by_path(make_graph()) == ids_by_path(make_graph(reverse=True))


def test_blank_node_ids_use_canonical_labels():
    """Blank-node IDs come from RDFC-1.0 labels, never Python's hash()."""
    ids = set(ids_by_path(make_graph()).values())
    assert ids == {"b-c14n0", "b-c14n1"}
