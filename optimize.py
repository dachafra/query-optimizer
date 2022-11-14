import argparse

import rdflib.term
from rdflib import Graph
from rdflib.plugins.sparql import *


def write_results(optimized_mapping):
    output_file = open(args.output_path, "w")
    output_file.write(optimized_mapping)
    output_file.close()


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


def get_predicates_from_sparql():
    predicates = []
    prefixes = get_prefixes_from_query()
    for triples in query[1]['where']['part']:
        for path in triples['triples']:
            if type(path[1]) == rdflib.term.Variable:
                raise Exception("Query has a variable")
            else:
                predicate = path[1]['part'][0]['part'][0]['part']
                if "prefix" in predicate:
                    predicates.append(prefixes[predicate['prefix']] + predicate['localname'])
                else:
                    predicates.append(predicate.toPython())

    return predicates


if __name__ == "__main__":
    args = define_args().parse_args()
    query, mapping = parse_arguments()
    predicates = get_predicates_from_sparql()
