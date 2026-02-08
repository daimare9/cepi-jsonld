"""
Benchmark at scale: Repeat the 90 records to ~900 records, 
use batch=100 (proportional to 1000 at 10x), and measure real speedup.
Also test multiprocessing with larger batches where process overhead is amortized.
"""
import pandas as pd
from rdflib import Graph, URIRef, BNode, Literal, Namespace
from rdflib.namespace import RDF, XSD
from pyld import jsonld
import json
import time
import os
from concurrent.futures import ProcessPoolExecutor, as_completed

ceds = Namespace("http://ceds.ed.gov/terms#")
cepi = Namespace("http://cepi-dev.state.mi.us/")
rdf = RDF
rdfs_ns = Namespace("http://www.w3.org/2000/01/rdf-schema#")
sh = Namespace("http://www.w3.org/ns/shacl#")
xsd = XSD

with open("Person_context.json", "r") as f:
    CTX = json.load(f)

FRAME = {
    "@context": CTX["@context"],
    "@type": "Person",
    "@embed": "@always",
    "hasPersonName": {"@embed": "@always"},
    "hasPersonBirth": {"@embed": "@always"},
    "hasPersonSexGender": {"@embed": "@always"},
    "hasPersonIdentification": {"@embed": "@always"},
    "hasPersonDemographicRace": {"@embed": "@always"}
}


def process_single_row(row):
    g = Graph()
    g.bind("ceds", ceds)
    g.bind("cepi", cepi)
    g.bind("rdf", rdf)
    g.bind("rdfs", rdfs_ns)
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
    if pd.notna(row.get('MiddleName')) and row['MiddleName']:
        g.add((name_node, ceds.P000184, Literal(row['MiddleName'])))
    g.add((name_node, ceds.P000172, Literal(row['LastName'])))
    if pd.notna(row.get('GenerationCodeOrSuffix')) and row['GenerationCodeOrSuffix']:
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

    if pd.notna(row.get('RaceEthnicity')):
        for group in row['RaceEthnicity'].split('|'):
            race_node = BNode()
            g.add((person_uri, ceds.P600035, race_node))
            g.add((race_node, RDF.type, ceds.C200282))
            add_common_nodes(race_node)
            for r in group.split(','):
                g.add((race_node, ceds.P000282, Literal(f"RaceAndEthnicity_{r.replace(' ', '')}")))

    if pd.notna(row.get('PersonIdentifiers')):
        ids = row['PersonIdentifiers'].split('|')
        systems = row['IdentificationSystems'].split('|') if pd.notna(row.get('IdentificationSystems')) else ['PersonIdentificationSystem_SSN'] * len(ids)
        types = row['PersonIdentifierTypes'].split('|') if pd.notna(row.get('PersonIdentifierTypes')) else ['PersonIdentifierType_PersonIdentifier'] * len(ids)
        for id_val, sys_val, typ in zip(ids, systems, types):
            id_node = BNode()
            g.add((person_uri, ceds.P600049, id_node))
            g.add((id_node, RDF.type, ceds.C200291))
            add_common_nodes(id_node)
            g.add((id_node, ceds.P001572, Literal(str(int(float(id_val))), datatype=XSD.token)))
            g.add((id_node, ceds.P001571, Literal(sys_val)))
            g.add((id_node, ceds.P001573, Literal(typ)))

    expanded = json.loads(g.serialize(format="json-ld"))
    framed = jsonld.frame(expanded, FRAME)
    compacted = jsonld.compact(framed, CTX)
    compacted["@context"] = "https://cepi-dev.state.mi.us/ontology/context-person.json"
    return compacted


def process_batch(rows_dicts):
    """Process a list of row dicts. Each worker handles a full batch."""
    return [process_single_row(r) for r in rows_dicts]


if __name__ == "__main__":
    cpu_count = os.cpu_count()
    print(f"CPU cores available: {cpu_count}")

    # Build a larger dataset by repeating the 90 rows ~10x = 900 rows
    df_base = pd.read_csv("person_sample_data.csv")
    df = pd.concat([df_base] * 10, ignore_index=True)
    n = len(df)
    rows = [row.to_dict() for _, row in df.iterrows()]

    TARGET = 1_000_000
    print(f"Test records: {n}")
    print()

    # --- Sequential baseline ---
    print("=" * 70)
    print("  SEQUENTIAL BASELINE")
    print("=" * 70)
    # warmup
    process_single_row(rows[0])

    t0 = time.perf_counter()
    seq_results = [process_single_row(r) for r in rows]
    t_seq = time.perf_counter() - t0
    ms_seq = (t_seq / n) * 1000
    print(f"  {n} records in {t_seq:.3f}s  |  {ms_seq:.2f} ms/record")

    # --- Multiprocessing with varying workers and batch sizes ---
    configs = [
        (5, 100),
        (5, 200),
        (10, 100),
        (10, 50),
    ]
    # Also test with cpu_count
    if cpu_count and cpu_count not in [5, 10]:
        configs.append((cpu_count, 100))

    mp_results_table = []

    for workers, batch_size in configs:
        print()
        print("=" * 70)
        print(f"  MULTIPROCESSING: {workers} workers, batch_size={batch_size}")
        print("=" * 70)

        batches = [rows[i:i + batch_size] for i in range(0, len(rows), batch_size)]

        t0 = time.perf_counter()
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(process_batch, batch): idx for idx, batch in enumerate(batches)}
            ordered = [None] * len(batches)
            for future in as_completed(futures):
                idx = futures[future]
                ordered[idx] = future.result()
        all_results = []
        for br in ordered:
            all_results.extend(br)
        t_mp = time.perf_counter() - t0

        ms_mp = (t_mp / n) * 1000
        speedup = t_seq / t_mp
        mp_results_table.append((workers, batch_size, t_mp, ms_mp, speedup))
        print(f"  {n} records in {t_mp:.3f}s  |  {ms_mp:.2f} ms/record  |  Speedup: {speedup:.2f}x")

    # --- Summary & Extrapolation ---
    print()
    print("=" * 70)
    print(f"  SUMMARY & EXTRAPOLATION TO {TARGET:,} RECORDS")
    print("=" * 70)
    print()
    print(f"  {'Method':<35s}  {'ms/rec':>7s}  {'Speedup':>8s}  {'1M Est':>10s}  {'Hours':>6s}")
    print(f"  {'-'*35}  {'-'*7}  {'-'*8}  {'-'*10}  {'-'*6}")

    est_s = (ms_seq * TARGET) / 1000
    print(f"  {'Sequential':<35s}  {ms_seq:7.2f}  {'1.00x':>8s}  {est_s:>10,.0f}s  {est_s/3600:>6.2f}")

    best_speedup = 0
    best_label = ""
    for workers, batch_size, t_mp, ms_mp, speedup in mp_results_table:
        label = f"MP {workers}P batch={batch_size}"
        est_s = (ms_mp * TARGET) / 1000
        print(f"  {label:<35s}  {ms_mp:7.2f}  {speedup:7.2f}x  {est_s:>10,.0f}s  {est_s/3600:>6.2f}")
        if speedup > best_speedup:
            best_speedup = speedup
            best_label = label

    print()
    print(f"  Best config: {best_label}  ({best_speedup:.2f}x speedup)")
    print()

    # Project the user's desired config: 10 workers, batch=1000
    # Use measured best speedup as proxy
    proj_ms = ms_seq / best_speedup
    proj_s = (proj_ms * TARGET) / 1000
    proj_m = proj_s / 60
    proj_h = proj_m / 60
    print(f"  PROJECTED: 10 workers, batch=1000 at 1M records")
    print(f"  (Using best measured speedup of {best_speedup:.2f}x)")
    print(f"  => {proj_ms:.2f} ms/record")
    print(f"  => {proj_s:,.0f} seconds  |  {proj_m:,.1f} minutes  |  {proj_h:.2f} hours")
    print("=" * 70)
