"""Tests for the SHACL introspector module.

Validates:
- SHACL Turtle parsing and shape tree construction
- Property extraction (paths, datatypes, cardinality, sh:in)
- Root shape detection
- Mapping template generation
- Mapping validation against introspected shapes
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from ceds_jsonld.exceptions import ShapeLoadError
from ceds_jsonld.introspector import NodeShapeInfo, PropertyInfo, SHACLIntrospector

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PERSON_SHACL = Path(__file__).resolve().parent.parent / "src" / "ceds_jsonld" / "ontologies" / "person" / "Person_SHACL.ttl"
PERSON_CONTEXT = Path(__file__).resolve().parent.parent / "src" / "ceds_jsonld" / "ontologies" / "person" / "person_context.json"
PERSON_MAPPING = Path(__file__).resolve().parent.parent / "src" / "ceds_jsonld" / "ontologies" / "person" / "person_mapping.yaml"


@pytest.fixture()
def introspector() -> SHACLIntrospector:
    """Create an introspector from the Person SHACL file."""
    return SHACLIntrospector(PERSON_SHACL)


@pytest.fixture()
def person_context() -> dict:
    """Load the Person JSON-LD context."""
    return json.loads(PERSON_CONTEXT.read_text(encoding="utf-8"))["@context"]


@pytest.fixture()
def person_mapping_config() -> dict:
    """Load the Person mapping YAML config."""
    return yaml.safe_load(PERSON_MAPPING.read_text(encoding="utf-8"))


# ===================================================================
# Basic parsing tests
# ===================================================================


class TestSHACLParsing:
    """Tests for basic SHACL file parsing."""

    def test_parse_person_shacl(self, introspector: SHACLIntrospector) -> None:
        """Person SHACL file should parse without errors."""
        shapes = introspector.all_shapes()
        assert len(shapes) > 0

    def test_discovers_all_node_shapes(self, introspector: SHACLIntrospector) -> None:
        """All 7 NodeShapes from Person_SHACL.ttl should be found."""
        shapes = introspector.all_shapes()
        expected = {
            "PersonShape",
            "PersonBirthShape",
            "PersonDemographicRaceShape",
            "PersonIdentificationShape",
            "PersonNameShape",
            "PersonSexGenderShape",
            "RecordStatusShape",
        }
        assert set(shapes.keys()) == expected

    def test_invalid_source_raises_error(self) -> None:
        """Non-existent file paths or bad Turtle should raise ShapeLoadError."""
        with pytest.raises(ShapeLoadError):
            SHACLIntrospector("definitely_not_a_valid_turtle_string!!! @#$%^&")

    def test_parse_from_string(self) -> None:
        """Should parse SHACL from a Turtle string."""
        ttl = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix ex: <http://example.org/> .

        ex:TestShape a sh:NodeShape ;
            sh:targetClass ex:TestClass ;
            sh:closed true ;
            sh:property ex:nameProperty .

        ex:nameProperty a sh:PropertyShape ;
            sh:path ex:name .
        """
        intro = SHACLIntrospector(ttl)
        shapes = intro.all_shapes()
        assert "TestShape" in shapes
        assert shapes["TestShape"].is_closed is True


# ===================================================================
# Root shape detection
# ===================================================================


class TestRootShape:
    """Tests for root shape identification."""

    def test_root_shape_is_person(self, introspector: SHACLIntrospector) -> None:
        """PersonShape should be the root — it's not referenced by any other shape."""
        root = introspector.root_shape()
        assert root.local_name == "PersonShape"

    def test_root_has_five_properties(self, introspector: SHACLIntrospector) -> None:
        """PersonShape should have 5 property shapes."""
        root = introspector.root_shape()
        assert len(root.properties) == 5

    def test_shape_tree_is_root(self, introspector: SHACLIntrospector) -> None:
        """shape_tree() is an alias for root_shape()."""
        assert introspector.shape_tree().local_name == introspector.root_shape().local_name


# ===================================================================
# NodeShape details
# ===================================================================


class TestNodeShapeDetails:
    """Tests for individual NodeShape property extraction."""

    def test_person_target_class(self, introspector: SHACLIntrospector) -> None:
        """PersonShape should target ceds:C200275."""
        ps = introspector.get_shape("PersonShape")
        assert ps.target_class is not None
        assert ps.target_class.endswith("C200275")

    def test_all_shapes_closed(self, introspector: SHACLIntrospector) -> None:
        """All NodeShapes in Person SHACL are sh:closed true."""
        for shape in introspector.all_shapes().values():
            assert shape.is_closed is True, f"{shape.local_name} should be closed"

    def test_ignored_properties_present(self, introspector: SHACLIntrospector) -> None:
        """All NodeShapes should have ignored properties (rdf:type, rdf:id, etc.)."""
        for shape in introspector.all_shapes().values():
            assert len(shape.ignored_properties) > 0, f"{shape.local_name} missing ignoredProperties"

    def test_get_shape_not_found(self, introspector: SHACLIntrospector) -> None:
        """Requesting a non-existent shape should raise KeyError."""
        with pytest.raises(KeyError, match="FakeShape"):
            introspector.get_shape("FakeShape")


# ===================================================================
# PropertyShape details
# ===================================================================


class TestPropertyShapeDetails:
    """Tests for property-level introspection."""

    def test_person_birth_has_birthdate(self, introspector: SHACLIntrospector) -> None:
        """PersonBirthShape should include a Birthdate property with path ceds:P000033."""
        birth = introspector.get_shape("PersonBirthShape")
        paths = {p.path_local for p in birth.properties}
        assert "P000033" in paths  # Birthdate path

    def test_person_name_has_four_fields(self, introspector: SHACLIntrospector) -> None:
        """PersonNameShape should have FirstName, MiddleName, LastOrSurname, GenerationCodeOrSuffix + injected shapes."""
        name = introspector.get_shape("PersonNameShape")
        # 4 leaf properties + hasDataCollectionShape + hasRecordStatusShape = 6
        assert len(name.properties) == 6

    def test_person_identification_system_has_allowed_values(
        self, introspector: SHACLIntrospector
    ) -> None:
        """hasPersonIdentificationSystemShape should have 21 allowed values from sh:in."""
        ident = introspector.get_shape("PersonIdentificationShape")
        # Find the property that has allowed_values
        sys_props = [p for p in ident.properties if "P001571" in p.path]
        assert len(sys_props) == 1
        assert len(sys_props[0].allowed_values) == 21

    def test_record_status_committed_by_has_class(
        self, introspector: SHACLIntrospector
    ) -> None:
        """CommittedByOrganization should have sh:class and sh:nodeKind."""
        rs = introspector.get_shape("RecordStatusShape")
        committed = [p for p in rs.properties if "P200999" in p.path]
        assert len(committed) == 1
        assert committed[0].node_class is not None
        assert committed[0].node_class.endswith("C200239")
        assert committed[0].node_kind is not None

    def test_has_person_birth_references_sub_shape(
        self, introspector: SHACLIntrospector
    ) -> None:
        """hasPersonBirth property on PersonShape should reference PersonBirthShape."""
        root = introspector.root_shape()
        birth_props = [p for p in root.properties if p.node_shape == "PersonBirthShape"]
        assert len(birth_props) == 1
        assert birth_props[0].node_class is not None
        assert birth_props[0].node_class.endswith("C200376")

    def test_children_populated(self, introspector: SHACLIntrospector) -> None:
        """Root PersonShape should have children dict populated with sub-shapes."""
        root = introspector.root_shape()
        assert len(root.children) == 5
        child_shapes = {c.local_name for c in root.children.values()}
        expected = {
            "PersonBirthShape",
            "PersonDemographicRaceShape",
            "PersonIdentificationShape",
            "PersonNameShape",
            "PersonSexGenderShape",
        }
        assert child_shapes == expected


# ===================================================================
# Dict export
# ===================================================================


class TestDictExport:
    """Tests for to_dict() serialization."""

    def test_to_dict_has_root_info(self, introspector: SHACLIntrospector) -> None:
        """to_dict() should return a dict with root shape info."""
        d = introspector.to_dict()
        assert d["local_name"] == "PersonShape"
        assert d["is_closed"] is True
        assert "properties" in d
        assert "children" in d

    def test_to_dict_is_serializable(self, introspector: SHACLIntrospector) -> None:
        """to_dict() output should be JSON-serializable (no rdflib objects)."""
        d = introspector.to_dict()
        json_str = json.dumps(d, indent=2)
        assert len(json_str) > 100

    def test_to_dict_children_nested(self, introspector: SHACLIntrospector) -> None:
        """Children in to_dict() are recursively converted."""
        d = introspector.to_dict()
        assert len(d["children"]) == 5
        # Check one child
        child_names = {child["local_name"] for child in d["children"].values()}
        assert "PersonNameShape" in child_names


# ===================================================================
# Mapping template generation
# ===================================================================


class TestMappingTemplateGeneration:
    """Tests for generate_mapping_template()."""

    def test_generates_template_for_person(
        self, introspector: SHACLIntrospector, person_context: dict
    ) -> None:
        """Template should contain all 5 top-level properties."""
        tpl = introspector.generate_mapping_template(context_lookup=person_context)
        assert tpl["shape"] == "PersonShape"
        assert "properties" in tpl
        assert len(tpl["properties"]) == 5

    def test_template_has_correct_type(
        self, introspector: SHACLIntrospector, person_context: dict
    ) -> None:
        """Root type should be mapped through context to 'Person'."""
        tpl = introspector.generate_mapping_template(context_lookup=person_context)
        assert tpl["type"] == "Person"

    def test_template_properties_have_fields(
        self, introspector: SHACLIntrospector, person_context: dict
    ) -> None:
        """Each property should have 'type', 'fields', and 'cardinality'."""
        tpl = introspector.generate_mapping_template(context_lookup=person_context)
        for name, prop_def in tpl["properties"].items():
            assert "type" in prop_def, f"'{name}' missing 'type'"
            assert "fields" in prop_def, f"'{name}' missing 'fields'"
            assert "cardinality" in prop_def, f"'{name}' missing 'cardinality'"

    def test_template_name_fields(
        self, introspector: SHACLIntrospector, person_context: dict
    ) -> None:
        """PersonName property should have FirstName, MiddleName, LastOrSurname, GenerationCodeOrSuffix."""
        tpl = introspector.generate_mapping_template(context_lookup=person_context)
        name_prop = tpl["properties"]["hasPersonName"]
        field_keys = set(name_prop["fields"].keys())
        assert "FirstName" in field_keys
        assert "LastOrSurname" in field_keys

    def test_template_record_status_defaults(
        self, introspector: SHACLIntrospector, person_context: dict
    ) -> None:
        """Template should include record_status_defaults."""
        tpl = introspector.generate_mapping_template(context_lookup=person_context)
        assert "record_status_defaults" in tpl
        assert tpl["record_status_defaults"]["type"] == "RecordStatus"

    def test_template_is_yaml_serializable(
        self, introspector: SHACLIntrospector, person_context: dict
    ) -> None:
        """Template should be serializable to YAML without errors."""
        tpl = introspector.generate_mapping_template(context_lookup=person_context)
        yaml_str = yaml.dump(tpl, default_flow_style=False)
        assert len(yaml_str) > 100
        # Should round-trip back
        loaded = yaml.safe_load(yaml_str)
        assert loaded["shape"] == "PersonShape"

    def test_template_without_context(
        self, introspector: SHACLIntrospector
    ) -> None:
        """Template should work without context — uses local IRI names."""
        tpl = introspector.generate_mapping_template()
        assert tpl["shape"] == "PersonShape"
        assert len(tpl["properties"]) == 5

    def test_template_identification_system_allowed_values(
        self, introspector: SHACLIntrospector, person_context: dict
    ) -> None:
        """PersonIdentification fields should note allowed values from sh:in."""
        tpl = introspector.generate_mapping_template(context_lookup=person_context)
        ident = tpl["properties"]["hasPersonIdentification"]
        # Find the field that documents allowed values
        has_allowed = any(
            "# allowed_values" in f
            for f in ident["fields"].values()
            if isinstance(f, dict)
        )
        assert has_allowed, "Expected at least one field with allowed_values comment"


# ===================================================================
# Mapping validation
# ===================================================================


class TestMappingValidation:
    """Tests for validate_mapping()."""

    def test_valid_mapping_no_errors(
        self,
        introspector: SHACLIntrospector,
        person_mapping_config: dict,
        person_context: dict,
    ) -> None:
        """The real Person mapping YAML should produce no errors."""
        issues = introspector.validate_mapping(
            person_mapping_config, context_lookup=person_context
        )
        errors = [i for i in issues if i["level"] == "error"]
        assert len(errors) == 0, f"Unexpected errors: {errors}"

    def test_missing_required_property_error(
        self, introspector: SHACLIntrospector, person_context: dict
    ) -> None:
        """A mapping with all properties removed should produce warnings."""
        empty_mapping: dict = {"properties": {}}
        issues = introspector.validate_mapping(
            empty_mapping, context_lookup=person_context
        )
        # All 5 top-level properties are not required (no minCount) so should be warnings
        assert len(issues) > 0
        assert all(i["level"] in ("error", "warning") for i in issues)

    def test_extra_property_warning(
        self, introspector: SHACLIntrospector, person_context: dict, person_mapping_config: dict
    ) -> None:
        """A mapping with an unknown property should produce a warning."""
        import copy

        bad_mapping = copy.deepcopy(person_mapping_config)
        bad_mapping["properties"]["fakeProperty"] = {"type": "FakeThing"}
        issues = introspector.validate_mapping(
            bad_mapping, context_lookup=person_context
        )
        fake_issues = [
            i for i in issues if i["property"] == "fakeProperty"
        ]
        assert len(fake_issues) == 1
        assert fake_issues[0]["level"] == "warning"

    def test_type_mismatch_error(
        self, introspector: SHACLIntrospector, person_context: dict, person_mapping_config: dict
    ) -> None:
        """A property with the wrong type should produce an error."""
        import copy

        bad_mapping = copy.deepcopy(person_mapping_config)
        bad_mapping["properties"]["hasPersonName"]["type"] = "WrongType"
        issues = introspector.validate_mapping(
            bad_mapping, context_lookup=person_context
        )
        type_issues = [
            i for i in issues if "Type mismatch" in i["message"]
        ]
        assert len(type_issues) >= 1

    def test_validation_without_context(
        self, introspector: SHACLIntrospector
    ) -> None:
        """Validation should work without context — uses IRI local names."""
        # Mapping using raw IRI local names
        issues = introspector.validate_mapping({"properties": {}})
        # Should produce warnings for missing properties (not crash)
        assert isinstance(issues, list)
        assert len(issues) > 0


# ===================================================================
# Data class tests
# ===================================================================


class TestDataClasses:
    """Test PropertyInfo and NodeShapeInfo data classes."""

    def test_property_info_defaults(self) -> None:
        """PropertyInfo should have sensible defaults."""
        p = PropertyInfo(path="http://example.org/p1", path_local="p1")
        assert p.name == ""
        assert p.datatype is None
        assert p.node_shape is None
        assert p.min_count is None
        assert p.max_count is None
        assert p.allowed_values == []
        assert p.is_closed is False

    def test_node_shape_info_defaults(self) -> None:
        """NodeShapeInfo should have sensible defaults."""
        n = NodeShapeInfo(iri="http://example.org/S1", local_name="S1")
        assert n.target_class is None
        assert n.is_closed is False
        assert n.properties == []
        assert n.children == {}
        assert n.ignored_properties == []
