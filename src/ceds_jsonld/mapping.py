"""Field mapper — apply declarative mapping configs to raw data rows.

The FieldMapper reads a mapping YAML config and transforms raw source dicts
(e.g. from CSV rows) into structured dicts ready for JSONLDBuilder.
"""

from __future__ import annotations

import copy
from typing import Any, Callable

from ceds_jsonld.exceptions import MappingError
from ceds_jsonld.transforms import BUILTIN_TRANSFORMS, get_transform


class FieldMapper:
    """Map raw data rows to structured dicts using a YAML mapping config.

    Example:
        >>> mapper = FieldMapper(shape_def.mapping_config)
        >>> mapped = mapper.map({"FirstName": "Jane", "LastName": "Doe", ...})
        >>> mapped["__id__"]
        '987654321'
        >>> mapped["hasPersonName"]
        [{"FirstName": "Jane", "LastOrSurname": "Doe"}]
    """

    def __init__(
        self,
        mapping_config: dict[str, Any],
        custom_transforms: dict[str, Callable[..., Any]] | None = None,
    ) -> None:
        """Initialize the mapper with a parsed mapping config.

        Args:
            mapping_config: Parsed YAML mapping configuration dict.
            custom_transforms: Optional user-defined transforms keyed by name.
        """
        self._config = mapping_config
        self._custom_transforms = custom_transforms

    # ------------------------------------------------------------------
    # Mapping flexibility — overrides & composition
    # ------------------------------------------------------------------

    def with_overrides(
        self,
        *,
        source_overrides: dict[str, dict[str, str]] | None = None,
        transform_overrides: dict[str, dict[str, str]] | None = None,
        id_source: str | None = None,
        id_transform: str | None = None,
    ) -> "FieldMapper":
        """Create a new FieldMapper with selective overrides applied.

        Returns a new mapper instance — the original is not mutated.

        Args:
            source_overrides: Dict mapping property name → field name → new source column.
                Example: ``{"hasPersonName": {"FirstName": "FIRST_NM"}}``
            transform_overrides: Dict mapping property name → field name → new transform.
                Example: ``{"hasPersonSexGender": {"hasSex": "my_custom_fn"}}``
            id_source: Override the ``id_source`` field.
            id_transform: Override the ``id_transform`` field.

        Returns:
            A new FieldMapper with the overrides applied.
        """
        new_config = copy.deepcopy(self._config)

        if id_source is not None:
            new_config["id_source"] = id_source
        if id_transform is not None:
            new_config["id_transform"] = id_transform

        if source_overrides:
            for prop_name, field_overrides in source_overrides.items():
                prop = new_config.get("properties", {}).get(prop_name)
                if prop is None:
                    continue
                for field_name, new_source in field_overrides.items():
                    for _key, field_def in prop.get("fields", {}).items():
                        if field_def.get("target") == field_name or _key == field_name:
                            field_def["source"] = new_source

        if transform_overrides:
            for prop_name, field_overrides in transform_overrides.items():
                prop = new_config.get("properties", {}).get(prop_name)
                if prop is None:
                    continue
                for field_name, new_transform in field_overrides.items():
                    for _key, field_def in prop.get("fields", {}).items():
                        if field_def.get("target") == field_name or _key == field_name:
                            field_def["transform"] = new_transform

        return FieldMapper(new_config, self._custom_transforms)

    @classmethod
    def compose(
        cls,
        base_config: dict[str, Any],
        overlay_config: dict[str, Any],
        custom_transforms: dict[str, Callable[..., Any]] | None = None,
    ) -> "FieldMapper":
        """Create a FieldMapper by deep-merging a base config with an overlay.

        The overlay selectively overrides fields in the base. Useful for
        per-district or per-source customization on top of a shared base mapping.

        Merge rules:
        - Top-level scalar keys in overlay replace base.
        - ``properties`` are merged per-property: overlay properties replace base
          properties of the same name; new properties are added.
        - Within a property, ``fields`` are merged per-field (same logic).
        - ``record_status_defaults`` and ``data_collection_defaults`` are deep-merged.

        Args:
            base_config: The base mapping config dict.
            overlay_config: The overlay mapping config dict.
            custom_transforms: Optional custom transforms.

        Returns:
            A new FieldMapper with the merged config.
        """
        merged = copy.deepcopy(base_config)

        for key, value in overlay_config.items():
            if key == "properties":
                base_props = merged.setdefault("properties", {})
                for prop_name, prop_def in value.items():
                    if prop_name in base_props:
                        # Merge fields within property
                        base_prop = base_props[prop_name]
                        for prop_key, prop_val in prop_def.items():
                            if prop_key == "fields" and "fields" in base_prop:
                                base_prop["fields"].update(prop_val)
                            else:
                                base_prop[prop_key] = prop_val
                    else:
                        base_props[prop_name] = copy.deepcopy(prop_def)
            elif key in ("record_status_defaults", "data_collection_defaults"):
                if key in merged and isinstance(merged[key], dict):
                    merged[key].update(value)
                else:
                    merged[key] = copy.deepcopy(value)
            else:
                merged[key] = value

        return cls(merged, custom_transforms)

    @property
    def config(self) -> dict[str, Any]:
        """Return the current mapping config (read-only copy)."""
        return copy.deepcopy(self._config)

    def map(self, raw_row: dict[str, Any]) -> dict[str, Any]:
        """Map a single raw data row to a structured dict for the builder.

        Args:
            raw_row: Dict of source field names to values (e.g. a CSV row).

        Returns:
            Structured dict with ``"__id__"`` and property-name keys, each
            mapping to a list of instance dicts.

        Raises:
            MappingError: If a required field is missing or a transform fails.
        """
        result: dict[str, Any] = {}

        # Extract document ID
        id_source = self._config["id_source"]
        id_raw = raw_row.get(id_source)
        if id_raw is None:
            msg = f"ID source field '{id_source}' is missing from row"
            raise MappingError(msg)
        id_value = str(id_raw)

        id_transform_name = self._config.get("id_transform")
        if id_transform_name:
            transform_fn = get_transform(id_transform_name, self._custom_transforms)
            id_value = transform_fn(id_value)
        result["__id__"] = id_value

        # Map each property
        for prop_name, prop_def in self._config.get("properties", {}).items():
            instances = self._map_property(raw_row, prop_name, prop_def)
            if instances:
                result[prop_name] = instances

        return result

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _map_property(
        self,
        raw_row: dict[str, Any],
        prop_name: str,
        prop_def: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Map a single property, respecting cardinality."""
        cardinality = prop_def.get("cardinality", "single")

        if cardinality == "multiple":
            return self._map_multiple(raw_row, prop_name, prop_def)
        return self._map_single(raw_row, prop_name, prop_def)

    def _map_single(
        self,
        raw_row: dict[str, Any],
        prop_name: str,
        prop_def: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Map a single-cardinality property (one instance)."""
        fields = prop_def.get("fields", {})
        instance: dict[str, Any] = {}

        for _field_key, field_def in fields.items():
            target = field_def.get("target", _field_key)
            source = field_def["source"]
            value = raw_row.get(source)

            if self._is_empty(value):
                if not field_def.get("optional", False):
                    msg = (
                        f"Required field '{source}' is missing or empty in row "
                        f"for property '{prop_name}'"
                    )
                    raise MappingError(msg)
                continue

            value = str(value)
            transform_name = field_def.get("transform")
            if transform_name:
                transform_fn = get_transform(transform_name, self._custom_transforms)
                value = transform_fn(value)

            instance[target] = value

        return [instance] if instance else []

    def _map_multiple(
        self,
        raw_row: dict[str, Any],
        prop_name: str,
        prop_def: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Map a multiple-cardinality property (pipe-delimited instances)."""
        split_on = prop_def.get("split_on", "|")
        fields = prop_def.get("fields", {})

        # Determine instance count from the first field's source column
        first_field_def = next(iter(fields.values()))
        first_source = first_field_def["source"]
        first_raw = raw_row.get(first_source)

        if self._is_empty(first_raw):
            # All fields missing — skip this property
            if first_field_def.get("optional", False):
                return []
            return []

        parts = str(first_raw).split(split_on)
        num_instances = len(parts)

        instances: list[dict[str, Any]] = []
        for i in range(num_instances):
            instance: dict[str, Any] = {}

            for _field_key, field_def in fields.items():
                target = field_def.get("target", _field_key)
                source = field_def["source"]
                raw_value = raw_row.get(source)

                if self._is_empty(raw_value):
                    if not field_def.get("optional", False):
                        continue
                    continue

                field_parts = str(raw_value).split(split_on)
                # Use the i-th part, or last available if source has fewer parts
                value = field_parts[i].strip() if i < len(field_parts) else field_parts[-1].strip()

                # Handle multi_value_split within a single instance
                multi_split = field_def.get("multi_value_split")
                if multi_split:
                    sub_values = [v.strip() for v in value.split(multi_split) if v.strip()]
                    transform_name = field_def.get("transform")
                    if transform_name:
                        transform_fn = get_transform(transform_name, self._custom_transforms)
                        sub_values = [transform_fn(v) for v in sub_values]
                    # Store as list (builder decides single vs array)
                    instance[target] = sub_values
                else:
                    transform_name = field_def.get("transform")
                    if transform_name:
                        transform_fn = get_transform(transform_name, self._custom_transforms)
                        value = transform_fn(value)
                    instance[target] = value

            if instance:
                instances.append(instance)

        return instances

    @staticmethod
    def _is_empty(value: Any) -> bool:
        """Check if a value is effectively empty."""
        if value is None:
            return True
        if isinstance(value, str) and not value.strip():
            return True
        # Handle pandas NaN
        try:
            import math
            if isinstance(value, float) and math.isnan(value):
                return True
        except (TypeError, ValueError):
            pass
        return False
