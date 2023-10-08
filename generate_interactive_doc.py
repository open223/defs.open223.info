from jinja2 import Environment, FileSystemLoader, select_autoescape
from rdflib import Namespace, BNode, RDF, RDFS, Graph
from copy import copy
from hashlib import blake2b
import sys

S223 = Namespace("http://data.ashrae.org/standard223#")
SH = Namespace("http://www.w3.org/ns/shacl#")
RDF = RDF
RDFS = RDFS

def simplify_node(node):
    if isinstance(node, BNode):
        return stable_id(node)
    for prefix, namespace in g.namespace_manager.namespaces():
        if str(node).startswith(namespace):
            return prefix + ":" + str(node)[len(namespace):]
    return node

def stable_id(bnode):
    """
    Returns a stable hex key for the given bnode
    """
    local_graph = g.cbd(bnode)
    h = blake2b()
    for (_, p, o) in sorted(local_graph.triples((None, None, None))):
        if isinstance(o, BNode):
            continue
        h.update(f"{p}{o}".encode("utf-8"))
    return h.digest().hex()


def meaningful(g, node):
    g = copy(g)
    g.remove((None, SH["class"], node))
    g.remove((None, RDFS["subClassOf"], node))
    if isinstance(node, BNode):
        abbr = stable_id(node)
    else:
        abbr = g.namespace_manager.qname(node)
    strg = g.serialize(format="turtle")
    return node in g.all_nodes() or abbr in strg

def bind_namespaces(g):
    """
    Bind the namespaces of the graph to the prefixes in the graph.
    """
    g.bind("s223", S223)
    g.bind("sh", SH)

FOLLOW_PROPS = [
    SH["property"],
    SH["or"],
]


def get_subgraph(g, node):
    """
    Return a subgraph of g starting at node.
    """
    subgraph = Graph()
    bind_namespaces(subgraph)
    to_visit = [node]
    # TODO: switch with g.cbd?
    for triple in g.triples((node, None, None)):
        subgraph.add(triple)
        if triple[1] in FOLLOW_PROPS:
            to_visit.append(triple[2])

    # this traversal will pull in definitions of all j
    while to_visit:
        n = to_visit.pop()
        # for triple in g.cbd(n):
        #     subgraph.add(triple)
        #     if triple[1] in FOLLOW_PROPS:
        #         to_visit.append(triple[2])
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

g = Graph()
bind_namespaces(g)
g.parse(sys.argv[1], format="turtle")
# node = S223[sys.argv[2]]
env = Environment(
    loader=FileSystemLoader('templates'),
    autoescape=select_autoescape()
)
template = env.get_template("index.html")

defns = []
prop_defns = []

for s223class in g.subjects(predicate=RDF["type"], object=S223["Class"]):
    print(s223class)
    immediate_subgraph = g.cbd(s223class)
    bind_namespaces(immediate_subgraph)
    subgraph = get_subgraph(g, s223class)
    bind_namespaces(subgraph)
    see_alsos = set()
    for s, o in subgraph.subject_objects():
        if s != s223class and (s, RDF["type"], S223.Class) in subgraph:
            see_alsos.add(g.namespace_manager.qname(s))
        if o != s223class and (o, RDF["type"], S223.Class) in subgraph:
            see_alsos.add(g.namespace_manager.qname(o))
    try:
        label  = next(g.objects(predicate=RDFS["label"], subject=s223class))
    except StopIteration:
        label = "n/a"
    defns.append({
        "class": s223class,
        "name": g.namespace_manager.qname(s223class),
        "label": label,
        "immediate_subgraph": immediate_subgraph,
        "subgraph": subgraph,
        "see_alsos": sorted(list(see_alsos)),
    })

seen = set()

# TODO: do this for property shapes!
for property_shape in set(g.objects(predicate=SH["property"])):
    if isinstance(property_shape, BNode):
        node_name = stable_id(property_shape)
    else:
        node_name = simplify_node(property_shape)
    # avlid duplicates
    if node_name in seen:
        continue
    seen.add(node_name)

    immediate_subgraph = g.cbd(property_shape)
    bind_namespaces(immediate_subgraph)
    subgraph = get_subgraph(g, property_shape)
    bind_namespaces(subgraph)

    name_or_label = g.value(property_shape, SH["name"]) or g.value(property_shape, RDFS["label"])
    message_or_comment = g.value(property_shape, SH["message"]) or g.value(property_shape, RDFS.comment)
    label = name_or_label or message_or_comment or "Property Shape"
    prop_defns.append({
        "class": None if isinstance(property_shape, BNode) else property_shape,
        "name": node_name,
        "label": label,
        "immediate_subgraph": immediate_subgraph,
        "subgraph": subgraph,
        "see_alsos": [],
    })

# for rules
for rule in set(g.objects(predicate=SH["rule"])):
    if isinstance(rule, BNode):
        node_name = stable_id(rule)
    else:
        node_name = simplify_node(rule)
    # avoid duplicates
    if node_name in seen:
        continue
    seen.add(node_name)

    immediate_subgraph = g.cbd(rule)
    bind_namespaces(immediate_subgraph)
    subgraph = get_subgraph(g, rule)
    bind_namespaces(subgraph)

    # TODO: add "condition" to the rule graph?

    name_or_label = g.value(rule, SH["name"]) or g.value(rule, RDFS["label"])
    message_or_comment = g.value(rule, SH["message"]) or g.value(rule, RDFS.comment)
    label = name_or_label or message_or_comment or "Property Shape"
    prop_defns.append({
        "class": None if isinstance(rule, BNode) else rule,
        "name": node_name,
        "label": label,
        "immediate_subgraph": immediate_subgraph,
        "subgraph": subgraph,
        "see_alsos": [],
    })


with open("static/index.html", "w") as f:
    f.write(template.render(
        concepts=sorted(defns, key=lambda x: x['class']),
        property_shapes=sorted(prop_defns, key=lambda x: x['name']),
    ))
