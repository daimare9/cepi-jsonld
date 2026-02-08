"""SHACL introspector — parse SHACL shapes into structured Python representations.

Reads SHACL Turtle files using rdflib and extracts a complete shape tree with
property paths, datatypes, cardinalities, allowed values (``sh:in``), and
nested sub-shapes. Supports mapping template generation and mapping validation.

This module is NOT in the hot path — it runs at dev/load time, not per-record.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rdflib import BNode, Graph, Namespace, URIRef
from rdflib.collection import Collection
from rdflib.namespace import RDF, XSD

from ceds_jsonld.exceptions import ShapeLoadError

# ---------------------------------------------------------------------------
# Namespaces
# ---------------------------------------------------------------------------

SH = Namespace("http://www.w3.org/ns/shacl#")
CEDS = Namespace("http://ceds.ed.gov/terms#")
CEPI = Namespace("http://cepi-dev.state.mi.us/")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class PropertyInfo:
    """Introspected information about a single SHACL property shape.

    Attributes:
        path: The IRI path of the property (e.g. ``ceds:P000115``).
        path_local: The local name extracted from the IRI (e.g. ``P000115``).
        name: Human-readable name derived from context or path (e.g. ``FirstName``).
        datatype: XSD datatype IRI if this is a literal property, or ``None``.
        node_shape: Name of the nested NodeShape if this is an object property.
        node_class: The ``sh:class`` IRI if specified.
        node_kind: The ``sh:nodeKind`` value (e.g. ``sh:IRI``).
        min_count: ``sh:minCount`` value, or ``None`` if unconstrained.
        max_count: ``sh:maxCount`` value, or ``None`` if unconstrained.
        allowed_values: List of allowed IRIs from ``sh:in``, or empty list.
        is_closed: Whether the parent node shape is closed.
    """

    path: str
    path_local: str
    name: str = ""
    datatype: str | None = None
    node_shape: str | None = None
    node_class: str | None = None
    node_kind: str | None = None
    min_count: int | None = None
    max_count: int | None = None
    allowed_values: list[str] = field(default_factory=list)
    is_closed: bool = False


@dataclass
class NodeShapeInfo:
    """Introspected information about a SHACL NodeShape.

    Attributes:
        iri: The full IRI of the shape (e.g. ``ceds:PersonShape``).
        local_name: The local name (e.g. ``PersonShape``).
        target_class: The ``sh:targetClass`` IRI, if specified.
        target_class_local: Local name of target class.
        is_closed: Whether ``sh:closed true`` is set.
        ignored_properties: List of ignored property IRIs.
        properties: List of PropertyInfo for this shape's ``sh:property`` entries.
        children: Dict mapping property name → child NodeShapeInfo for nested shapes.
    """

    iri: str
    local_name: str
    target_class: str | None = None
    target_class_local: str | None = None
    is_closed: bool = False
    ignored_properties: list[str] = field(default_factory=list)
    properties: list[PropertyInfo] = field(default_factory=list)
    children: dict[str, NodeShapeInfo] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Main introspector
# ---------------------------------------------------------------------------


class SHACLIntrospector:
    """Parse a SHACL Turtle file and extract structured shape information.

    Example:
        >>> introspector = SHACLIntrospector("ontologies/person/Person_SHACL.ttl")
        >>> tree = introspector.shape_tree()
        >>> tree.local_name
        'PersonShape'
        >>> [p.name for p in tree.properties]
        ['hasPersonBirth', 'hasPersonDemographicRace', ...]
    """

    def __init__(self, shacl_source: str | Path, *, format: str = "turtle") -> None:
        """Load and parse a SHACL file.

        Args:
            shacl_source: Path to a SHACL Turtle file, or Turtle string data.
            format: RDF serialization format (default: "turtle").

        Raises:
            ShapeLoadError: If parsing fails.
        """
        self._graph = Graph()
        try:
            source_path = Path(shacl_source)
            if source_path.exists():
                self._graph.parse(str(source_path), format=format)
            else:
                self._graph.parse(data=str(shacl_source), format=format)
        except Exception as exc:
            msg = f"Failed to parse SHACL source: {exc}"
            raise ShapeLoadError(msg) from exc

        self._graph.bind("sh", SH)
        self._graph.bind("ceds", CEDS)
        self._graph.bind("cepi", CEPI)

        # Cache parsed shapes
        self._node_shapes: dict[str, NodeShapeInfo] = {}
        self._root_shape: NodeShapeInfo | None = None
        self._parse_all()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def root_shape(self) -> NodeShapeInfo:
        """Return the root (top-level) shape that references other sub-shapes.

        The root is the NodeShape whose ``sh:property`` entries contain
        properties with ``sh:node`` references to other NodeShapes (i.e.
        the shape that *contains* sub-shapes rather than *being* one).

        Returns:
            The root NodeShapeInfo.

        Raises:
            ShapeLoadError: If no root shape can be determined.
        """
        if self._root_shape is None:
            msg = "No root shape found in SHACL file"
            raise ShapeLoadError(msg)
        return self._root_shape

    def shape_tree(self) -> NodeShapeInfo:
        """Return the full shape tree starting from the root shape.

        Same as ``root_shape()`` but with ``children`` populated recursively.

        Returns:
            The root NodeShapeInfo with nested children.
        """
        return self.root_shape()

    def all_shapes(self) -> dict[str, NodeShapeInfo]:
        """Return all parsed NodeShapes keyed by local name."""
        return dict(self._node_shapes)

    def get_shape(self, local_name: str) -> NodeShapeInfo:
        """Get a specific NodeShape by its local name.

        Args:
            local_name: e.g. "PersonShape", "PersonNameShape".

        Returns:
            The NodeShapeInfo.

        Raises:
            KeyError: If the shape is not found.
        """
        if local_name not in self._node_shapes:
            available = sorted(self._node_shapes)
            msg = f"Shape '{local_name}' not found. Available: {available}"
            raise KeyError(msg)
        return self._node_shapes[local_name]

    def to_dict(self) -> dict[str, Any]:
        """Export the full shape tree as a plain dict (JSON-serializable).

        Returns:
            Nested dict representation of the shape tree.
        """
        return self._shape_to_dict(self.root_shape())

    # ------------------------------------------------------------------
    # Mapping template generation
    # ------------------------------------------------------------------

    def generate_mapping_template(
        self,
        *,
        context_url: str = "",
        base_uri: str = "",
        context_lookup: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Generate a YAML-ready mapping config template from introspected shapes.

        The template has all ``target`` fields filled from the SHACL shape tree.
        Users fill in ``source`` columns for their data. If a ``context_lookup``
        dict is provided (mapping CEDS property IRIs to human-readable names),
        it uses those names for targets.

        Args:
            context_url: The ``@context`` URL for the output JSON-LD.
            base_uri: Base URI prefix for document ``@id`` values.
            context_lookup: Optional dict mapping property IRIs to human-readable
                names (e.g. from a JSON-LD context file).

        Returns:
            A dict that can be serialized to YAML as a mapping config.
        """
        root = self.root_shape()
        lookup = context_lookup or {}

        # Reverse lookup: IRI → human name (from context)
        iri_to_name = self._build_iri_to_name(lookup)

        template: dict[str, Any] = {
            "shape": root.local_name,
            "context_url": context_url,
            "base_uri": base_uri,
            "id_source": "TODO_ID_COLUMN",
            "id_transform": "first_pipe_split",
            "type": iri_to_name.get(root.target_class or "", root.target_class_local or root.local_name),
        }

        properties: dict[str, Any] = {}
        for prop in root.properties:
            if prop.node_shape and prop.node_shape in self._node_shapes:
                child = self._node_shapes[prop.node_shape]
                prop_name = iri_to_name.get(prop.path, prop.name or prop.path_local)
                prop_entry = self._build_property_template(child, prop, iri_to_name)
                properties[prop_name] = prop_entry

        template["properties"] = properties

        # Add record_status and data_collection defaults if RecordStatusShape exists
        if "RecordStatusShape" in self._node_shapes:
            template["record_status_defaults"] = {
                "type": "RecordStatus",
                "RecordStartDateTime": {
                    "value": "1900-01-01T00:00:00",
                    "datatype": "xsd:dateTime",
                },
                "RecordEndDateTime": {
                    "value": "9999-12-31T00:00:00",
                    "datatype": "xsd:dateTime",
                },
                "CommittedByOrganization": {
                    "value_id": "cepi:organization/TODO",
                },
            }
            template["data_collection_defaults"] = {
                "type": "DataCollection",
                "value_id": "http://example.org/dataCollection/TODO",
            }

        return template

    # ------------------------------------------------------------------
    # Mapping validation
    # ------------------------------------------------------------------

    def validate_mapping(
        self,
        mapping_config: dict[str, Any],
        *,
        context_lookup: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        """Validate a mapping YAML config against the introspected SHACL shape.

        Checks for:
        - Properties in the YAML that don't exist in SHACL
        - Required SHACL properties missing from the YAML
        - Datatype mismatches between YAML and SHACL
        - Sub-shape type mismatches

        Args:
            mapping_config: Parsed mapping YAML dict.
            context_lookup: Optional dict mapping CEDS IRIs to human-readable names.

        Returns:
            List of issue dicts, each with ``"level"`` ("error"/"warning"),
            ``"property"``, and ``"message"`` keys. Empty list = valid.
        """
        root = self.root_shape()
        lookup = context_lookup or {}
        iri_to_name = self._build_iri_to_name(lookup)
        {v: k for k, v in iri_to_name.items()}
        issues: list[dict[str, Any]] = []

        yaml_props = mapping_config.get("properties", {})
        shacl_prop_names = set()

        for prop in root.properties:
            human = iri_to_name.get(prop.path, prop.name or prop.path_local)
            shacl_prop_names.add(human)

            if human not in yaml_props:
                if prop.min_count and prop.min_count > 0:
                    issues.append(
                        {
                            "level": "error",
                            "property": human,
                            "message": (
                                f"Required SHACL property '{human}'"
                                f" (minCount={prop.min_count}) is missing from mapping YAML"
                            ),
                        }
                    )
                else:
                    issues.append(
                        {
                            "level": "warning",
                            "property": human,
                            "message": f"Optional SHACL property '{human}' is not mapped in YAML",
                        }
                    )
                continue

            yaml_prop = yaml_props[human]

            # Check sub-shape type
            if prop.node_shape and prop.node_shape in self._node_shapes:
                child = self._node_shapes[prop.node_shape]
                expected_type = iri_to_name.get(child.target_class or "", child.target_class_local or child.local_name)
                yaml_type = yaml_prop.get("type", "")
                if yaml_type and yaml_type != expected_type:
                    issues.append(
                        {
                            "level": "error",
                            "property": human,
                            "message": f"Type mismatch: YAML has '{yaml_type}', SHACL expects '{expected_type}'",
                        }
                    )

                # Check fields within sub-shape
                self._validate_sub_shape_fields(child, yaml_prop, human, iri_to_name, issues)

        # Check for YAML properties not in SHACL
        for yaml_name in yaml_props:
            if yaml_name not in shacl_prop_names:
                issues.append(
                    {
                        "level": "warning",
                        "property": yaml_name,
                        "message": f"YAML property '{yaml_name}' does not match any SHACL property on root shape",
                    }
                )

        return issues

    # ------------------------------------------------------------------
    # Internal parsing
    # ------------------------------------------------------------------

    def _parse_all(self) -> None:
        """Parse all NodeShapes from the graph and determine the root."""
        g = self._graph

        # First pass: collect all NodeShapes
        for shape_iri in g.subjects(RDF.type, SH.NodeShape):
            info = self._parse_node_shape(shape_iri)
            self._node_shapes[info.local_name] = info

        # Second pass: resolve children (properties with sh:node)
        for shape_info in self._node_shapes.values():
            for prop in shape_info.properties:
                if prop.node_shape and prop.node_shape in self._node_shapes:
                    child_name = prop.name or prop.path_local
                    shape_info.children[child_name] = self._node_shapes[prop.node_shape]

        # Determine root: the shape with the most children that reference other NodeShapes
        # Prefer shapes that aren't referenced as sh:node by any other shape
        referenced_shapes = set()
        for shape_info in self._node_shapes.values():
            for prop in shape_info.properties:
                if prop.node_shape:
                    referenced_shapes.add(prop.node_shape)

        candidates = [name for name in self._node_shapes if name not in referenced_shapes]

        if candidates:
            # Pick the one with the most child references
            self._root_shape = max(
                (self._node_shapes[c] for c in candidates),
                key=lambda s: len(s.children),
            )
        elif self._node_shapes:
            # Fallback: pick the one with most properties
            self._root_shape = max(
                self._node_shapes.values(),
                key=lambda s: len(s.properties),
            )

    def _parse_node_shape(self, shape_iri: URIRef | BNode) -> NodeShapeInfo:
        """Parse a single NodeShape from the graph."""
        g = self._graph

        local_name = self._local_name(shape_iri)
        target_class = g.value(shape_iri, SH.targetClass)
        is_closed = bool(g.value(shape_iri, SH.closed))

        # Ignored properties
        ignored = []
        ignored_list = g.value(shape_iri, SH.ignoredProperties)
        if ignored_list:
            ignored = [str(item) for item in Collection(g, ignored_list)]

        # Properties
        properties: list[PropertyInfo] = []
        for prop_node in g.objects(shape_iri, SH.property):
            prop_info = self._parse_property_shape(prop_node)
            properties.append(prop_info)

        # Sort properties by path for deterministic output
        properties.sort(key=lambda p: p.path)

        return NodeShapeInfo(
            iri=str(shape_iri),
            local_name=local_name,
            target_class=str(target_class) if target_class else None,
            target_class_local=self._local_name(target_class) if target_class else None,
            is_closed=is_closed,
            ignored_properties=ignored,
            properties=properties,
        )

    def _parse_property_shape(self, prop_node: URIRef | BNode) -> PropertyInfo:
        """Parse a single PropertyShape from the graph."""
        g = self._graph

        path = g.value(prop_node, SH.path)
        datatype = g.value(prop_node, SH.datatype)
        node_ref = g.value(prop_node, SH.node)
        class_ref = g.value(prop_node, getattr(SH, "class"))
        node_kind = g.value(prop_node, SH.nodeKind)
        min_count = g.value(prop_node, SH.minCount)
        max_count = g.value(prop_node, SH.maxCount)

        # sh:in list
        in_list_node = g.value(prop_node, getattr(SH, "in"))
        allowed: list[str] = []
        if in_list_node:
            allowed = [str(item) for item in Collection(g, in_list_node)]

        path_str = str(path) if path else ""
        path_local = self._local_name(path) if path else ""

        return PropertyInfo(
            path=path_str,
            path_local=path_local,
            name=path_local,  # will be refined with context lookup
            datatype=str(datatype) if datatype else None,
            node_shape=self._local_name(node_ref) if node_ref else None,
            node_class=str(class_ref) if class_ref else None,
            node_kind=str(node_kind) if node_kind else None,
            min_count=int(min_count) if min_count is not None else None,
            max_count=int(max_count) if max_count is not None else None,
            allowed_values=allowed,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _local_name(iri: URIRef | BNode | None) -> str:
        """Extract the local name from an IRI (part after # or last /)."""
        if iri is None:
            return ""
        s = str(iri)
        if "#" in s:
            return s.rsplit("#", 1)[1]
        if "/" in s:
            return s.rsplit("/", 1)[1]
        return s

    @staticmethod
    def _build_iri_to_name(context_lookup: dict[str, str]) -> dict[str, str]:
        """Build a reverse lookup from IRI → human-readable name.

        Args:
            context_lookup: A JSON-LD context dict where keys are names and
                values are IRIs or dicts with ``@id``.

        Returns:
            Dict mapping full IRI strings to their context names.
        """
        result: dict[str, str] = {}
        for name, value in context_lookup.items():
            if name.startswith("@"):
                continue
            if isinstance(value, str):
                # Resolve prefixed IRIs
                iri = value
                for prefix_name, prefix_iri in context_lookup.items():
                    if isinstance(prefix_iri, str) and ":" in iri and not iri.startswith("http"):
                        parts = iri.split(":", 1)
                        if parts[0] == prefix_name:
                            iri = prefix_iri + parts[1]
                            break
                result[iri] = name
            elif isinstance(value, dict) and "@id" in value:
                result[str(value["@id"])] = name
        return result

    def _build_property_template(
        self,
        child_shape: NodeShapeInfo,
        parent_prop: PropertyInfo,
        iri_to_name: dict[str, str],
    ) -> dict[str, Any]:
        """Build a mapping template entry for a sub-shape property."""
        child_type = iri_to_name.get(
            child_shape.target_class or "",
            child_shape.target_class_local or child_shape.local_name,
        )

        # Determine if this is single or multiple cardinality
        cardinality = "single"
        if parent_prop.max_count is None:
            cardinality = "multiple"

        entry: dict[str, Any] = {
            "type": child_type,
            "cardinality": cardinality,
            "include_record_status": any(p.node_shape == "RecordStatusShape" for p in child_shape.properties),
            "include_data_collection": any(
                p.path_local in ("P201003", "hasDataCollectionShape") or p.node_class == str(CEDS.C200410)
                for p in child_shape.properties
            ),
        }

        if cardinality == "multiple":
            entry["split_on"] = "|"

        # Build fields (excluding RecordStatus/DataCollection which are injected)
        fields: dict[str, Any] = {}
        for prop in child_shape.properties:
            # Skip injected shapes
            if prop.node_shape in ("RecordStatusShape", "DataCollectionShape"):
                continue
            if prop.node_class and prop.node_class in (str(CEDS.C200411), str(CEDS.C200410)):
                continue

            field_name = iri_to_name.get(prop.path, prop.name or prop.path_local)
            field_entry: dict[str, Any] = {
                "source": f"TODO_{field_name}",
                "target": field_name,
            }

            if prop.datatype:
                # Map full XSD IRI to prefixed form
                xsd_prefix = str(XSD)
                if prop.datatype.startswith(xsd_prefix):
                    field_entry["datatype"] = f"xsd:{prop.datatype[len(xsd_prefix) :]}"
                else:
                    field_entry["datatype"] = prop.datatype

            if prop.allowed_values:
                field_entry["# allowed_values"] = [self._local_name(URIRef(v)) for v in prop.allowed_values]

            if prop.min_count is None or prop.min_count == 0:
                field_entry["optional"] = True

            fields[field_name] = field_entry

        entry["fields"] = fields
        return entry

    def _validate_sub_shape_fields(
        self,
        child_shape: NodeShapeInfo,
        yaml_prop: dict[str, Any],
        parent_name: str,
        iri_to_name: dict[str, str],
        issues: list[dict[str, Any]],
    ) -> None:
        """Validate fields within a sub-shape property."""
        yaml_fields = yaml_prop.get("fields", {})

        shacl_field_names = set()
        for prop in child_shape.properties:
            # Skip injected shapes
            if prop.node_shape in ("RecordStatusShape", "DataCollectionShape"):
                continue
            if prop.node_class and prop.node_class in (str(CEDS.C200411), str(CEDS.C200410)):
                continue

            field_name = iri_to_name.get(prop.path, prop.name or prop.path_local)
            shacl_field_names.add(field_name)

            # Find matching YAML field (match by target, not key)
            yaml_match = None
            for _key, fdef in yaml_fields.items():
                if fdef.get("target") == field_name or _key == field_name:
                    yaml_match = fdef
                    break

            if yaml_match is None:
                if prop.min_count and prop.min_count > 0:
                    issues.append(
                        {
                            "level": "error",
                            "property": f"{parent_name}.{field_name}",
                            "message": f"Required SHACL field '{field_name}' (minCount={prop.min_count}) missing from YAML",
                        }
                    )
                continue

            # Check datatype
            if prop.datatype and yaml_match.get("datatype"):
                xsd_prefix = str(XSD)
                expected_dt = prop.datatype
                if expected_dt.startswith(xsd_prefix):
                    expected_dt = f"xsd:{expected_dt[len(xsd_prefix) :]}"
                yaml_dt = yaml_match["datatype"]
                if yaml_dt != expected_dt and yaml_dt != prop.datatype:
                    issues.append(
                        {
                            "level": "warning",
                            "property": f"{parent_name}.{field_name}",
                            "message": f"Datatype mismatch: YAML has '{yaml_dt}', SHACL expects '{expected_dt}'",
                        }
                    )

    def _shape_to_dict(self, shape: NodeShapeInfo) -> dict[str, Any]:
        """Convert a NodeShapeInfo tree to a plain dict."""
        result: dict[str, Any] = {
            "iri": shape.iri,
            "local_name": shape.local_name,
            "target_class": shape.target_class,
            "target_class_local": shape.target_class_local,
            "is_closed": shape.is_closed,
            "properties": [],
            "children": {},
        }

        for prop in shape.properties:
            prop_dict: dict[str, Any] = {
                "path": prop.path,
                "path_local": prop.path_local,
                "name": prop.name,
                "datatype": prop.datatype,
                "node_shape": prop.node_shape,
                "node_class": prop.node_class,
                "min_count": prop.min_count,
                "max_count": prop.max_count,
            }
            if prop.allowed_values:
                prop_dict["allowed_values"] = prop.allowed_values
            result["properties"].append(prop_dict)

        for child_name, child_shape in shape.children.items():
            result["children"][child_name] = self._shape_to_dict(child_shape)

        return result
