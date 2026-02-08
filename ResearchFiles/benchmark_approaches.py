"""
Direct JSON-LD Construction (No rdflib, No PyLD)
=================================================
Constructs compacted JSON-LD dictionaries directly from CSV data,
using known context mappings. This bypasses the entire RDF→serialize→frame→compact
pipeline since the mapping from CSV columns to JSON-LD terms is deterministic.

Also benchmarks: rdflib auto_compact approach as a middle ground.
"""
import pandas as pd
import json
import time
from statistics import mean, median, stdev

# ═══════════════════════════════════════════════════════════════════════
# APPROACH 1: Direct Dict Construction (zero-dependency beyond pandas)
# ═══════════════════════════════════════════════════════════════════════

def make_record_status():
    """Reusable record status sub-object."""
    return {
        "@type": "RecordStatus",
        "RecordStartDateTime": {
            "@type": "xsd:dateTime",
            "@value": "1900-01-01T00:00:00"
        },
        "RecordEndDateTime": {
            "@type": "xsd:dateTime",
            "@value": "9999-12-31T00:00:00"
        },
        "CommittedByOrganization": {
            "@id": "cepi:organization/3000000789"
        }
    }

def make_data_collection():
    """Reusable data collection sub-object."""
    return {
        "@id": "http://example.org/dataCollection/45678",
        "@type": "DataCollection"
    }

def build_person_direct(row):
    """Build a compacted JSON-LD person dict directly from a CSV row."""
    person_id = str(int(float(row['PersonIdentifiers'].split('|')[0])))

    person = {
        "@context": "https://cepi-dev.state.mi.us/ontology/context-person.json",
        "@id": f"cepi:person/{person_id}",
        "@type": "Person",
    }

    # --- PersonDemographicRace ---
    if pd.notna(row['RaceEthnicity']):
        race_groups = row['RaceEthnicity'].split('|')
        race_nodes = []
        for group in race_groups:
            races = group.split(',')
            race_values = [f"RaceAndEthnicity_{r.strip().replace(' ', '')}" for r in races]
            node = {
                "@type": "PersonDemographicRace",
                "hasRaceAndEthnicity": race_values if len(race_values) > 1 else race_values[0],
                "hasRecordStatus": make_record_status(),
                "hasDataCollection": make_data_collection()
            }
            race_nodes.append(node)
        person["hasPersonDemographicRace"] = race_nodes if len(race_nodes) > 1 else race_nodes[0]

    # --- PersonIdentification ---
    if pd.notna(row['PersonIdentifiers']):
        ids = row['PersonIdentifiers'].split('|')
        systems = row['IdentificationSystems'].split('|') if pd.notna(row.get('IdentificationSystems', None)) else ['PersonIdentificationSystem_SSN'] * len(ids)
        types = row['PersonIdentifierTypes'].split('|') if pd.notna(row.get('PersonIdentifierTypes', None)) else ['PersonIdentifierType_PersonIdentifier'] * len(ids)

        id_nodes = []
        for id_val, sys_, typ in zip(ids, systems, types):
            node = {
                "@type": "PersonIdentification",
                "hasPersonIdentificationSystem": sys_,
                "PersonIdentifier": {
                    "@type": "xsd:token",
                    "@value": str(int(float(id_val)))
                },
                "hasPersonIdentifierType": typ,
                "hasRecordStatus": make_record_status(),
                "hasDataCollection": make_data_collection()
            }
            id_nodes.append(node)
        person["hasPersonIdentification"] = id_nodes if len(id_nodes) > 1 else id_nodes[0]

    # --- PersonBirth ---
    birth = {
        "@type": "PersonBirth",
        "Birthdate": {
            "@type": "xsd:date",
            "@value": str(row['Birthdate'])
        },
        "hasRecordStatus": make_record_status(),
        "hasDataCollection": make_data_collection()
    }
    person["hasPersonBirth"] = birth

    # --- PersonName ---
    name = {
        "@type": "PersonName",
        "FirstName": str(row['FirstName']),
        "LastOrSurname": str(row['LastName']),
        "hasRecordStatus": make_record_status(),
        "hasDataCollection": make_data_collection()
    }
    if pd.notna(row['MiddleName']) and row['MiddleName']:
        name["MiddleName"] = str(row['MiddleName'])
    if pd.notna(row['GenerationCodeOrSuffix']) and row['GenerationCodeOrSuffix']:
        name["GenerationCodeOrSuffix"] = str(row['GenerationCodeOrSuffix'])
    person["hasPersonName"] = name

    # --- PersonSexGender ---
    sex_value = "Sex_Female" if row['Sex'] == "Female" else "Sex_Male"
    sex = {
        "@type": "PersonSexGender",
        "hasSex": sex_value,
        "hasRecordStatus": make_record_status(),
        "hasDataCollection": make_data_collection()
    }
    person["hasPersonSexGender"] = sex

    return person

# ═══════════════════════════════════════════════════════════════════════
# APPROACH 2: rdflib with auto_compact (skip PyLD)
# ═══════════════════════════════════════════════════════════════════════

def build_person_rdflib_autocompact(row, ctx_data):
    """Use rdflib's built-in auto_compact serialization with context."""
    from rdflib import Graph, URIRef, BNode, Literal, Namespace
    from rdflib.namespace import RDF, XSD

    ceds = Namespace("http://ceds.ed.gov/terms#")
    cepi_ns = Namespace("http://cepi-dev.state.mi.us/")

    g = Graph()
    g.bind("ceds", ceds)
    g.bind("cepi", cepi_ns)

    person_uri = URIRef(f"http://cepi-dev.state.mi.us/person/{int(row['PersonIdentifiers'].split('|')[0])}")
    g.add((person_uri, RDF.type, ceds.C200275))

    def add_common(parent):
        rec = BNode()
        g.add((parent, ceds.P201001, rec))
        g.add((rec, RDF.type, ceds.C200411))
        g.add((rec, ceds.P200999, URIRef("http://cepi-dev.state.mi.us/organization/3000000789")))
        g.add((rec, ceds.P001917, Literal("1900-01-01T00:00:00.000", datatype=XSD.dateTime)))
        g.add((rec, ceds.P001918, Literal("9999-12-31T00:00:00.000", datatype=XSD.dateTime)))
        dc = URIRef("http://example.org/dataCollection/45678")
        g.add((parent, ceds.P201003, dc))
        g.add((dc, RDF.type, ceds.C200410))

    # Name
    nn = BNode()
    g.add((person_uri, ceds.P600336, nn))
    g.add((nn, RDF.type, ceds.C200377))
    add_common(nn)
    g.add((nn, ceds.P000115, Literal(row['FirstName'])))
    if pd.notna(row['MiddleName']) and row['MiddleName']:
        g.add((nn, ceds.P000184, Literal(row['MiddleName'])))
    g.add((nn, ceds.P000172, Literal(row['LastName'])))
    if pd.notna(row['GenerationCodeOrSuffix']) and row['GenerationCodeOrSuffix']:
        g.add((nn, ceds.P000121, Literal(row['GenerationCodeOrSuffix'])))

    # Birth
    bn = BNode()
    g.add((person_uri, ceds.P600335, bn))
    g.add((bn, RDF.type, ceds.C200376))
    add_common(bn)
    g.add((bn, ceds.P000033, Literal(row['Birthdate'], datatype=XSD.date)))

    # Sex
    sn = BNode()
    g.add((person_uri, ceds.P600338, sn))
    g.add((sn, RDF.type, ceds.C200011))
    add_common(sn)
    sex_value = "Sex_Female" if row['Sex'] == "Female" else "Sex_Male"
    g.add((sn, ceds.P000011, Literal(sex_value)))

    # Race
    if pd.notna(row['RaceEthnicity']):
        for group in row['RaceEthnicity'].split('|'):
            rn = BNode()
            g.add((person_uri, ceds.P600035, rn))
            g.add((rn, RDF.type, ceds.C200282))
            add_common(rn)
            for r in group.split(','):
                g.add((rn, ceds.P000282, Literal(f"RaceAndEthnicity_{r.strip().replace(' ', '')}")))

    # Identification
    if pd.notna(row['PersonIdentifiers']):
        id_list = row['PersonIdentifiers'].split('|')
        sys_list = row['IdentificationSystems'].split('|') if pd.notna(row.get('IdentificationSystems', None)) else ['PersonIdentificationSystem_SSN'] * len(id_list)
        typ_list = row['PersonIdentifierTypes'].split('|') if pd.notna(row.get('PersonIdentifierTypes', None)) else ['PersonIdentifierType_PersonIdentifier'] * len(id_list)
        for iv, sy, ty in zip(id_list, sys_list, typ_list):
            idn = BNode()
            g.add((person_uri, ceds.P600049, idn))
            g.add((idn, RDF.type, ceds.C200291))
            add_common(idn)
            g.add((idn, ceds.P001572, Literal(str(int(float(iv))), datatype=XSD.token)))
            g.add((idn, ceds.P001571, Literal(sy)))
            g.add((idn, ceds.P001573, Literal(ty)))

    # Serialize with auto_compact directly
    result_str = g.serialize(format="json-ld", context=ctx_data["@context"], auto_compact=True)
    return json.loads(result_str)


# ═══════════════════════════════════════════════════════════════════════
# APPROACH 3: Original pipeline (rdflib → serialize → frame → compact)
# ═══════════════════════════════════════════════════════════════════════

def build_person_original(row, ctx, frame_template):
    """Original rdflib + PyLD pipeline."""
    from rdflib import Graph, URIRef, BNode, Literal, Namespace
    from rdflib.namespace import RDF, XSD
    from pyld import jsonld

    ceds = Namespace("http://ceds.ed.gov/terms#")
    cepi_ns = Namespace("http://cepi-dev.state.mi.us/")

    g = Graph()
    g.bind("ceds", ceds)
    g.bind("cepi", cepi_ns)
    g.bind("rdf", RDF)
    g.bind("rdfs", Namespace("http://www.w3.org/2000/01/rdf-schema#"))
    g.bind("sh", Namespace("http://www.w3.org/ns/shacl#"))
    g.bind("xsd", XSD)

    person_uri = URIRef(f"http://cepi-dev.state.mi.us/person/{int(row['PersonIdentifiers'].split('|')[0])}")
    g.add((person_uri, RDF.type, ceds.C200275))

    def add_common(parent):
        rec = BNode()
        g.add((parent, ceds.P201001, rec))
        g.add((rec, RDF.type, ceds.C200411))
        g.add((rec, ceds.P200999, URIRef("http://cepi-dev.state.mi.us/organization/3000000789")))
        g.add((rec, ceds.P001917, Literal("1900-01-01T00:00:00.000", datatype=XSD.dateTime)))
        g.add((rec, ceds.P001918, Literal("9999-12-31T00:00:00.000", datatype=XSD.dateTime)))
        dc = URIRef("http://example.org/dataCollection/45678")
        g.add((parent, ceds.P201003, dc))
        g.add((dc, RDF.type, ceds.C200410))

    nn = BNode()
    g.add((person_uri, ceds.P600336, nn))
    g.add((nn, RDF.type, ceds.C200377))
    add_common(nn)
    g.add((nn, ceds.P000115, Literal(row['FirstName'])))
    if pd.notna(row['MiddleName']) and row['MiddleName']:
        g.add((nn, ceds.P000184, Literal(row['MiddleName'])))
    g.add((nn, ceds.P000172, Literal(row['LastName'])))
    if pd.notna(row['GenerationCodeOrSuffix']) and row['GenerationCodeOrSuffix']:
        g.add((nn, ceds.P000121, Literal(row['GenerationCodeOrSuffix'])))

    bn = BNode()
    g.add((person_uri, ceds.P600335, bn))
    g.add((bn, RDF.type, ceds.C200376))
    add_common(bn)
    g.add((bn, ceds.P000033, Literal(row['Birthdate'], datatype=XSD.date)))

    sn = BNode()
    g.add((person_uri, ceds.P600338, sn))
    g.add((sn, RDF.type, ceds.C200011))
    add_common(sn)
    sex_value = "Sex_Female" if row['Sex'] == "Female" else "Sex_Male"
    g.add((sn, ceds.P000011, Literal(sex_value)))

    if pd.notna(row['RaceEthnicity']):
        for group in row['RaceEthnicity'].split('|'):
            rn = BNode()
            g.add((person_uri, ceds.P600035, rn))
            g.add((rn, RDF.type, ceds.C200282))
            add_common(rn)
            for r in group.split(','):
                g.add((rn, ceds.P000282, Literal(f"RaceAndEthnicity_{r.strip().replace(' ', '')}")))

    if pd.notna(row['PersonIdentifiers']):
        id_list = row['PersonIdentifiers'].split('|')
        sys_list = row['IdentificationSystems'].split('|') if pd.notna(row.get('IdentificationSystems', None)) else ['PersonIdentificationSystem_SSN'] * len(id_list)
        typ_list = row['PersonIdentifierTypes'].split('|') if pd.notna(row.get('PersonIdentifierTypes', None)) else ['PersonIdentifierType_PersonIdentifier'] * len(id_list)
        for iv, sy, ty in zip(id_list, sys_list, typ_list):
            idn = BNode()
            g.add((person_uri, ceds.P600049, idn))
            g.add((idn, RDF.type, ceds.C200291))
            add_common(idn)
            g.add((idn, ceds.P001572, Literal(str(int(float(iv))), datatype=XSD.token)))
            g.add((idn, ceds.P001571, Literal(sy)))
            g.add((idn, ceds.P001573, Literal(ty)))

    expanded_str = g.serialize(format="json-ld")
    expanded = json.loads(expanded_str)
    framed = jsonld.frame(expanded, frame_template)
    compacted = jsonld.compact(framed, ctx)
    compacted["@context"] = "https://cepi-dev.state.mi.us/ontology/context-person.json"
    return compacted


# ═══════════════════════════════════════════════════════════════════════
# BENCHMARK RUNNER
# ═══════════════════════════════════════════════════════════════════════

def benchmark(name, func, rows, n_runs=1, **kwargs):
    """Time a function over all rows, return per-record timings."""
    timings = []
    # Warmup
    func(rows[0], **kwargs)

    for _ in range(n_runs):
        for row_tuple in rows:
            t0 = time.perf_counter()
            func(row_tuple, **kwargs)
            t1 = time.perf_counter()
            timings.append((t1 - t0) * 1000)
    return timings


if __name__ == "__main__":
    df = pd.read_csv("person_sample_data.csv")
    rows = [row for _, row in df.iterrows()]

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

    N_RUNS = 3  # repeat dataset for stable measurements

    print("=" * 72)
    print("  MULTI-APPROACH BENCHMARK")
    print("=" * 72)
    print(f"  Records: {len(rows)}  x  {N_RUNS} runs = {len(rows)*N_RUNS} iterations each\n")

    # --- Approach 1: Direct Dict ---
    print("  [1/3] Direct Dict Construction...")
    t1 = benchmark("Direct Dict", build_person_direct, rows, n_runs=N_RUNS)

    # --- Approach 2: rdflib auto_compact ---
    print("  [2/3] rdflib + auto_compact...")
    t2 = benchmark("rdflib auto_compact", build_person_rdflib_autocompact, rows, n_runs=N_RUNS, ctx_data=ctx)

    # --- Approach 3: Original (rdflib + PyLD) ---
    print("  [3/3] Original (rdflib + PyLD frame + compact)...")
    t3 = benchmark("Original", build_person_original, rows, n_runs=N_RUNS, ctx=ctx, frame_template=frame_template)

    # --- Results ---
    results = [
        ("1. Direct Dict (no rdflib/PyLD)", t1),
        ("2. rdflib + auto_compact",         t2),
        ("3. Original (rdflib + PyLD)",       t3),
    ]

    print(f"\n{'=' * 72}")
    print(f"  {'Approach':<38} {'Mean ms':>8} {'Median':>8} {'Speedup':>8} {'1M est':>10}")
    print(f"  {'-'*38} {'-'*8} {'-'*8} {'-'*8} {'-'*10}")

    baseline_mean = mean(t3)
    for name, timings in results:
        m = mean(timings)
        md = median(timings)
        speedup = baseline_mean / m if m > 0 else float('inf')
        est_hours = (m * 1_000_000 / 1000) / 3600
        print(f"  {name:<38} {m:8.3f} {md:8.3f} {speedup:7.1f}x {est_hours:8.2f} hr")

    print(f"{'=' * 72}")

    # --- Verify output equivalence ---
    print("\n  OUTPUT VERIFICATION:")
    d1 = build_person_direct(rows[0])
    d3 = build_person_original(rows[0], ctx=ctx, frame_template=frame_template)

    # Compare key fields
    checks = [
        ("@type",         d1.get("@type") == d3.get("@type")),
        ("@id",           d1.get("@id") == d3.get("@id")),
        ("Name.First",    d1["hasPersonName"]["FirstName"] == d3["hasPersonName"]["FirstName"]),
        ("Name.Last",     d1["hasPersonName"]["LastOrSurname"] == d3["hasPersonName"]["LastOrSurname"]),
        ("Birth.date",    d1["hasPersonBirth"]["Birthdate"]["@value"] == d3["hasPersonBirth"]["Birthdate"]["@value"]),
        ("Sex",           d1["hasPersonSexGender"]["hasSex"] == d3["hasPersonSexGender"]["hasSex"]),
    ]
    for label, ok in checks:
        status = "PASS" if ok else "FAIL"
        print(f"    [{status}] {label}")
    
    # Save direct-construction output for manual comparison
    all_direct = [build_person_direct(r) for r in rows]
    with open("person_direct.json", "w") as f:
        json.dump(all_direct, f, indent=2)
    print(f"\n  Direct output saved to person_direct.json for manual comparison.")
    print(f"{'=' * 72}")
