"""Extract the SHACL constraints and rules attached to each 223P concept.

This is a port of ``publication/constraints.py`` from the 223standard
repository.  The two copies must generate identical stable IDs: the
publication links to ``https://defs.open223.info#<stable_id>`` and this site
must define the matching anchors.

Named resources get their qualified name (``s223:Equipment``) as the ID.
Blank-node constraints get ``b-<label>`` where the label comes from RDFC-1.0
canonicalization (``b-c14n42``), so the ID depends only on the structure of
the graph and not on the labels a particular parser happened to assign.
"""

from contextlib import redirect_stdout
from io import StringIO

from rdfcanon import RDFCanon, RDFCanonTimeTicker
from rdflib import RDF, RDFS, SH, BNode, Dataset, Graph, Literal, URIRef

CANONICALIZATION_TIMEOUT_MS = 120_000


def qname(graph: Graph, uri: URIRef) -> str:
    """The prefixed name of ``uri`` under the graph's namespace bindings.

    RDFLib refuses to split URIs whose local part is not a valid XML name,
    such as ``s223:FiberEthernet-QSFP+``.  Those fall back to the longest
    bound namespace that prefixes the URI, which yields the same ``prefix:name``
    RDFLib would have produced for a well-formed local part.
    """
    try:
        return graph.namespace_manager.qname(uri)
    except (ValueError, KeyError):
        pass
    matches = [(prefix, str(ns)) for prefix, ns in graph.namespaces() if uri.startswith(ns)]
    if not matches:
        raise ValueError(f"No namespace bound for {uri}")
    prefix, namespace = max(matches, key=lambda m: len(m[1]))
    return f"{prefix}:{uri[len(namespace):]}"


class FoundConstraints:
    def __init__(self, graph: Graph, simple_constraints=None, complex_constraints=None, rules=None):
        self.simple_constraints = set(simple_constraints) if simple_constraints else set()
        self.complex_constraints = set(complex_constraints) if complex_constraints else set()
        self.rules = set(rules) if rules else set()
        self.graph = graph

    def merge(self, other):
        """Merge another FoundConstraints into this one."""
        self.simple_constraints.update(other.simple_constraints)
        self.complex_constraints.update(other.complex_constraints)
        self.rules.update(other.rules)


class ResolvedFoundConstraints(FoundConstraints):
    def __init__(self, concept: URIRef, found: FoundConstraints):
        super().__init__(found.graph, found.simple_constraints, None, found.rules)
        self.concept = concept
        self.label = str(
            self.graph.value(concept, RDFS.label)
            or (self.graph.qname(concept) if isinstance(concept, URIRef) else None)
            or concept
        )
        self.labels = {}
        self.stable_ids = {}
        self.cbds = {}
        self.stable_id = self.get_stable_id(concept)

        self._gather_labels()
        self._gather_stable_ids()
        self._gather_cbds()

    def as_dict(self):
        return {
            "simple_constraints": sorted(self.simple_constraints),
            "complex_constraints": sorted(self.complex_constraints),
            "rules": sorted(self.rules),
            "label": str(self.label),
            "stable_id": self.stable_id,
            "labels": {str(k): self.labels[k] for k in sorted(self.labels)},
            "stable_ids": {str(k): self.stable_ids[k] for k in sorted(self.stable_ids)},
            "cbd": self.serialize(self.graph.cbd(self.concept)),
            "cbds": {str(k): self.serialize(self.cbds[k]) for k in sorted(self.cbds)},
        }

    def serialize(self, subgraph: Graph) -> str:
        """Serialize a subgraph as Turtle using the source graph's prefixes.

        ``Graph.cbd()`` returns a graph with no namespace bindings, and the
        serializer's auto-generated ``ns1``/``ns2`` prefixes are assigned in an
        order that varies from run to run.
        """
        for prefix, namespace in self.graph.namespaces():
            subgraph.bind(prefix, namespace)
        return subgraph.serialize(format="turtle")

    def _gather_labels(self):
        for constraint in self.simple_constraints | self.complex_constraints | self.rules:
            label = self.graph.value(constraint, RDFS.comment)
            # remove newlines
            label = str(label).replace("\n", " ") if label else None
            self.labels[constraint] = label

    def _gather_stable_ids(self):
        for constraint in self.simple_constraints | self.complex_constraints | self.rules:
            stable_id = self.get_stable_id(constraint)
            assert stable_id is not None
            self.stable_ids[constraint] = stable_id

    def _gather_cbds(self):
        for constraint in self.simple_constraints | self.complex_constraints | self.rules:
            self.cbds[constraint] = self.graph.cbd(constraint)

    def get_stable_id(self, constraint):
        """Generate a stable ID for a constraint."""
        assert not isinstance(constraint, Literal), f"Expected URIRef or bnode, got {constraint}"
        if isinstance(constraint, URIRef):
            return qname(self.graph, constraint)
        return f"b-{constraint}"


class ConstraintExtractor:
    def __init__(self, graph: Graph):
        # Parser-assigned blank node labels are temporary. Canonicalize them
        # before extracting constraints so generated links remain stable when
        # the same RDF graph is serialized and parsed again.
        canonical_ids = self._canonicalize_blank_nodes(graph)

        # Rebuild the graph with the canonical labels while preserving the
        # namespace bindings used to render named resources as qualified names.
        self.graph = Graph()
        for prefix, namespace in graph.namespaces():
            self.graph.bind(prefix, namespace)
        for subject, predicate, object_ in graph:
            if isinstance(subject, BNode):
                subject = BNode(canonical_ids[str(subject)])
            if isinstance(object_, BNode):
                object_ = BNode(canonical_ids[str(object_)])
            self.graph.add((subject, predicate, object_))
        self.constraints = {}

    @staticmethod
    def _canonicalize_blank_nodes(graph):
        """Return the RDFC-1.0 mapping from input blank nodes to canonical IDs."""
        # rdfcanon operates on an RDF Dataset. This source is an RDFLib Graph,
        # so all of its triples are copied into the dataset's default graph.
        dataset = Dataset(default_union=True)
        for triple in graph:
            dataset.add(triple)

        # The ticker limits worst-case work on graphs with highly symmetric
        # blank-node structures. Its timeout is expressed in milliseconds.
        canonicalizer = RDFCanon(
            hash_algorithm="sha256",
            dataset=dataset,
            ticker=RDFCanonTimeTicker(CANONICALIZATION_TIMEOUT_MS),
        )
        try:
            # rdfcanon 1.0.0 prints expected first-degree hash collisions.
            with redirect_stdout(StringIO()):
                canonicalizer.canonize()
        except TimeoutError as error:
            raise RuntimeError(
                f"RDF canonicalization exceeded {CANONICALIZATION_TIMEOUT_MS // 1000} seconds"
            ) from error

        # rdfcanon represents canonical labels as "_:c14n0". RDFLib's BNode
        # constructor expects only the identifier portion, such as "c14n0".
        return {
            blank_id: canonical_id.removeprefix("_:")
            for blank_id, canonical_id in (
                canonicalizer.blank_id_to_normalized_blank_ids_map.items()
            )
        }

    def get_constraints(self, concept: URIRef) -> ResolvedFoundConstraints:
        if concept in self.constraints:
            return self.constraints[concept]

        found = self.get_nodeshape_constraints(concept)

        while True:
            initial_size = len(found.complex_constraints)

            # Iterate over a copy: merging may grow complex_constraints.
            for constraint in list(found.complex_constraints):
                if self.constraint_is_list(constraint):
                    found.merge(self.get_constraint_list(constraint))
                else:
                    found.merge(self.get_nodeshape_constraints(constraint))

            # Fixed point: no new constraints were discovered.
            if len(found.complex_constraints) == initial_size:
                break

        resolved = ResolvedFoundConstraints(concept, found)
        self.constraints[concept] = resolved
        return resolved

    def as_dict(self):
        """All extracted concepts, plus every constraint and rule they reference.

        Constraints and rules are resolved as concepts in their own right so
        that the site defines an anchor for each stable ID it hands out.
        """
        pending = list(self.constraints.values())
        while pending:
            defn = pending.pop()
            for constraint in sorted(defn.simple_constraints | defn.rules):
                if constraint not in self.constraints:
                    pending.append(self.get_constraints(constraint))
        return {str(name): c.as_dict() for name, c in self.constraints.items()}

    def constraint_is_list(self, constraint: URIRef):
        return self.graph.value(constraint, RDF.first) is not None

    def get_constraint_list(self, constraint: URIRef) -> FoundConstraints:
        found = FoundConstraints(self.graph)
        for node in self.walk_list(constraint):
            found.merge(self.get_nodeshape_constraints(node))
        return found

    def walk_list(self, node):
        """Given the head of an RDF list, yield each of the nodes."""
        while node != RDF.nil:
            yield self.graph.value(node, RDF.first)
            node = self.graph.value(node, RDF.rest)

    def get_nodeshape_constraints(self, nodeshape: URIRef) -> FoundConstraints:
        """
        Constraints on a node shape are:
        - ?nodeshape sh:property ?constraint
        - ?nodeshape sh:sparql ?constraint
        - ?constraint sh:targetClass ?nodeshape
        - ?nodeshape sh:or|sh:and|sh:not|sh:xone ?constraint

        Do *not* include any constraint with an sh:rule.
        """
        simple_constraints = []
        complex_constraints = []
        rules = []

        # Start with property and sparql constraints on the node shape
        for constraint in self.graph.objects(nodeshape, SH.property | SH.sparql):
            if self.graph.value(constraint, RDFS.comment):
                simple_constraints.append(constraint)
            else:
                complex_constraints.append(constraint)

        # Get "external" constraints that point to our nodeshape.
        for constraint in self.graph.subjects(SH.targetClass, nodeshape):
            if self.graph.value(constraint, RDFS.comment):
                simple_constraints.append(constraint)
            else:
                complex_constraints.append(constraint)

        # Get "compound" constraints that are part of our nodeshape.
        for constraint in self.graph.objects(nodeshape, SH["or"] | SH["and"] | SH["not"] | SH.xone):
            if self.graph.value(constraint, RDFS.comment):
                simple_constraints.append(constraint)
            else:
                complex_constraints.append(constraint)

        # get rules
        for rule in self.graph.objects(nodeshape, SH.rule):
            rules.append(rule)

        return FoundConstraints(self.graph, simple_constraints, complex_constraints, rules)
