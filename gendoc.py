from jinja2 import Environment, FileSystemLoader, select_autoescape
from rdflib import Namespace, BNode, RDF, RDFS, Graph
from rdflib.compare import to_canonical_graph
from copy import copy
from hashlib import blake2b
import json
import sys

S223 = Namespace("http://data.ashrae.org/standard223#")
SH = Namespace("http://www.w3.org/ns/shacl#")

FOLLOW_PROPS = [
    SH["property"],
    SH["or"],
    SH["and"],
    SH["not"],
    SH["xone"],
    SH["xor"],
    SH["sparql"],
    SH["rule"],
    SH["qualifiedValueShape"],
    SH["node"],
]

STABLE_IDS = {}

def walk_list(g, node):
    """Given the head of an RDF list, yield each of the nodes."""
    while node != RDF.nil:
        yield g.value(node, RDF.first)
        node = g.value(node, RDF.rest)

def bind_namespaces(g):
    """Bind the namespaces of the graph to the prefixes in the graph."""
    g.bind("s223", S223)
    g.bind("sh", SH)

def stable_id(g, bnode):
    """Returns a stable hex key for the given bnode."""
    local_graph = g.cbd(bnode)
    h = blake2b()
    for (s, p, o) in sorted(local_graph.triples((None, None, None))):
        h.update(f"{s}{p}{o}".encode("utf-8"))
    return h.hexdigest()

def simplify_node(g, node):
    if isinstance(node, BNode):
        return stable_id(g, node)
    return g.namespace_manager.qname(node)

def meaningful(g, node):
    g_copy = copy(g)
    g_copy.remove((None, SH["class"], node))
    g_copy.remove((None, RDFS["subClassOf"], node))
    abbr = stable_id(g, node) if isinstance(node, BNode) else g.namespace_manager.qname(node)
    strg = g_copy.serialize(format="turtle")
    return node in g_copy.all_nodes() or abbr in strg

def get_all_constraints(g):
    for node_shape in g.subjects(RDF["type"], SH["NodeShape"]):
        if node_shape in S223:
            yield node_shape
    for property_shape in g.subjects(RDF["type"], SH["PropertyShape"]):
        if property_shape in S223:
            yield property_shape
    for sproperty in g.subjects(RDF["type"], RDF["Property"]):
        if sproperty in S223:
            yield sproperty
    for rule in g.objects(SH["rule"]):
        if rule in S223:
            yield rule

def get_subgraph(g, node):
    """Return a subgraph of g starting at node."""
    subgraph = Graph()
    bind_namespaces(subgraph)
    to_visit = [node]
    for triple in g.triples((node, None, None)):
        subgraph.add(triple)
        if triple[1] in FOLLOW_PROPS:
            to_visit.append(triple[2])
    while to_visit:
        n = to_visit.pop()
        for triple in g.triples((n, None, None)):
            subgraph.add(triple)
            if triple[1] in FOLLOW_PROPS:
                to_visit.append(triple[2])
    for constraint in get_all_constraints(g):
        if constraint == node:
            continue
        other_subgraph = g.cbd(constraint)
        bind_namespaces(other_subgraph)
        if not meaningful(other_subgraph, node):
            continue
        subgraph += other_subgraph
    return subgraph

class Definition:
    def __init__(self, g, node):
        self.g = g
        self.node = node
        self.name = self.get_name()
        self.label = self.get_label()
        self.immediate_subgraph = self.get_immediate_subgraph()
        self.subgraph = self.get_subgraph()
        self.see_alsos = self.get_see_alsos()
        STABLE_IDS[self.node] = self.name

    def get_name(self):
        if isinstance(self.node, BNode) and "If the relation hasProperty is present" in self.get_subgraph().serialize(format="turtle"):
            #import q ; q.d()
            print(self.get_subgraph().serialize(format="turtle"))
            print(self.node)
            #raise ValueError("Found a property shape with a hasProperty constraint")
        return simplify_node(self.g, self.node)

    def get_label(self):
        name_or_label = self.g.value(self.node, SH["name"]) or self.g.value(self.node, RDFS["label"])
        message_or_comment = self.g.value(self.node, SH["message"]) or self.g.value(self.node, RDFS.comment)
        return name_or_label or message_or_comment or "Definition"

    def get_immediate_subgraph(self):
        subgraph = self.g.cbd(self.node)
        bind_namespaces(subgraph)
        return subgraph

    def get_subgraph(self):
        subgraph = get_subgraph(self.g, self.node)
        bind_namespaces(subgraph)
        return subgraph

    def get_see_alsos(self):
        see_alsos = set()
        for s, o in self.subgraph.subject_objects():
            if s != self.node and (s, RDF["type"], S223.Class) in self.subgraph:
                see_alsos.add(self.g.namespace_manager.qname(s))
            if o != self.node and (o, RDF["type"], S223.Class) in self.subgraph:
                see_alsos.add(self.g.namespace_manager.qname(o))
        return sorted(list(see_alsos))

    def to_dict(self):
        return {
            "class": None if isinstance(self.node, BNode) else self.node,
            "name": self.name,
            "label": self.label,
            "immediate_subgraph": self.immediate_subgraph,
            "subgraph": self.subgraph,
            "see_alsos": self.see_alsos,
        }

class NodeShapeDefinition(Definition):
    def get_label(self):
        name_or_label = self.g.value(self.node, SH["name"]) or self.g.value(self.node, RDFS["label"])
        message_or_comment = self.g.value(self.node, SH["message"]) or self.g.value(self.node, RDFS.comment)
        return name_or_label or message_or_comment or "Node Shape"

class PropertyShapeDefinition(Definition):
    def get_label(self):
        name_or_label = self.g.value(self.node, SH["name"]) or self.g.value(self.node, RDFS["label"])
        message_or_comment = self.g.value(self.node, SH["message"]) or self.g.value(self.node, RDFS.comment)
        return name_or_label or message_or_comment or "Property Shape"

    def get_immediate_subgraph(self):
        subgraph = self.g.cbd(self.node)
        has_interpretable_subject = False
        if isinstance(self.node, BNode):
            query = """
            SELECT ?owner WHERE {
                ?owner (sh:and|sh:or|sh:not|sh:xor|sh:xone|rdf:first|rdf:rest)*/sh:property ?property .
            }"""
            for row in self.g.query(query, initBindings={"property": self.node}):
                if isinstance(row["owner"], BNode):
                    continue
                subgraph.add((row["owner"], SH["property"], self.node))
                has_interpretable_subject = True
            if not has_interpretable_subject:
                return None
        bind_namespaces(subgraph)
        return subgraph

class RuleDefinition(Definition):
    def get_label(self):
        name_or_label = self.g.value(self.node, SH["name"]) or self.g.value(self.node, RDFS["label"])
        message_or_comment = self.g.value(self.node, SH["message"]) or self.g.value(self.node, RDFS.comment)
        return name_or_label or message_or_comment or "Rule"

    def get_immediate_subgraph(self):
        subgraph = self.g.cbd(self.node)
        if isinstance(self.node, BNode):
            subject_of_rule = next(self.g.subjects(predicate=SH["rule"], object=self.node), None)
            if subject_of_rule:
                subgraph.add((subject_of_rule, SH["rule"], self.node))
        bind_namespaces(subgraph)
        return subgraph

def main():
    g = Graph()
    for filename in sys.argv[1:]:
        print(f"Loading {filename}")
        g.parse(filename, format="turtle")
    bind_namespaces(g)
    g = to_canonical_graph(g)
    g.skolemize().serialize("/tmp/canonical.ttl", format="turtle")
    # write a list of all subjects to /tmp/gendoc_subjects.txt
    with open("/tmp/gendoc_subjects.txt", "w") as f:
        for s in sorted(set(g.subjects())):
            f.write(f"{s}\n")
    env = Environment(
        loader=FileSystemLoader('templates'),
        autoescape=select_autoescape()
    )
    template = env.get_template("index.html")

    definitions = []
    prop_defns = []
    seen = set()

    # Process classes (NodeShapes that are classes)
    for s223class in g.subjects(predicate=RDF["type"], object=S223["Class"]):
        print(f"Generating class {s223class}")
        definition = NodeShapeDefinition(g, s223class)
        definitions.append(definition)

    # Process NodeShapes that are not classes
    for node_shape in set(g.subjects(predicate=RDF["type"], object=SH.NodeShape)):
        if (node_shape, RDF["type"], S223["Class"]) in g:
            continue

        print(f"Generating node shape {node_shape}")
        node_name = simplify_node(g, node_shape)
        if node_name in seen:
            continue
        seen.add(node_name)

        definition = NodeShapeDefinition(g, node_shape)
        prop_defns.append(definition)

    # Process compound shapes in NodeShapes (sh:or, sh:and, sh:xone)
    for node_shape in set(g.subjects(predicate=RDF["type"], object=SH.NodeShape)):
        constraints = list(g.objects(subject=node_shape, predicate=SH["or"] | SH["and"] | SH["xone"]))
        for compound_shape in constraints:
            node_name = simplify_node(g, compound_shape)
            if node_name in seen:
                continue
            seen.add(node_name)

            desc_set = {g.value(s, SH.property / RDFS.comment) for s in walk_list(g, compound_shape)}
            desc = ' '.join(filter(None, desc_set)) or g.namespace_manager.qname(compound_shape)
            definition = Definition(g, compound_shape)
            definition.label = desc
            prop_defns.append(definition)

    # Process PropertyShapes
    for property_shape in set(g.objects(predicate=SH["property"])):
        node_name = simplify_node(g, property_shape)
        print(f"Generating property shape {property_shape} {node_name}")

        if node_name in seen:
            continue
        seen.add(node_name)

        definition = PropertyShapeDefinition(g, property_shape)
        if definition.immediate_subgraph is not None:
            prop_defns.append(definition)

    # Process Rules
    for rule in set(g.objects(predicate=SH["rule"])):
        node_name = simplify_node(g, rule)
        if node_name in seen:
            continue
        seen.add(node_name)

        print(f"Generating rule {rule} {node_name}")
        definition = RuleDefinition(g, rule)
        prop_defns.append(definition)

    # Now render the template
    with open("index.html", "w") as f:
        f.write(template.render(
            concepts=[d.to_dict() for d in definitions],
            property_shapes=[d.to_dict() for d in prop_defns],
        ))

    json.dump(STABLE_IDS, open("stable_ids.json", "w"), indent=2)

if __name__ == "__main__":
    main()
