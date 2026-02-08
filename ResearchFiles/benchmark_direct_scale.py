"""
Final Benchmark: Direct Dict + Multiprocessing at scale
========================================================
Tests the direct-construction approach at 10K+ records with
both sequential and parallel execution.
"""
import pandas as pd
import json
import time
from statistics import mean, median, stdev
from concurrent.futures import ProcessPoolExecutor
import multiprocessing

def make_record_status():
    return {
        "@type": "RecordStatus",
        "RecordStartDateTime": {"@type": "xsd:dateTime", "@value": "1900-01-01T00:00:00"},
        "RecordEndDateTime": {"@type": "xsd:dateTime", "@value": "9999-12-31T00:00:00"},
        "CommittedByOrganization": {"@id": "cepi:organization/3000000789"}
    }

def make_data_collection():
    return {"@id": "http://example.org/dataCollection/45678", "@type": "DataCollection"}

def build_person_direct(row_dict):
    """Build a compacted JSON-LD person dict from a plain dict (for pickling)."""
    person_id = str(int(float(row_dict['PersonIdentifiers'].split('|')[0])))

    person = {
        "@context": "https://cepi-dev.state.mi.us/ontology/context-person.json",
        "@id": f"cepi:person/{person_id}",
        "@type": "Person",
    }

    if row_dict.get('RaceEthnicity'):
        race_groups = row_dict['RaceEthnicity'].split('|')
        race_nodes = []
        for group in race_groups:
            races = group.split(',')
            vals = [f"RaceAndEthnicity_{r.strip().replace(' ', '')}" for r in races]
            race_nodes.append({
                "@type": "PersonDemographicRace",
                "hasRaceAndEthnicity": vals if len(vals) > 1 else vals[0],
                "hasRecordStatus": make_record_status(),
                "hasDataCollection": make_data_collection()
            })
        person["hasPersonDemographicRace"] = race_nodes if len(race_nodes) > 1 else race_nodes[0]

    if row_dict.get('PersonIdentifiers'):
        ids = row_dict['PersonIdentifiers'].split('|')
        systems = row_dict.get('IdentificationSystems', '').split('|') if row_dict.get('IdentificationSystems') else ['PersonIdentificationSystem_SSN'] * len(ids)
        types = row_dict.get('PersonIdentifierTypes', '').split('|') if row_dict.get('PersonIdentifierTypes') else ['PersonIdentifierType_PersonIdentifier'] * len(ids)
        id_nodes = []
        for iv, sy, ty in zip(ids, systems, types):
            id_nodes.append({
                "@type": "PersonIdentification",
                "hasPersonIdentificationSystem": sy,
                "PersonIdentifier": {"@type": "xsd:token", "@value": str(int(float(iv)))},
                "hasPersonIdentifierType": ty,
                "hasRecordStatus": make_record_status(),
                "hasDataCollection": make_data_collection()
            })
        person["hasPersonIdentification"] = id_nodes if len(id_nodes) > 1 else id_nodes[0]

    person["hasPersonBirth"] = {
        "@type": "PersonBirth",
        "Birthdate": {"@type": "xsd:date", "@value": str(row_dict['Birthdate'])},
        "hasRecordStatus": make_record_status(),
        "hasDataCollection": make_data_collection()
    }

    name = {
        "@type": "PersonName",
        "FirstName": str(row_dict['FirstName']),
        "LastOrSurname": str(row_dict['LastName']),
        "hasRecordStatus": make_record_status(),
        "hasDataCollection": make_data_collection()
    }
    if row_dict.get('MiddleName'):
        name["MiddleName"] = str(row_dict['MiddleName'])
    if row_dict.get('GenerationCodeOrSuffix'):
        name["GenerationCodeOrSuffix"] = str(row_dict['GenerationCodeOrSuffix'])
    person["hasPersonName"] = name

    person["hasPersonSexGender"] = {
        "@type": "PersonSexGender",
        "hasSex": "Sex_Female" if row_dict['Sex'] == "Female" else "Sex_Male",
        "hasRecordStatus": make_record_status(),
        "hasDataCollection": make_data_collection()
    }

    return person

def process_batch(batch):
    """Process a list of row dicts."""
    return [build_person_direct(row) for row in batch]


if __name__ == "__main__":
    df = pd.read_csv("person_sample_data.csv")
    # Convert to dicts for pickling and repeat to simulate scale
    base_rows = df.to_dict('records')
    # Replace NaN with None for cleaner handling
    for row in base_rows:
        for k, v in row.items():
            if pd.isna(v):
                row[k] = None

    # Scale up: repeat to get 9000 records (100x)
    scale_factor = 100
    rows = base_rows * scale_factor
    N = len(rows)
    
    num_cpus = multiprocessing.cpu_count()
    print("=" * 72)
    print(f"  DIRECT DICT BENCHMARK AT SCALE")
    print(f"  {N:,} records  |  {num_cpus} CPUs available")
    print("=" * 72)

    # --- Sequential ---
    print(f"\n  [1/4] Sequential ({N:,} records)...")
    t0 = time.perf_counter()
    results_seq = [build_person_direct(r) for r in rows]
    t1 = time.perf_counter()
    seq_time = t1 - t0
    seq_per = seq_time / N * 1000
    print(f"         {seq_time:.3f}s total  |  {seq_per:.4f} ms/record")

    # --- Parallel with different worker counts ---
    configs = [
        (4, 500),
        (8, 500),
        (num_cpus, 500),
    ]

    par_results = []
    for i, (workers, batch_size) in enumerate(configs):
        print(f"\n  [{i+2}/4] Multiprocessing: {workers} workers, batch={batch_size}...")
        batches = [rows[j:j+batch_size] for j in range(0, N, batch_size)]
        
        t0 = time.perf_counter()
        all_results = []
        with ProcessPoolExecutor(max_workers=workers) as executor:
            for batch_result in executor.map(process_batch, batches):
                all_results.extend(batch_result)
        t1 = time.perf_counter()
        
        par_time = t1 - t0
        par_per = par_time / N * 1000
        speedup = seq_time / par_time
        par_results.append((workers, batch_size, par_time, par_per, speedup))
        print(f"         {par_time:.3f}s total  |  {par_per:.4f} ms/record  |  {speedup:.1f}x speedup")

    # --- Summary ---
    print(f"\n{'=' * 72}")
    print(f"  {'Config':<30} {'Total s':>8} {'ms/rec':>8} {'Speedup':>8} {'1M est':>10}")
    print(f"  {'-'*30} {'-'*8} {'-'*8} {'-'*8} {'-'*10}")
    
    est_1m_seq = seq_per * 1_000_000 / 1000
    print(f"  {'Sequential':<30} {seq_time:8.3f} {seq_per:8.4f} {'1.0x':>8} {est_1m_seq/60:8.1f} min")
    
    for workers, bs, pt, pp, sp in par_results:
        est_1m = pp * 1_000_000 / 1000
        print(f"  {f'MP {workers}W batch={bs}':<30} {pt:8.3f} {pp:8.4f} {f'{sp:.1f}x':>8} {est_1m/60:8.1f} min")

    print(f"{'=' * 72}")

    # Verify count
    print(f"\n  Verified: {len(results_seq)} records produced sequentially")
    print(f"  Sample @id: {results_seq[0]['@id']}")
