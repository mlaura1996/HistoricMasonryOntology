"""Corrects the SWRL rules of the Historic Masonry Ontology so that they can
be executed by a reasoner, and records every change.

    python fix_hmo_rules.py <in.ttl> <out.ttl> [--only F1,F2,...]

Corrections (rule text fixed to do what the rule evidently intends):
  F1  unit-dimension rules: the second length atom read the MINIMUM again
      instead of the maximum, and the "average" was divide(min, max)
      instead of (min + max) / 2.
  F2  the three MQI total rules: swrlb:multiply had two arguments, missing
      the sum it is meant to scale; in MQI_OutOfPlane the horizontal-joint
      score was bound to ?HoP but summed as ?HJoP.
  F3  the four property formulas: ?Rpv (lower case) was a free variable,
      so a property of one RVE took the quality index of any wall. The RVE
      and the index are now joined through the wall that owns both.
  F4  score rules: the score was asserted on the wall (?wl), although every
      score property has MasonryQualityIndex as its domain and the total
      rules read the scores from the index. Scores now go on the index.
  F5  numeric literals in rule built-ins and heads typed as xsd:float,
      consistently with the declared ranges; 13 formula constants were
      untyped strings, on which arithmetic built-ins cannot operate.
Extensions (vocabulary the case study needs and the ontology lacks):
  F6  MQI_SM_SquaredSoftStone: unit material score for squared soft stone,
      which had no rule (only the irregular variant did).
  F7  NoHeaders and MQI_WC_NoHeaders: absence of transverse connection for
      masonry that is not rubble, previously only expressible through the
      rubble-stone constant.
  F9  IrregularHardstone and MQI_SM_IrregularHardStone: unit material score
      for hard stone that is not squared. The hard-stone score was reachable
      only through SquaredHardstone, which also sets a squared unit shape,
      so irregular or roughly cut hard stone (the SERA-AIMS sandstone)
      could not be scored without contradicting its shape. Material only:
      the shape is given by its own constant (RoughlyCutStone, RubbleStones).
"""
import sys
import rdflib
from rdflib import RDF, RDFS, OWL, XSD, BNode, Literal, URIRef
from rdflib.collection import Collection

S = "http://www.w3.org/2003/11/swrl#"
SB = "http://www.w3.org/2003/11/swrlb#"
HMO = "https://w3id.org/hmo#"
V = "http://www.semanticweb.org/owl/owlapi/turtle#"
sw = lambda x: URIRef(S + x)
h = lambda x: URIRef(HMO + x)
var = lambda x: URIRef(V + x)

src, dst = sys.argv[1], sys.argv[2]
only = set(sys.argv[sys.argv.index("--only") + 1].split(",")) if "--only" in sys.argv else None
on = lambda f: only is None or f in only

g = rdflib.Graph()
g.parse(src, format="turtle")
log = []


def rule(label):
    hits = [r for r in g.subjects(RDF.type, sw("Imp")) if str(g.value(r, RDFS.label)) == label]
    assert len(hits) == 1, (label, len(hits))
    return hits[0]


def items(node):
    return list(Collection(g, node)) if node is not None and node != RDF.nil else []


def set_items(subject, pred, new_items):
    """Replace an RDF list (rule body/head or builtin arguments)."""
    old = g.value(subject, pred)
    if old is not None and old != RDF.nil:
        Collection(g, old).clear()
        g.remove((subject, pred, old))
    head = BNode()
    Collection(g, head, new_items)
    g.add((subject, pred, head))


def ensure_var(name):
    v = var(name)
    g.add((v, RDF.type, sw("Variable")))
    return v


def prop_atom(prop, a1, a2, datavalued=False):
    a = BNode()
    g.add((a, RDF.type, sw("DatavaluedPropertyAtom" if datavalued else "IndividualPropertyAtom")))
    g.add((a, sw("propertyPredicate"), prop))
    g.add((a, sw("argument1"), a1))
    g.add((a, sw("argument2"), a2))
    return a


def args_of(atom):
    return items(g.value(atom, sw("arguments")))


def as_float(lit):
    return Literal(float(lit.toPython() if lit.datatype else str(lit)), datatype=XSD.float)


# --- F1 ----------------------------------------------------------------------
if on("F1"):
    for lab in ("MQI_SD_PresenceOfLittleUnits", "MQI_SD_PresenceOfMediumUnits", "MQI_SD_PresenceOfLargeUnits"):
        r = rule(lab)
        for a in items(g.value(r, sw("body"))):
            if g.value(a, sw("propertyPredicate")) == h("unitsLengthHasMinimumValue") \
                    and g.value(a, sw("argument2")) == var("maxVal"):
                g.set((a, sw("propertyPredicate"), h("unitsLengthMaximumValue")))
            if g.value(a, sw("builtin")) == URIRef(SB + "divide"):
                set_items(a, sw("arguments"), [var("avg"), var("sum"), Literal(2.0, datatype=XSD.float)])
        log.append(f"F1 {lab}: maximum length read with unitsLengthMaximumValue; avg = (min + max) / 2")

# --- F2 ----------------------------------------------------------------------
if on("F2"):
    for lab, sm in (("MQI_Vertical", "SMv"), ("MQI_OutOfPlane", "SMoP"), ("MQI_InPlane", "SMiP")):
        r = rule(lab)
        for a in items(g.value(r, sw("body"))):
            b = g.value(a, sw("builtin"))
            if b == URIRef(SB + "multiply"):
                set_items(a, sw("arguments"), [var("mlt"), var("sum"), var(sm)])
            if b == URIRef(SB + "add") and lab == "MQI_OutOfPlane":
                set_items(a, sw("arguments"), [var("HoP") if x == var("HJoP") else x for x in args_of(a)])
        log.append(f"F2 {lab}: total = sum of the six additive scores x unit material score"
                   + ("; ?HJoP renamed ?HoP" if lab == "MQI_OutOfPlane" else ""))

# --- F3 ----------------------------------------------------------------------
if on("F3"):
    wl = ensure_var("wl")
    for lab in ("YoungModulusMQI", "CompressiveStrenghMQI", "ShearModulusMQI", "ShearStrengthMQI"):
        r = rule(lab)
        new = []
        for a in items(g.value(r, sw("body"))):
            if g.value(a, sw("propertyPredicate")) == h("hasMasonryQualityIndex") \
                    and g.value(a, sw("argument1")) == var("Rpv"):
                new.append(prop_atom(h("hasRepresentativeVolumeElement"), wl, var("RpV")))
                new.append(prop_atom(h("hasMasonryQualityIndex"), wl, var("MQI")))
            else:
                new.append(a)
        set_items(r, sw("body"), new)
        log.append(f"F3 {lab}: RVE and quality index joined through the wall (?Rpv was free)")

# --- F4 ----------------------------------------------------------------------
if on("F4"):
    wl, mqi = ensure_var("wl"), ensure_var("MQI")
    for r in g.subjects(RDF.type, sw("Imp")):
        lab = str(g.value(r, RDFS.label))
        head = items(g.value(r, sw("head")))
        score_atoms = [a for a in head
                       if str(g.value(a, sw("propertyPredicate")) or "").startswith(HMO + "MQI")
                       and g.value(a, sw("argument1")) == wl]
        if not score_atoms:
            continue
        body = items(g.value(r, sw("body")))
        linked = any(g.value(a, sw("propertyPredicate")) == h("hasMasonryQualityIndex")
                     and g.value(a, sw("argument1")) == wl for a in body)
        if not linked:
            set_items(r, sw("body"), body + [prop_atom(h("hasMasonryQualityIndex"), wl, mqi)])
        for a in score_atoms:
            g.set((a, sw("argument1"), mqi))
        log.append(f"F4 {lab}: scores asserted on the quality index instead of the wall")

# --- F5 ----------------------------------------------------------------------
if on("F5"):
    n = 0
    for a in list(g.subjects(RDF.type, sw("BuiltinAtom"))):
        ar = args_of(a)
        if any(isinstance(x, Literal) and x.datatype != XSD.float for x in ar):
            set_items(a, sw("arguments"), [as_float(x) if isinstance(x, Literal) else x for x in ar])
            n += 1
    m = 0
    for a in list(g.subjects(RDF.type, sw("DatavaluedPropertyAtom"))):
        x = g.value(a, sw("argument2"))
        if isinstance(x, Literal) and x.datatype != XSD.float:
            g.set((a, sw("argument2"), as_float(x))); m += 1
    log.append(f"F5 numeric literals typed xsd:float: {n} built-in atoms, {m} property atoms")

# --- F8 ----------------------------------------------------------------------
# MasonryQualityIndex was declared both a subclass of, and disjoint with,
# HomogenisedMechanicalProperty, which makes the class unsatisfiable: any
# quality index individual turns the whole ontology inconsistent. Its own
# definition ("a visual method for assessing...") and its disjointness from
# the property classes say it is not a mechanical property, so the
# subclass axiom is the one removed.
if on("F8"):
    g.remove((h("MasonryQualityIndex"), RDFS.subClassOf, h("HomogenisedMechanicalProperty")))
    log.append("F8 removed MasonryQualityIndex subClassOf HomogenisedMechanicalProperty "
               "(contradicted the disjointness of the two classes)")

# --- F6 and F7 (extensions) -------------------------------------------------
def clone_rule(src_label, new_label, old_const, new_const, comment):
    r = rule(src_label)
    nr = BNode()
    g.add((nr, RDF.type, sw("Imp")))
    g.add((nr, RDFS.label, Literal(new_label)))
    g.add((nr, RDFS.comment, Literal(comment)))
    for t in g.objects(r, URIRef("http://swrl.stanford.edu/ontologies/3.3/swrla.owl#isRuleEnabled")):
        g.add((nr, URIRef("http://swrl.stanford.edu/ontologies/3.3/swrla.owl#isRuleEnabled"), t))
    for part in ("body", "head"):
        copies = []
        for a in items(g.value(r, sw(part))):
            c = BNode()
            for p, o in g.predicate_objects(a):
                if p == sw("arguments"):
                    continue
                g.add((c, p, new_const if o == old_const else o))
            if g.value(a, sw("arguments")) is not None:
                set_items(c, sw("arguments"), args_of(a))
            copies.append(c)
        set_items(nr, sw(part), copies)

if on("F6"):
    g.add((h("SquaredSoftstone"), RDF.type, OWL.NamedIndividual))
    clone_rule("MQI_SM_IrregularSoftStone", "MQI_SM_SquaredSoftStone",
               h("IrregularSoftstone"), h("SquaredSoftstone"),
               "Unit material score for soft stone (tuff, calcarenite) when the units are squared; "
               "the same score as the irregular soft-stone rule, since the material is the same.")
    log.append("F6 added MQI_SM_SquaredSoftStone (unit material 0.7 for squared soft stone)")

if on("F7"):
    cls = g.value(h("HeadersBondUnits"), RDF.type) or h("PatternEntities")
    if cls == OWL.NamedIndividual:
        cls = next((c for c in g.objects(h("HeadersBondUnits"), RDF.type) if c != OWL.NamedIndividual), h("PatternEntities"))
    g.add((h("NoHeaders"), RDF.type, OWL.NamedIndividual))
    g.add((h("NoHeaders"), RDF.type, cls))
    g.add((h("NoHeaders"), RDFS.label, Literal("No headers", lang="en")))
    g.add((h("NoHeaders"), RDFS.comment, Literal(
        "Absence of transverse connection between the leaves, for masonry that is not rubble stone.", lang="en")))
    clone_rule("MQI_WC_RubbleStones", "MQI_WC_NoHeaders", h("RubbleStones"), h("NoHeaders"),
               "Wall leaves connection score when no headers are present and the masonry is not rubble stone.")
    log.append(f"F7 added NoHeaders ({str(cls).split('#')[-1]}) and MQI_WC_NoHeaders (0, 0, 0)")

if on("F9"):
    g.add((h("IrregularHardstone"), RDF.type, OWL.NamedIndividual))
    g.add((h("IrregularHardstone"), RDF.type, h("Units")))
    g.add((h("IrregularHardstone"), RDFS.label, Literal("Irregular hardstone", lang="en")))
    g.add((h("IrregularHardstone"), RDFS.comment, Literal(
        "Hard stone units that are not squared (irregular or roughly cut), such as limestone or sandstone "
        "rubble. Sets the unit material only; the unit shape is given by its own pattern entity.", lang="en")))
    clone_rule("MQI_SM_SquaredHardStone", "MQI_SM_IrregularHardStone",
               h("SquaredHardstone"), h("IrregularHardstone"),
               "Unit material score for hard stone that is not squared: the same score as squared hard stone, "
               "since the unit material score depends on the material, not on the shape.")
    log.append("F9 added IrregularHardstone and MQI_SM_IrregularHardStone (unit material 1 for hard stone)")

g.serialize(dst, format="turtle", encoding="utf-8")
print("\n".join(log))
print(f"-> {dst}")
