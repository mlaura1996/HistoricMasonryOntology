# Changelog

## Unreleased — SWRL rules made executable

The SWRL rules as previously published could not be executed by a reasoner.
Run with Pellet on four masonry walls (the Castelnuovo di Porto case
study), the ontology was reported inconsistent; with the individual
defects isolated, several rules derived wrong values or values for every
wall at once. The rules have been corrected to do what they evidently
intend, and two gaps have been filled.

All four serialisations (`ontology.ttl`, `.nt`, `.owl`, `.jsonld`) are
regenerated from the corrected graph. The `.jsonld` omits 8 explicit
`rdf:type rdf:List` statements, which JSON-LD expresses through `@list`; no
information is lost.

### Corrections

- **F1, unit-dimension rules** (`MQI_SD_PresenceOf{Little,Medium,Large}Units`):
  the second length atom read `unitsLengthHasMinimumValue` again instead of
  `unitsLengthMaximumValue`, and the mean was `divide(min, max)` instead of
  `(min + max) / 2`.
- **F2, MQI totals** (`MQI_Vertical`, `MQI_OutOfPlane`, `MQI_InPlane`):
  `swrlb:multiply` had two arguments, so the total was the unit-material
  score alone instead of the sum of the six additive scores times it. In
  `MQI_OutOfPlane` the horizontal-joint score was bound to `?HoP` but
  summed as `?HJoP`.
- **F3, property formulas** (`YoungModulusMQI`, `CompressiveStrenghMQI`,
  `ShearModulusMQI`, `ShearStrengthMQI`): `?Rpv` differed from `?RpV` only by
  case and was therefore a free variable, so each property took the quality
  index of every wall. The RVE and the index are now joined through the wall.
- **F4, score rules** (all 26): scores were asserted on the wall although
  every score property has `MasonryQualityIndex` as its domain and the total
  rules read them from the index. They are now asserted on the index.
- **F5, literals**: numeric literals in rule built-ins and heads are typed
  `xsd:float`, as the property ranges declare. Thirteen formula constants
  were untyped strings, on which the arithmetic built-ins cannot operate,
  and `decimal`/`integer` values asserted into `float` properties make the
  ontology inconsistent in OWL 2.
- **F8, class hierarchy**: `MasonryQualityIndex` was declared both a
  subclass of and disjoint with `HomogenisedMechanicalProperty`, which made
  it unsatisfiable. Its definition describes a method of assessment, not a
  mechanical property, so the subclass axiom is removed.

### Additions (to review as design decisions)

- **F6**: `MQI_SM_SquaredSoftStone`, the unit-material score (0.7) for
  squared soft stone. The score existed only through the `IrregularSoftstone`
  constant, which also sets an irregular unit shape, so squared tuff
  masonry could not be scored without contradicting its shape.
- **F7**: `NoHeaders` and `MQI_WC_NoHeaders`, the absence of transverse
  connection (score 0) for masonry that is not rubble stone; before, it was
  only reachable through the `RubbleStones` constant.
- **F9**: `IrregularHardstone` and `MQI_SM_IrregularHardStone`, the
  unit-material score (1) for hard stone that is not squared. The score
  existed only through the `SquaredHardstone` constant, which also sets a
  squared unit shape, so irregular or roughly cut hard stone (the sandstone
  of the SERA-AIMS benchmark) could not be scored without contradicting its
  shape. The constant sets the material only; the shape is given by its own
  pattern entity.

### Evidence

Removing one correction at a time and running Pellet again:

| removed | result on 4 walls × 4 properties |
|---|---|
| F1 | 12 values wrong |
| F2 | 16 values wrong |
| F3 | 16 values with multiple values |
| F4 | inconsistent |
| F5 | inconsistent |
| F6 | 4 values missing |
| F7 | 4 values missing |
| F9 | SERA-AIMS masonry: no quality index derived, so no values |
| F8 | inconsistent |

With all corrections, Pellet derives one value per property for every wall,
equal within rounding to an independent Python implementation of the same
rules.

### Tools

- `tools/fix_swrl_rules.py` applies the corrections to `ontology.ttl`
  (each switchable with `--only`).
- `tools/lint_swrl_rules.py` checks every rule for unbound variables,
  built-in arity and variables differing only by case. A comparison
  built-in (`lessThan`...) now counts its first argument as used, which
  removes three false reports on the unit-dimension rules.
- `tools/check_rules_with_pellet.py` runs the rules with Pellet on the four
  example walls. Needs Java and `owlready2==0.48`.
