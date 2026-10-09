"""Static check of every SWRL rule in an ontology file: unbound variables,
built-in arity, undeclared properties/classes, variables differing only by
case. Variables live in the OWLAPI turtle namespace; constants in hmo#."""
import sys, collections
import rdflib
from rdflib import RDF, RDFS, OWL, URIRef

path = sys.argv[1]
g = rdflib.Graph(); g.parse(path, format='turtle')
S = 'http://www.w3.org/2003/11/swrl#'; u = lambda x: URIRef(S + x)
V = 'http://www.semanticweb.org/owl/owlapi/turtle#'
isvar = lambda t: str(t).startswith(V)
vn = lambda t: '?' + str(t)[len(V):]
short = lambda t: str(t).split('#')[-1]

declared_props = set(g.subjects(RDF.type, OWL.ObjectProperty)) | set(g.subjects(RDF.type, OWL.DatatypeProperty))
declared_cls = set(g.subjects(RDF.type, OWL.Class))
BIND = {'add', 'multiply', 'divide', 'pow', 'subtract'}
ARITY = {'add': (3, 99), 'multiply': (3, 99), 'divide': (3, 3), 'pow': (3, 3), 'subtract': (3, 3),
         'greaterThan': (2, 2), 'greaterThanOrEqual': (2, 2), 'lessThan': (2, 2), 'lessThanOrEqual': (2, 2)}

def atoms(lst):
    out = []
    while lst and lst != RDF.nil:
        a = g.value(lst, RDF.first); t = short(g.value(a, RDF.type))
        if t == 'ClassAtom':
            out.append(('class', g.value(a, u('classPredicate')), [g.value(a, u('argument1'))]))
        elif t in ('IndividualPropertyAtom', 'DatavaluedPropertyAtom'):
            out.append(('prop', g.value(a, u('propertyPredicate')), [g.value(a, u('argument1')), g.value(a, u('argument2'))]))
        elif t == 'BuiltinAtom':
            args = []; l = g.value(a, u('arguments'))
            while l and l != RDF.nil: args.append(g.value(l, RDF.first)); l = g.value(l, RDF.rest)
            out.append(('builtin', g.value(a, u('builtin')), args))
        lst = g.value(lst, RDF.rest)
    return out

total = 0
for r in sorted(g.subjects(RDF.type, u('Imp')), key=lambda r: str(g.value(r, RDFS.label))):
    label = str(g.value(r, RDFS.label)); problems = []
    body, head = atoms(g.value(r, u('body'))), atoms(g.value(r, u('head')))
    bound = set()
    for kind, pred, args in body:
        if kind == 'class' and pred not in declared_cls: problems.append(f'classe non dichiarata {short(pred)}')
        if kind == 'prop' and pred not in declared_props: problems.append(f'proprieta non dichiarata {short(pred)}')
        if kind in ('class', 'prop'):
            bound |= {a for a in args if isvar(a)}
    for kind, pred, args in body:
        if kind != 'builtin': continue
        name = short(pred); lo, hi = ARITY.get(name, (0, 99))
        if not lo <= len(args) <= hi: problems.append(f'{name} con {len(args)} argomenti (attesi {lo}{"" if lo==hi else "+"})')
        ins = args[1:] if name in BIND else args
        for a in ins:
            if isvar(a) and a not in bound: problems.append(f'{name}: variabile {vn(a)} non legata')
        if name in BIND and args and isvar(args[0]): bound.add(args[0])
    for kind, pred, args in head:
        if kind == 'prop' and pred not in declared_props: problems.append(f'testa: proprieta non dichiarata {short(pred)}')
        for a in args:
            if isvar(a) and a not in bound: problems.append(f'testa: variabile {vn(a)} non legata')
    allv = {vn(a) for _, _, args in body + head for a in args if isvar(a)}
    low = collections.defaultdict(set)
    for v in allv: low[v.lower()].add(v)
    for k, vs in low.items():
        if len(vs) > 1: problems.append('variabili che differiscono solo per maiuscole: ' + ', '.join(sorted(vs)))
    # a binding built-in (add, divide...) uses its arguments after the first;
    # a test built-in (lessThan...) uses all of them, the first included
    used = [a for k, pred, args in body if k == 'builtin'
            for a in (args[1:] if short(pred) in BIND else args) if isvar(a)]
    for kind, pred, args in body:
        if kind == 'builtin' and short(pred) in BIND and args and isvar(args[0]):
            out = args[0]
            if out not in used and all(out not in a for _, _, a in head):
                problems.append(f'{short(pred)}: risultato {vn(out)} calcolato e mai usato')
    if problems:
        total += len(problems)
        print(f'### {label}')
        for p in dict.fromkeys(problems): print('    -', p)
print(f'\nproblemi trovati: {total}')
