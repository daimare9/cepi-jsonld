"""Quick output comparison between original and direct approaches."""
import json

with open("person_compacted.json") as f:
    original = json.load(f)
with open("person_direct.json") as f:
    direct = json.load(f)

print(f"Original records: {len(original)}")
print(f"Direct records:   {len(direct)}")

o = original[0]
d = direct[0]

print(f"\n--- Record 1 comparison ---")
print(f"@id:  O={o['@id']}  D={d['@id']}  Match={o['@id']==d['@id']}")
print(f"@type: O={o['@type']}  D={d['@type']}  Match={o['@type']==d['@type']}")

on = o["hasPersonName"]
dn = d["hasPersonName"]
for k in ["FirstName", "LastOrSurname", "MiddleName", "GenerationCodeOrSuffix"]:
    ov = on.get(k, "MISSING")
    dv = dn.get(k, "MISSING")
    print(f"  Name.{k}: O={ov} D={dv} Match={ov==dv}")

print(f"  Birthdate: O={o['hasPersonBirth']['Birthdate']} D={d['hasPersonBirth']['Birthdate']} Match={o['hasPersonBirth']['Birthdate']==d['hasPersonBirth']['Birthdate']}")
print(f"  Sex: O={o['hasPersonSexGender']['hasSex']} D={d['hasPersonSexGender']['hasSex']} Match={o['hasPersonSexGender']['hasSex']==d['hasPersonSexGender']['hasSex']}")

o_race = o.get("hasPersonDemographicRace", [])
d_race = d.get("hasPersonDemographicRace", [])
if not isinstance(o_race, list): o_race = [o_race]
if not isinstance(d_race, list): d_race = [d_race]
print(f"  Race nodes: O={len(o_race)} D={len(d_race)} Match={len(o_race)==len(d_race)}")

o_id = o.get("hasPersonIdentification", [])
d_id = d.get("hasPersonIdentification", [])
if not isinstance(o_id, list): o_id = [o_id]
if not isinstance(d_id, list): d_id = [d_id]
print(f"  ID nodes: O={len(o_id)} D={len(d_id)} Match={len(o_id)==len(d_id)}") 

o_ids = sorted([r["@id"] for r in original])
d_ids = sorted([r["@id"] for r in direct])
print(f"\n  All @ids match: {o_ids == d_ids}")

o2 = original[1]
d2 = direct[1]
print(f"\n--- Record 2 (single race, no suffix) ---")
print(f"  Name: O={o2['hasPersonName']['FirstName']} D={d2['hasPersonName']['FirstName']}")
r2o = o2.get("hasPersonDemographicRace", {})
r2d = d2.get("hasPersonDemographicRace", {})
print(f"  Race type: O={type(r2o).__name__} D={type(r2d).__name__}")
if isinstance(r2o, dict):
    print(f"  Race val: O={r2o.get('hasRaceAndEthnicity')} D={r2d.get('hasRaceAndEthnicity')}")

# 1M scale test
import time
import pandas as pd

df = pd.read_csv("person_sample_data.csv")
base_rows = df.to_dict("records")
for row in base_rows:
    for k, v in row.items():
        if pd.isna(v):
            row[k] = None

# Scale to 100K
rows_100k = base_rows * 1112  # ~100K
print(f"\n--- 100K Scale Test ({len(rows_100k):,} records) ---")

import benchmark_direct_scale as bds
t0 = time.perf_counter()
results = [bds.build_person_direct(r) for r in rows_100k]
t1 = time.perf_counter()
total = t1 - t0
per_rec = total / len(rows_100k) * 1000
est_1m = per_rec * 1_000_000 / 1000

print(f"  Time: {total:.3f}s  |  {per_rec:.4f} ms/record")
print(f"  1M projection: {est_1m:.1f} seconds ({est_1m/60:.1f} min)")

# JSON serialization test
print(f"\n--- JSON Serialization (100K records) ---")
t0 = time.perf_counter()
output = json.dumps(results, indent=2)
t1 = time.perf_counter()
print(f"  json.dumps: {t1-t0:.3f}s  |  {len(output)/1024/1024:.1f} MB")
