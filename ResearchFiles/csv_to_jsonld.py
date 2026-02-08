import pandas as pd
from rdflib import Graph, URIRef, BNode, Literal, Namespace
from rdflib.namespace import RDF, XSD
from pyld import jsonld
import json
import time
from statistics import mean, median, stdev

# Define namespaces based on the SHACL file
ceds = Namespace("http://ceds.ed.gov/terms#")
cepi = Namespace("http://cepi-dev.state.mi.us/")
rdf = RDF
rdfs = Namespace("http://www.w3.org/2000/01/rdf-schema#")
sh = Namespace("http://www.w3.org/ns/shacl#")
xsd = XSD

# Load the CSV data - all records
df = pd.read_csv("person_sample_data.csv")

# Load the context for compaction (once)
with open("Person_context.json", "r") as f:
    ctx = json.load(f)

# Frame template
frame = {
    "@context": ctx["@context"],
    "@type": "Person",
    "@embed": "@always",
    "hasPersonName": {"@embed": "@always"},
    "hasPersonBirth": {"@embed": "@always"},
    "hasPersonSexGender": {"@embed": "@always"},
    "hasPersonIdentification": {"@embed": "@always"},
    "hasPersonDemographicRace": {"@embed": "@always"}
}

all_persons = []
timings = []
total_start = time.perf_counter()

for index, row in df.iterrows():
    record_start = time.perf_counter()

    # Create a new RDF graph per person
    g = Graph()
    g.bind("ceds", ceds)
    g.bind("cepi", cepi)
    g.bind("rdf", rdf)
    g.bind("rdfs", rdfs)
    g.bind("sh", sh)
    g.bind("xsd", xsd)
    # Create a unique IRI for each person using cepi namespace and PersonIdentifier
    person_uri = URIRef(f"http://cepi-dev.state.mi.us/person/{int(row['PersonIdentifiers'].split('|')[0])}")
    
    # Add the Person type
    g.add((person_uri, RDF.type, ceds.C200275))
    
    # Helper function to add RecordStatus and DataCollection
    def add_common_nodes(parent_node):
        # RecordStatus
        record_node = BNode()
        g.add((parent_node, ceds.P201001, record_node))  # hasRecordStatus
        g.add((record_node, RDF.type, ceds.C200411))    # RecordStatus
        g.add((record_node, ceds.P200999, URIRef("http://cepi-dev.state.mi.us/organization/3000000789")))  # CommittedByOrganization
        g.add((record_node, ceds.P001917, Literal("1900-01-01T00:00:00.000", datatype=XSD.dateTime)))  # RecordStartDateTime
        g.add((record_node, ceds.P001918, Literal("9999-12-31T00:00:00.000", datatype=XSD.dateTime)))  # RecordEndDateTime
        
        # DataCollection
        data_node = URIRef("http://example.org/dataCollection/45678")
        g.add((parent_node, ceds.P201003, data_node))  # hasDataCollection
        g.add((data_node, RDF.type, ceds.C200410))     # DataCollection
    
    # Person Name Shape
    name_node = BNode()
    g.add((person_uri, ceds.P600336, name_node))  # hasPersonNameShape
    g.add((name_node, RDF.type, ceds.C200377))    # PersonName class
    add_common_nodes(name_node)
    
    # Add name properties
    g.add((name_node, ceds.P000115, Literal(row['FirstName'])))  # FirstName
    if pd.notna(row['MiddleName']) and row['MiddleName']:
        g.add((name_node, ceds.P000184, Literal(row['MiddleName'])))  # MiddleName
    g.add((name_node, ceds.P000172, Literal(row['LastName'])))  # LastOrSurname
    if pd.notna(row['GenerationCodeOrSuffix']) and row['GenerationCodeOrSuffix']:
        g.add((name_node, ceds.P000121, Literal(row['GenerationCodeOrSuffix'])))  # GenerationCodeOrSuffix
    
    # Person Birth Shape
    birth_node = BNode()
    g.add((person_uri, ceds.P600335, birth_node))  # hasPersonBirthShape
    g.add((birth_node, RDF.type, ceds.C200376))    # PersonBirth class
    add_common_nodes(birth_node)
    g.add((birth_node, ceds.P000033, Literal(row['Birthdate'], datatype=XSD.date)))  # Birthdate
    
    # Person Sex Gender Shape
    sex_node = BNode()
    g.add((person_uri, ceds.P600338, sex_node))  # hasPersonSexGenderShape
    g.add((sex_node, RDF.type, ceds.C200011))    # PersonSexGender class
    add_common_nodes(sex_node)
    sex_value = "Sex_Female" if row['Sex'] == "Female" else "Sex_Male"
    g.add((sex_node, ceds.P000011, Literal(sex_value)))  # hasSex
    
    # Person Demographic Race Shapes - multiple, with arrays
    if pd.notna(row['RaceEthnicity']):
        race_groups = row['RaceEthnicity'].split('|')
        for group in race_groups:
            race_node = BNode()
            g.add((person_uri, ceds.P600035, race_node))  # hasPersonDemographicRaceShape
            g.add((race_node, RDF.type, ceds.C200282))     # PersonDemographicRace class
            add_common_nodes(race_node)
            races = group.split(',')
            for r in races:
                race_value = f"RaceAndEthnicity_{r.replace(' ', '')}"
                g.add((race_node, ceds.P000282, Literal(race_value)))  # hasRaceAndEthnicity
    
    # Person Identification Shapes - multiple
    if pd.notna(row['PersonIdentifiers']):
        ids = row['PersonIdentifiers'].split('|')
        systems = row['IdentificationSystems'].split('|') if pd.notna(row['IdentificationSystems']) else ['PersonIdentificationSystem_SSN'] * len(ids)
        types = row['PersonIdentifierTypes'].split('|') if pd.notna(row['PersonIdentifierTypes']) else ['PersonIdentifierType_PersonIdentifier'] * len(ids)
        for id_val, sys, typ in zip(ids, systems, types):
            id_node = BNode()
            g.add((person_uri, ceds.P600049, id_node))  # hasPersonIdentificationShape
            g.add((id_node, RDF.type, ceds.C200291))     # PersonIdentification class
            add_common_nodes(id_node)
            g.add((id_node, ceds.P001572, Literal(str(int(float(id_val))), datatype=XSD.token)))  # PersonIdentifier
            g.add((id_node, ceds.P001571, Literal(sys)))  # hasPersonIdentificationSystem
            g.add((id_node, ceds.P001573, Literal(typ)))  # hasPersonIdentifierType

    # Serialize, frame, compact this person
    expanded_str = g.serialize(format="json-ld")
    expanded = json.loads(expanded_str)
    framed = jsonld.frame(expanded, frame)
    compacted = jsonld.compact(framed, ctx)
    compacted["@context"] = "https://cepi-dev.state.mi.us/ontology/context-person.json"
    all_persons.append(compacted)

    record_end = time.perf_counter()
    elapsed_ms = (record_end - record_start) * 1000
    timings.append(elapsed_ms)
    print(f"  Record {index + 1:>3}/{len(df)}  ({row['FirstName']:>12} {row['LastName']:<15})  {elapsed_ms:8.2f} ms")

total_end = time.perf_counter()
total_elapsed = total_end - total_start

# Write all persons to output file
with open("person_compacted.json", "w") as f:
    json.dump(all_persons, f, indent=2)

# --- Timing Report ---
print("\n" + "=" * 65)
print(f"  TIMING REPORT  ({len(df)} records)")
print("=" * 65)
print(f"  Total wall time:       {total_elapsed:10.3f} s")
print(f"  Mean per record:       {mean(timings):10.2f} ms")
print(f"  Median per record:     {median(timings):10.2f} ms")
if len(timings) > 1:
    print(f"  Std dev per record:    {stdev(timings):10.2f} ms")
print(f"  Min per record:        {min(timings):10.2f} ms")
print(f"  Max per record:        {max(timings):10.2f} ms")
print("=" * 65)

# Extrapolate to 1,000,000 records
mean_ms = mean(timings)
est_seconds = (mean_ms * 1_000_000) / 1000
est_minutes = est_seconds / 60
est_hours = est_minutes / 60

print(f"\n  EXTRAPOLATION TO 1,000,000 RECORDS")
print(f"  -----------------------------------")
print(f"  Estimated time:  {est_seconds:,.0f} seconds")
print(f"                   {est_minutes:,.1f} minutes")
print(f"                   {est_hours:,.2f} hours")
print("=" * 65)
print(f"\nAll {len(df)} persons saved to person_compacted.json")