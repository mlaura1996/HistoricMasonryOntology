"""Runs the HMO SWRL rules with Pellet on the four Castelnuovo masonry types.

    python tools/check_rules_with_pellet.py ontology.ttl [--json out.json] [--dump kb.nt]

Each type is instantiated as the rules expect it: a MasonryWall with a
RepresentativeVolumeElement, a Pattern whose dominant entities are the
named constants the score rules match on, a Units individual carrying the
minimum and maximum unit length, a MasonryQualityIndex, and one
HomogenisedMechanicalProperty individual per derived quantity.

The test individuals are written with rdflib, not with owlready2, so that
every literal carries exactly the datatype of the property range: owlready2
writes a Python float as xsd:double, which OWL 2 treats as disjoint from
xsd:float and Pellet then reports as an inconsistency.
"""
import json
import os
import sys
import tempfile

import owlready2 as ow
import rdflib
from rdflib import RDF, OWL, XSD, Literal, URIRef

HMO = "https://w3id.org/hmo#"
T = "http://example.org/castelnuovo-test#"
SAREF_HAS_VALUE = "https://saref.etsi.org/core/hasValue"
h = lambda x: URIRef(HMO + x)
t = lambda x: URIRef(T + x)

# Unit length range in cm, chosen so that (min + max) / 2 falls in the
# category assigned by the survey: small < 20, medium 20-40, large >= 40.
UNIT_LENGTH = {"small": (10.0, 20.0), "medium": (20.0, 40.0), "large": (40.0, 60.0)}

TYPES = {
    "A": {"units": "medium",
          "dominant": ["SquaredSoftstone", "LimeMortarJoints",
                       "PartiallyContinuousHorizontalJoints", "PartiallyStaggeredJoints"],
          "sparse": ["HeadersBondUnits"]},
    "B": {"units": "medium",
          "dominant": ["RoughlyCutStone", "IrregularSoftstone", "LimeMortarJoints",
                       "NotContinuousHorizontalJoints", "PartiallyStaggeredJoints"],
          "sparse": ["HeadersBondUnits"]},
    "C": {"units": "small",
          "dominant": ["RoughlyCutStone", "IrregularSoftstone", "LimeMortarJoints",
                       "NotContinuousHorizontalJoints", "VerticallyAlignedJoints", "NoHeaders"],
          "sparse": []},
    "D": {"units": "medium",
          "dominant": ["RoughlyCutStone", "IrregularSoftstone", "LimeMortarJoints",
                       "NotContinuousHorizontalJoints", "PartiallyStaggeredJoints"],
          "sparse": ["HeadersBondUnits"]},
}
PROPERTIES = {"E": "YoungModulus", "fc": "CompressiveStrength",
              "G": "ShearModulus", "tau": "ShearStrengthTC"}
DIRS = ("Vertical", "OutOfPlane", "InPlane")


def build_abox():
    a = rdflib.Graph()
    for k, spec in TYPES.items():
        wall, rve, pat, units, mqi = (t(f"{n}_{k}") for n in ("Wall", "RVE", "Pattern", "Units", "MQI"))
        for ind, cls in ((wall, "MasonryWall"), (rve, "RepresentativeVolumeElement"),
                         (pat, "Pattern"), (units, "Units"), (mqi, "MasonryQualityIndex")):
            a.add((ind, RDF.type, OWL.NamedIndividual)); a.add((ind, RDF.type, h(cls)))
        lo, hi = UNIT_LENGTH[spec["units"]]
        a.add((units, h("unitsLengthHasMinimumValue"), Literal(lo, datatype=XSD.float)))
        a.add((units, h("unitsLengthMaximumValue"), Literal(hi, datatype=XSD.float)))
        a.add((wall, h("hasRepresentativeVolumeElement"), rve))
        a.add((wall, h("hasMasonryQualityIndex"), mqi))
        a.add((rve, h("hasPattern"), pat))
        a.add((pat, h("hasDominantPatternEntities"), units))
        for c in spec["dominant"]:
            a.add((pat, h("hasDominantPatternEntities"), h(c)))
        for c in spec["sparse"]:
            a.add((pat, h("hasSparsePatternEntities"), h(c)))
        for key, cls in PROPERTIES.items():
            p = t(f"{key}_{k}")
            a.add((p, RDF.type, OWL.NamedIndividual)); a.add((p, RDF.type, h(cls)))
            a.add((rve, h("hasHomogenisedMechanicalProperty"), p))
    return a


def main():
    path = sys.argv[1]
    arg = lambda f: sys.argv[sys.argv.index(f) + 1] if f in sys.argv else None

    kb = rdflib.Graph()
    kb.parse(path, format="turtle")
    declared = set(kb.subjects())
    abox = build_abox()
    used = {o for o in abox.objects() if isinstance(o, URIRef) and str(o).startswith(HMO)}
    missing = sorted(str(u).split("#")[-1] for u in used if u not in declared)
    if missing:
        print("terms used by the test data but absent from the ontology:", missing)
    kb += abox

    dump = arg("--dump") or os.path.join(tempfile.gettempdir(), "hmo_kb_for_pellet.nt")
    kb.serialize(dump, format="nt", encoding="utf-8")

    world = ow.World()
    world.get_ontology("file://" + dump.replace("\\", "/")).load(format="ntriples")
    try:
        ow.sync_reasoner_pellet(world, infer_property_values=True,
                                infer_data_property_values=True, debug=0)
    except ow.OwlReadyInconsistentOntologyError:
        print("PELLET: knowledge base INCONSISTENT")
        print(f"   explain with: java -cp <pellet jars> pellet.Pellet explain --inconsistent {dump}")
        return 2
    except Exception as exc:                  # noqa: BLE001
        print("PELLET FAILED:", type(exc).__name__, str(exc)[:600])
        return 3

    has_value = world[SAREF_HAS_VALUE]
    report = {}
    for k in TYPES:
        mqi, wall = world[T + f"MQI_{k}"], world[T + f"Wall_{k}"]
        tot = {d: sorted(float(v) for v in getattr(mqi, f"MQITotal{d}", []) or []) for d in DIRS}
        on_wall = {d: sorted(float(v) for v in getattr(wall, f"MQITotal{d}", []) or []) for d in DIRS}
        vals = {key: sorted(float(v) for v in has_value[world[T + f"{key}_{k}"]]) for key in PROPERTIES}
        report[k] = {"mqi_total": tot, "mqi_total_on_wall": on_wall, "properties": vals}
        print(f"type {k}: MQI totals {tot}")
        if any(on_wall.values()):
            print(f"        totals asserted on the WALL {on_wall}")
        print(f"        properties {vals}")
    if arg("--json"):
        json.dump(report, open(arg("--json"), "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
