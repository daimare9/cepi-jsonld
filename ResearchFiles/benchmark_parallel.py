"""
Benchmark: Sequential vs Parallel batch processing for CSV -> JSON-LD conversion.
Tests multithreading (ThreadPoolExecutor) and multiprocessing (ProcessPoolExecutor).
"""
import pandas as pd
from rdflib import Graph, URIRef, BNode, Literal, Namespace
from rdflib.namespace import RDF, XSD
from pyld import jsonld
import json
import time
from statistics import mean, median
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
import math

# --- Shared setup ---
ceds = Namespace("http://ceds.ed.gov/terms#")
cepi = Namespace("http://cepi-dev.state.mi.us/")
rdf = RDF
rdfs = Namespace("http://www.w3.org/2000/01/rdf-schema#")
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
    """Process one CSV row into a compacted JSON-LD dict."""
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

    # Name
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

    # Birth
    birth_node = BNode()
    g.add((person_uri, ceds.P600335, birth_node))
    g.add((birth_node, RDF.type, ceds.C200376))
    add_common_nodes(birth_node)
    g.add((birth_node, ceds.P000033, Literal(row['Birthdate'], datatype=XSD.date)))

    # Sex
    sex_node = BNode()
    g.add((person_uri, ceds.P600338, sex_node))
    g.add((sex_node, RDF.type, ceds.C200011))
    add_common_nodes(sex_node)
    sex_value = "Sex_Female" if row['Sex'] == "Female" else "Sex_Male"
    g.add((sex_node, ceds.P000011, Literal(sex_value)))

    # Race
    if pd.notna(row['RaceEthnicity']):
        race_groups = row['RaceEthnicity'].split('|')
        for group in race_groups:
            race_node = BNode()
            g.add((person_uri, ceds.P600035, race_node))
            g.add((race_node, RDF.type, ceds.C200282))
            add_common_nodes(race_node)
            for r in group.split(','):
                g.add((race_node, ceds.P000282, Literal(f"RaceAndEthnicity_{r.replace(' ', '')}")))

    # Identification
    if pd.notna(row['PersonIdentifiers']):
        ids = row['PersonIdentifiers'].split('|')
        systems = row['IdentificationSystems'].split('|') if pd.notna(row['IdentificationSystems']) else ['PersonIdentificationSystem_SSN'] * len(ids)
        types = row['PersonIdentifierTypes'].split('|') if pd.notna(row['PersonIdentifierTypes']) else ['PersonIdentifierType_PersonIdentifier'] * len(ids)
        for id_val, sys, typ in zip(ids, systems, types):
            id_node = BNode()
            g.add((person_uri, ceds.P600049, id_node))
            g.add((id_node, RDF.type, ceds.C200291))
            add_common_nodes(id_node)
            g.add((id_node, ceds.P001572, Literal(str(int(float(id_val))), datatype=XSD.token)))
            g.add((id_node, ceds.P001571, Literal(sys)))
            g.add((id_node, ceds.P001573, Literal(typ)))

    # Serialize, frame, compact
    expanded = json.loads(g.serialize(format="json-ld"))
    framed = jsonld.frame(expanded, FRAME)
    compacted = jsonld.compact(framed, CTX)
    compacted["@context"] = "https://cepi-dev.state.mi.us/ontology/context-person.json"
    return compacted


def process_batch(rows_list):
    """Process a list of row dicts (a batch) and return list of compacted JSON-LD."""
    return [process_single_row(row) for row in rows_list]


def run_sequential(df):
    """Sequential baseline - process all rows one by one."""
    results = []
    for _, row in df.iterrows():
        results.append(process_single_row(row))
    return results


def run_threaded(df, batch_size, max_workers):
    """Multithreaded - batches processed in parallel threads."""
    rows = [row for _, row in df.iterrows()]
    batches = [rows[i:i + batch_size] for i in range(0, len(rows), batch_size)]
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_batch, batch): idx for idx, batch in enumerate(batches)}
        batch_results = [None] * len(batches)
        for future in as_completed(futures):
            idx = futures[future]
            batch_results[idx] = future.result()
    for br in batch_results:
        results.extend(br)
    return results


def run_multiprocess(df, batch_size, max_workers):
    """Multiprocessing - batches processed in parallel processes (bypasses GIL)."""
    rows = [row.to_dict() for _, row in df.iterrows()]
    batches = [rows[i:i + batch_size] for i in range(0, len(rows), batch_size)]
    results = []
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_batch, batch): idx for idx, batch in enumerate(batches)}
        batch_results = [None] * len(batches)
        for future in as_completed(futures):
            idx = futures[future]
            batch_results[idx] = future.result()
    for br in batch_results:
        results.extend(br)
    return results


if __name__ == "__main__":
    df = pd.read_csv("person_sample_data.csv")
    n = len(df)
    TARGET = 1_000_000

    # Batch config matching user's request
    BATCH_SIZE = 10  # Scale down proportionally (1000/100 since we have 90 not 90000)
    MAX_WORKERS = 10

    print(f"Records: {n}")
    print(f"Batch size (scaled for {n} records): {BATCH_SIZE}")
    print(f"Parallel workers: {MAX_WORKERS}")
    print()

    # --- 1) Sequential baseline ---
    print("=" * 65)
    print("  [1/3] SEQUENTIAL (baseline)")
    print("=" * 65)
    # Warmup
    process_single_row(next(df.iterrows())[1])

    t0 = time.perf_counter()
    seq_results = run_sequential(df)
    t_seq = time.perf_counter() - t0
    ms_per_rec_seq = (t_seq / n) * 1000
    print(f"  Time: {t_seq:.3f} s  |  {ms_per_rec_seq:.2f} ms/record")

    # --- 2) Multithreaded ---
    print()
    print("=" * 65)
    print(f"  [2/3] MULTITHREADED  ({MAX_WORKERS} threads, batch={BATCH_SIZE})")
    print("=" * 65)
    t0 = time.perf_counter()
    thr_results = run_threaded(df, BATCH_SIZE, MAX_WORKERS)
    t_thr = time.perf_counter() - t0
    ms_per_rec_thr = (t_thr / n) * 1000
    thread_speedup = t_seq / t_thr
    print(f"  Time: {t_thr:.3f} s  |  {ms_per_rec_thr:.2f} ms/record  |  Speedup: {thread_speedup:.2f}x")

    # --- 3) Multiprocessing ---
    print()
    print("=" * 65)
    print(f"  [3/3] MULTIPROCESSING  ({MAX_WORKERS} processes, batch={BATCH_SIZE})")
    print("=" * 65)
    t0 = time.perf_counter()
    mp_results = run_multiprocess(df, BATCH_SIZE, MAX_WORKERS)
    t_mp = time.perf_counter() - t0
    ms_per_rec_mp = (t_mp / n) * 1000
    mp_speedup = t_seq / t_mp
    print(f"  Time: {t_mp:.3f} s  |  {ms_per_rec_mp:.2f} ms/record  |  Speedup: {mp_speedup:.2f}x")

    # --- Extrapolation ---
    print()
    print("=" * 65)
    print(f"  EXTRAPOLATION TO {TARGET:,} RECORDS")
    print("=" * 65)

    for label, ms_per, speedup in [
        ("Sequential", ms_per_rec_seq, 1.0),
        (f"Threaded ({MAX_WORKERS}T)", ms_per_rec_thr, thread_speedup),
        (f"Multiprocess ({MAX_WORKERS}P)", ms_per_rec_mp, mp_speedup),
    ]:
        est_s = (ms_per * TARGET) / 1000
        est_m = est_s / 60
        est_h = est_m / 60
        print(f"  {label:<25s}  {ms_per:6.2f} ms/rec  => {est_s:>10,.0f}s  |  {est_m:>7,.1f}m  |  {est_h:>5.2f}h")

    # Projected with real batch=1000 and 10 workers
    print()
    print("  NOTE: With batch=1000 & 10 workers at scale, overhead per")
    print("  batch is amortized. Adjusted estimates (using measured speedup):")
    print()
    # At scale, threading overhead is lower per record, so use measured speedup
    for label, speedup in [
        (f"Threaded  (10T, batch=1000)", thread_speedup),
        (f"Multiproc (10P, batch=1000)", mp_speedup),
    ]:
        adj_ms = ms_per_rec_seq / speedup
        est_s = (adj_ms * TARGET) / 1000
        est_m = est_s / 60
        est_h = est_m / 60
        print(f"  {label:<30s}  {adj_ms:6.2f} ms/rec  => {est_s:>10,.0f}s  |  {est_m:>7,.1f}m  |  {est_h:>5.2f}h")

    print("=" * 65)
