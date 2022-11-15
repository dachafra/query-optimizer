import argparse

import rdflib.term
from rdflib import Graph, URIRef, RDF
from rdflib.plugins.sparql import *


def write_results():
    optimized_mapping.serialize(args.output_path, format="turtle")


def parse_arguments():
    if args.query_path and args.mapping_path:
        with open(args.query_path) as f:
            query = parser.parseQuery(f)
        mapping = Graph()
        mapping.parse(args.mapping_path, format="turtle")
    else:
        sys.tracebacklimit = 0
        raise Exception("No correct arguments, run python3 optimize.py -h to see the help)")

    return query, mapping


def define_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-q", "--query_path", required=True, help="Input SPARQL query path")
    parser.add_argument("-m", "--mapping_path", required=True, help="Input mapping path")
    parser.add_argument("-o", "--output_path", required=True, help="Output mapping path")
    return parser


def get_prefixes_from_query():
    prefixes = {}
    for prefix in query[0]:
        prefixes[prefix['prefix']] = prefix['iri'].toPython()
    return prefixes


def get_subjects_from_query():
    subject = {}
    for triples in query[1]['where']['part']:
        for path in triples['triples']:
            if type(path[0]) is rdflib.term.Variable:
                subject[path[0]] = []
    return subject


def get_resources_from_sparql():
    resources = get_subjects_from_query()
    prefixes = get_prefixes_from_query()
    for triples in query[1]['where']['part']:
        for path in triples['triples']:
            if type(path[1]) == rdflib.term.Variable:
                raise Exception("Query has a variable")
            else:
                predicate = path[1]['part'][0]['part'][0]['part']
                if "prefix" in predicate:
                    predicate = URIRef(prefixes[predicate['prefix']] + predicate['localname'])

                if predicate == RDF.type:
                    if "prefix" in path[2]:
                        resources[path[0]].append({
                            "predicate": predicate, "type": URIRef(prefixes[path[2]['prefix']] + path[2]['localname'])})
                    else:
                        resources[path[0]].append({"predicate": predicate, "type": path[2]})
                else:
                    resources[path[0]].append({"predicate": predicate})

    return resources

def get_predicates_classes_for_tm(triple):
    query_predicates = f'SELECT DISTINCT ?predicate WHERE {{ ' \
                       f'<{triple}> rr:predicateObjectMap ?pom . ' \
                       f'{{?pom rr:predicate ?predicate}}' \
                       f'UNION' \
                       f'{{?pom rr:predicateMap ?predicateMap . ?predicateMap ?type ?predicate}}' \
                       f'FILTER (?predicate != rr:PredicateMap) }} '
    query_classes = f'SELECT DISTINCT ?class WHERE {{ ' \
                    f'<{triple}> rr:predicateObjectMap ?pom . ' \
                    f'{{?pom rr:predicate rdf:type. ?pom rr:object ?class}}' \
                    f'UNION' \
                    f'{{?pom rr:predicateMap ?predicateMap . ?predicateMap rr:constant rdf:type . ' \
                    f'?pom rr:objectMap ?objectMap . ?objectMap rr:constant ?class}}' \
                    f'UNION' \
                    f'{{<{triple}> rr:subjectMap ?subjectMap . ?subjectMap rr:class ?class }} }}'

    predicates = [tm[rdflib.Variable('predicate')] for tm in mapping.query(query_predicates).bindings]
    classes = [tm[rdflib.Variable('class')] for tm in mapping.query(query_classes).bindings]

    return predicates, classes

def add_source_subject_from_tm(triples_map, g, remove_class=False):
    query = f'CONSTRUCT WHERE {{ ' \
           f'<{triples_map}> rr:logicalTable ?source . ' \
           f'?source ?source_predicates ?source_objects .'\
           f'<{triples_map}> rr:subjectMap ?subjectMap . ' \
           f'?subjectMap ?subject_predicates ?subject_objects }} '
    results = mapping.query(query)
    for s, p, o in results:
        if not remove_class or p != URIRef('http://www.w3.org/ns/r2rml#class'):
            g.add((s, p, o))

def create_object_query(triples_map, predicate, object_type):
    return f'CONSTRUCT WHERE {{ ' \
            f'<{triples_map}> rr:predicateObjectMap ?pom . ' \
            f'?pom rr:predicateMap ?predicateMap . ?predicateMap rr:constant <{predicate}> . ' \
            f'?pom rr:objectMap ?objectMap . ' \
            f'?objectMap {object_type} ?object_value . }}'

def add_refobject_query(triples_map, predicate, g):
    query = f'CONSTRUCT WHERE {{ ' \
            f'<{triples_map}> rr:predicateObjectMap ?pom . ' \
            f'?pom rr:predicateMap ?predicateMap . ?predicateMap rr:constant <{predicate}> . ' \
            f'?pom rr:objectMap ?objectMap . ' \
            f'?objectMap rr:parentTriplesMap ?parent_triples_map .' \
            f'?objectMap  rr:joinCondition ?join_condition .' \
            f'?join_condition ?predicates_join ?values_join  }}'
    results = mapping.query(query)
    for s, p, o in results:
        if p == URIRef('http://www.w3.org/ns/r2rml#parentTriplesMap'):
            add_source_subject_from_tm(o, g, True)
            g.add((triples_map, RDF.type, URIRef('http://www.w3.org/ns/r2rml#TriplesMap')))
        g.add((s, p, o))

def add_object_features(object_id, predicate, g):
    query = f'CONSTRUCT WHERE {{ <{object_id}> {predicate} ?value. }}'
    results = mapping.query(query)
    for s, p, o in results:
        g.add((s, p, o))

def add_predicate_object_map(triples_map, predicate, g):
    query = f'CONSTRUCT WHERE {{ ' \
            f'<{triples_map}> rr:predicateObjectMap ?pom . ' \
            f'?pom rr:predicate <{predicate}>. ?pom rr:object ?objects}}'
    results = mapping.query(query)
    options = ['rr:column', 'rr:constant', 'rr:template']
    index = 0
    while len(results) == 0 and index < 2:
        results = mapping.query(create_object_query(triples_map, predicate, options[index]))
        index = index + 1

    for s, p, o in results:
        if p == URIRef('http://www.w3.org/ns/r2rml#objectMap') or p == URIRef('http://www.w3.org/ns/r2rml#object'):
            add_object_features(o, 'rr:termType', g)
            add_object_features(o, 'rr:datatype', g)
        g.add((s, p, o))

    if len(results) == 0 and predicate != URIRef(RDF.type):
        add_refobject_query(triples_map, predicate, g)
def generate_optimized_mapping():
    mapping.bind('rr', rdflib.term.URIRef('http://www.w3.org/ns/r2rml#'))
    query_tm = f'SELECT ?triplesMap WHERE {{ ?triplesMap rdf:type rr:TriplesMap . }} '
    triples_map = [tm[rdflib.Variable('triplesMap')] for tm in mapping.query(query_tm).bindings]
    optimized_mapping = Graph()
    optimized_mapping.bind('rr', rdflib.term.URIRef('http://www.w3.org/ns/r2rml#'))
    selected_triples_map = {}
    for triple in triples_map:
        predicates, classes = get_predicates_classes_for_tm(triple)
        query_keys = resources.keys()
        for key in query_keys:
            tm_for_query = True
            for resource in resources[key]:
                if resource['predicate'] != RDF.type:
                    if resource['predicate'] not in predicates:
                        tm_for_query = False
                else:
                    if resource['type'] not in classes:
                        tm_for_query = False
            if tm_for_query:
                selected_triples_map[triple] = resources[key]

    for triples_map in selected_triples_map.keys():
        g = Graph()
        optimized_mapping.add((triples_map, RDF.type, URIRef('http://www.w3.org/ns/r2rml#TriplesMap')))
        add_source_subject_from_tm(triples_map, g)
        remove_class = True
        for resource in selected_triples_map[triples_map]:
            add_predicate_object_map(triples_map, resource['predicate'], g)
            if 'type' in resource.keys():
                remove_class = False
        if remove_class:
            g.remove((None, URIRef('http://www.w3.org/ns/r2rml#class'), None))
        optimized_mapping = optimized_mapping + g

    return optimized_mapping

if __name__ == "__main__":
    args = define_args().parse_args()
    query, mapping = parse_arguments()
    resources = get_resources_from_sparql()
    optimized_mapping = generate_optimized_mapping()
    write_results()
