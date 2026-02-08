"""
Profile Bottleneck Breakdown
============================
Measures time spent in each phase of the CSV-to-JSON-LD pipeline:
  1. Graph creation (rdflib triples)
  2. JSON-LD serialization (rdflib serialize)
  3. JSON parse (json.loads)
  4. Framing (pyld.jsonld.frame)
  5. Compaction (pyld.jsonld.compact)
"""
import pandas as pd
from rdflib import Graph, URIRef, BNode, Literal, Namespace
from rdflib.namespace import RDF, XSD
from pyld import jsonld
import json
import time
from statistics import mean, median, stdev

ceds = Namespace("http://ceds.ed.gov/terms#")
cepi = Namespace("http://cepi-dev.state.mi.us/")
rdf = RDF
rdfs = Namespace("http://www.w3.org/2000/01/rdf-schema#")
sh = Namespace("http://www.w3.org/ns/shacl#")
xsd = XSD

df = pd.read_csv("person_sample_data.csv")

with open("Person_context.json", "r") as f:
    ctx = json.load(f)

frame_template = {
    "@context": ctx["@context"],
    "@type": "Person",
    "@embed": "@always",
    "hasPersonName": {"@embed": "@always"},
    "hasPersonBirth": {"@embed": "@always"},
    "hasPersonSexGender": {"@embed": "@always"},
    "hasPersonIdentification": {"@embed": "@always"},
    "hasPersonDemographicRace": {"@embed": "@always"}
}

# Phase accumulators
t_graph = []
t_serialize = []
t_parse = []
t_frame = []
t_compact = []
t_total = []

for index, row in df.iterrows():
    t0 = time.perf_counter()

    # --- Phase 1: Graph Creation ---
    g = Graph()
    g.bind("ceds", ceds)
    g.bind("cepi", cepi)
    g.bind("rdf", rdf)
    g.bind("rdfs", rdfs)
    g.bind("sh", sh)
    g.bind("xsd", xsd)

    person_uri = URIRef(f"http://cepi-dev.state.mi.us/person/{int(row['PersonIdentifiers'].split('|')[0])}")
    g.add((person_uri, RDF.type, ceds.C200275))

    def add_common_nodes(parent_node):
        record_node = BNode()
        g.add((parent_node, ceds.P201001, record_node))
        g.add((record_node, RDF.type, ceds.C200411))
        g.add((record_node, ceds.P200999, URIRef("http://cepi-dev.state.mi.us/organization/3000000789")))
        g.add((record_node, ceds.P001917, Literal("1900-01-01T00:00:00.000", datatype=XSD.dateTime)))
        g.add((record_node, ceds.P001918, Literal("9999-12-31T00:00:00.000", datatype=XSD.dateTime)))
        data_node = URIRef("http://example.org/dataCollection/45678")
        g.add((parent_node, ceds.P201003, data_node))
        g.add((data_node, RDF.type, ceds.C200410))

    name_node = BNode()
    g.add((person_uri, ceds.P600336, name_node))
    g.add((name_node, RDF.type, ceds.C200377))
    add_common_nodes(name_node)
    g.add((name_node, ceds.P000115, Literal(row['FirstName'])))
    if pd.notna(row['MiddleName']) and row['MiddleName']:
        g.add((name_node, ceds.P000184, Literal(row['MiddleName'])))
    g.add((name_node, ceds.P000172, Literal(row['LastName'])))
    if pd.notna(row['GenerationCodeOrSuffix']) and row['GenerationCodeOrSuffix']:
        g.add((name_node, ceds.P000121, Literal(row['GenerationCodeOrSuffix'])))

    birth_node = BNode()
    g.add((person_uri, ceds.P600335, birth_node))
    g.add((birth_node, RDF.type, ceds.C200376))
    add_common_nodes(birth_node)
    g.add((birth_node, ceds.P000033, Literal(row['Birthdate'], datatype=XSD.date)))

    sex_node = BNode()
    g.add((person_uri, ceds.P600338, sex_node))
    g.add((sex_node, RDF.type, ceds.C200011))
    add_common_nodes(sex_node)
    sex_value = "Sex_Female" if row['Sex'] == "Female" else "Sex_Male"
    g.add((sex_node, ceds.P000011, Literal(sex_value)))

    if pd.notna(row['RaceEthnicity']):
        race_groups = row['RaceEthnicity'].split('|')
        for group in race_groups:
            race_node = BNode()
            g.add((person_uri, ceds.P600035, race_node))
            g.add((race_node, RDF.type, ceds.C200282))
            add_common_nodes(race_node)
            races = group.split(',')
            for r in races:
                race_value = f"RaceAndEthnicity_{r.replace(' ', '')}"
                g.add((race_node, ceds.P000282, Literal(race_value)))

    if pd.notna(row['PersonIdentifiers']):
        ids = row['PersonIdentifiers'].split('|')
        systems = row['IdentificationSystems'].split('|') if pd.notna(row['IdentificationSystems']) else ['PersonIdentificationSystem_SSN'] * len(ids)
        types = row['PersonIdentifierTypes'].split('|') if pd.notna(row['PersonIdentifierTypes']) else ['PersonIdentifierType_PersonIdentifier'] * len(ids)
        for id_val, sys_, typ in zip(ids, systems, types):
            id_node = BNode()
            g.add((person_uri, ceds.P600049, id_node))
            g.add((id_node, RDF.type, ceds.C200291))
            add_common_nodes(id_node)
            g.add((id_node, ceds.P001572, Literal(str(int(float(id_val))), datatype=XSD.token)))
            g.add((id_node, ceds.P001571, Literal(sys_)))
            g.add((id_node, ceds.P001573, Literal(typ)))

    t1 = time.perf_counter()

    # --- Phase 2: Serialize to JSON-LD string ---
    expanded_str = g.serialize(format="json-ld")
    t2 = time.perf_counter()

    # --- Phase 3: JSON parse ---
    expanded = json.loads(expanded_str)
    t3 = time.perf_counter()

    # --- Phase 4: Frame ---
    framed = jsonld.frame(expanded, frame_template)
    t4 = time.perf_counter()

    # --- Phase 5: Compact ---
    compacted = jsonld.compact(framed, ctx)
    t5 = time.perf_counter()

    t_graph.append((t1 - t0) * 1000)
    t_serialize.append((t2 - t1) * 1000)
    t_parse.append((t3 - t2) * 1000)
    t_frame.append((t4 - t3) * 1000)
    t_compact.append((t5 - t4) * 1000)
    t_total.append((t5 - t0) * 1000)

# --- Report ---
print("=" * 72)
print(f"  BOTTLENECK PROFILE  ({len(df)} records)")
print("=" * 72)

phases = [
    ("1. Graph creation (rdflib)", t_graph),
    ("2. Serialize to JSON-LD",    t_serialize),
    ("3. JSON parse",              t_parse),
    ("4. PyLD frame",              t_frame),
    ("5. PyLD compact",            t_compact),
    ("TOTAL",                      t_total),
]

total_mean = mean(t_total)
print(f"\n  {'Phase':<30} {'Mean ms':>10} {'Median':>10} {'% of Total':>12}")
print(f"  {'-'*30} {'-'*10} {'-'*10} {'-'*12}")

for name, data in phases:
    m = mean(data)
    md = median(data)
    pct = (m / total_mean * 100) if total_mean > 0 else 0
    print(f"  {name:<30} {m:10.3f} {md:10.3f} {pct:11.1f}%")

print(f"\n  Min/Max total: {min(t_total):.2f} / {max(t_total):.2f} ms")
print(f"  Std dev total: {stdev(t_total):.2f} ms" if len(t_total) > 1 else "")

# Show where the time goes as a bar chart
print(f"\n  VISUAL BREAKDOWN (mean per record):")
print(f"  {'─' * 50}")
for name, data in phases[:-1]:  # exclude TOTAL
    m = mean(data)
    pct = (m / total_mean * 100)
    bar_len = int(pct / 2)
    print(f"  {name:<30} {'█' * bar_len} {pct:.1f}%")

# Extrapolation
print(f"\n  1M RECORD PROJECTION (sequential):")
est_s = total_mean * 1_000_000 / 1000
print(f"  {est_s:,.0f} seconds  ({est_s/3600:,.1f} hours)")
print("=" * 72)
