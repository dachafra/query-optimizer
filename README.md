# Answering SPARQL queries over big RDBs
Instead of virtualize (translate the query), this script helps materializers to only generate 
the needed RDF for a given query.

## How it works
Given a complete mapping that describes the relationship between ontology and data sources and a SPARQL query, 
it produces a new mapping with the rules required for answer that query. 

```
python3 -m pip install rdflib
```

```
python3 optimize.py -m complete-mapping.r2rml.ttl -q myquery.rq -o output-mapping.r2rml.ttl
```

