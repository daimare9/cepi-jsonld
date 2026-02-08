"""Shape registry — load, manage, and access SHACL shape definitions.

Each shape is a self-contained folder containing SHACL, JSON-LD context,
mapping YAML, and optional sample data. The registry discovers and caches
these definitions for use by FieldMapper and JSONLDBuilder.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.request import urlopen

import yaml

from ceds_jsonld.exceptions import ShapeLoadError
from ceds_jsonld.logging import get_logger

_log = get_logger(__name__)

# Default ontologies directory shipped with the package
_PACKAGE_ONTOLOGIES = Path(__file__).parent / "ontologies"


@dataclass(frozen=True)
class ShapeDefinition:
    """A fully loaded shape definition ready for mapping and building.

    Attributes:
        name: Shape name (e.g. "person", "organization").
        base_dir: Path to the shape folder.
        shacl_path: Path to the SHACL Turtle file.
        context: Parsed JSON-LD context dict.
        mapping_config: Parsed YAML mapping configuration.
        sample_path: Path to sample CSV data, if present.
        example_path: Path to golden-file example JSON, if present.
    """

    name: str
    base_dir: Path
    shacl_path: Path
    context: dict[str, Any]
    mapping_config: dict[str, Any]
    sample_path: Path | None = None
    example_path: Path | None = None


class ShapeRegistry:
    """Discover, load, and manage shape definitions.

    Example:
        >>> registry = ShapeRegistry()
        >>> registry.load_shape("person")
        >>> shape = registry.get_shape("person")
        >>> shape.mapping_config["type"]
        'Person'
    """

    def __init__(self) -> None:
        self._shapes: dict[str, ShapeDefinition] = {}
        self._search_dirs: list[Path] = [_PACKAGE_ONTOLOGIES]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_search_dir(self, path: str | Path) -> None:
        """Add a directory to search for shape folders.

        Args:
            path: Directory containing shape sub-folders.

        Raises:
            FileNotFoundError: If the directory does not exist.
        """
        p = Path(path)
        if not p.is_dir():
            msg = f"Shape search directory does not exist: {p}"
            raise FileNotFoundError(msg)
        if p not in self._search_dirs:
            self._search_dirs.insert(0, p)  # user dirs searched first

    def load_shape(self, name: str, *, path: str | Path | None = None) -> ShapeDefinition:
        """Load a shape definition by name or explicit path.

        Args:
            name: Shape name (e.g. "person"). Used to find the folder.
            path: Optional explicit path to the shape folder. If provided,
                  skips the directory search.

        Returns:
            The loaded ShapeDefinition.

        Raises:
            ShapeLoadError: If required files are missing or malformed.
        """
        if path is not None:
            shape_dir = Path(path)
        else:
            shape_dir = self._find_shape_dir(name)

        shape_def = self._load_from_dir(name, shape_dir)
        self._shapes[name] = shape_def
        return shape_def

    def get_shape(self, name: str) -> ShapeDefinition:
        """Get a previously loaded shape definition.

        Args:
            name: Shape name.

        Returns:
            The ShapeDefinition.

        Raises:
            KeyError: If the shape has not been loaded.
        """
        if name not in self._shapes:
            msg = f"Shape '{name}' not loaded. Call load_shape('{name}') first. Loaded: {self.list_shapes()}"
            raise KeyError(msg)
        return self._shapes[name]

    def list_shapes(self) -> list[str]:
        """Return names of all loaded shapes."""
        return sorted(self._shapes)

    def list_available(self) -> list[str]:
        """Return names of all discoverable shape folders (loaded or not)."""
        found: set[str] = set()
        for search_dir in self._search_dirs:
            if not search_dir.is_dir():
                continue
            for child in search_dir.iterdir():
                if child.is_dir() and child.name != "base":
                    found.add(child.name)
        return sorted(found)

    def fetch_shape(
        self,
        name: str,
        *,
        shacl_url: str,
        context_url: str,
        mapping_url: str | None = None,
        cache_dir: str | Path | None = None,
        force: bool = False,
    ) -> ShapeDefinition:
        """Fetch shape files from URIs, cache locally, and load.

        Downloads SHACL and context files (and optionally mapping YAML) from
        remote URLs. Files are cached in ``cache_dir/<name>/`` so subsequent
        calls skip the download unless ``force=True``.

        A mapping file is **required** for loading. If ``mapping_url`` is not
        provided, the cache directory must already contain a mapping YAML
        (e.g. created manually or from ``SHACLIntrospector.generate_mapping_template()``).

        Args:
            name: Shape name (e.g. "organization").
            shacl_url: URL to the SHACL Turtle file.
            context_url: URL to the JSON-LD context file.
            mapping_url: Optional URL to a mapping YAML file.
            cache_dir: Local directory for caching. Defaults to
                ``<package_ontologies>/../.cache``.
            force: If True, re-download even if cached files exist.

        Returns:
            The loaded ShapeDefinition.

        Raises:
            ShapeLoadError: If download fails or required files are missing.
        """
        if cache_dir is None:
            cache_dir = _PACKAGE_ONTOLOGIES.parent / ".cache"
        shape_cache = Path(cache_dir) / name
        shape_cache.mkdir(parents=True, exist_ok=True)

        # Download files
        shacl_path = shape_cache / f"{name}_SHACL.ttl"
        context_path = shape_cache / f"{name}_context.json"
        mapping_path = shape_cache / f"{name}_mapping.yaml"

        self._download_if_needed(shacl_url, shacl_path, force=force)
        self._download_if_needed(context_url, context_path, force=force)

        if mapping_url is not None:
            self._download_if_needed(mapping_url, mapping_path, force=force)
        elif not mapping_path.exists():
            msg = f"No mapping YAML for shape '{name}'. Provide mapping_url or place a mapping file at {mapping_path}"
            raise ShapeLoadError(msg)

        return self.load_shape(name, path=shape_cache)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _download_if_needed(url: str, dest: Path, *, force: bool = False) -> None:
        """Download a URL to a local file if not already cached.

        Args:
            url: The remote URL to download.
            dest: Local destination path.
            force: Re-download even if the file exists.

        Raises:
            ShapeLoadError: If the download fails.
        """
        if dest.exists() and not force:
            _log.debug("cache.hit", path=str(dest))
            return

        _log.info("shape.download", url=url, dest=str(dest))
        try:
            with urlopen(url, timeout=30) as resp:  # noqa: S310
                data = resp.read()
            dest.write_bytes(data)
        except Exception as exc:
            msg = f"Failed to download {url}: {exc}"
            raise ShapeLoadError(msg) from exc

    def _find_shape_dir(self, name: str) -> Path:
        """Search registered directories for a shape folder."""
        for search_dir in self._search_dirs:
            candidate = search_dir / name
            if candidate.is_dir():
                return candidate
        msg = (
            f"Shape folder '{name}' not found in search directories: "
            f"{[str(d) for d in self._search_dirs]}. "
            f"Available shapes: {self.list_available()}"
        )
        raise ShapeLoadError(msg)

    def _load_from_dir(self, name: str, shape_dir: Path) -> ShapeDefinition:
        """Load all required files from a shape directory."""
        if not shape_dir.is_dir():
            msg = f"Shape directory does not exist: {shape_dir}"
            raise ShapeLoadError(msg)

        # --- SHACL ---
        shacl_path = self._find_file(shape_dir, "*SHACL*.ttl", "SHACL Turtle")

        # --- JSON-LD Context ---
        context_path = self._find_file(shape_dir, "*context*.json", "JSON-LD context")
        try:
            context = json.loads(context_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            msg = f"Failed to parse context file {context_path}: {exc}"
            raise ShapeLoadError(msg) from exc

        # --- Mapping YAML ---
        mapping_path = self._find_file(shape_dir, "*mapping*.yaml", "mapping YAML")
        try:
            mapping_config = yaml.safe_load(mapping_path.read_text(encoding="utf-8"))
        except (yaml.YAMLError, OSError) as exc:
            msg = f"Failed to parse mapping YAML {mapping_path}: {exc}"
            raise ShapeLoadError(msg) from exc

        # --- Optional files ---
        sample_path = self._find_file_optional(shape_dir, "*.csv")
        example_path = self._find_file_optional(shape_dir, "*example*.json")

        return ShapeDefinition(
            name=name,
            base_dir=shape_dir,
            shacl_path=shacl_path,
            context=context,
            mapping_config=mapping_config,
            sample_path=sample_path,
            example_path=example_path,
        )

    @staticmethod
    def _find_file(directory: Path, pattern: str, description: str) -> Path:
        """Find exactly one file matching a glob pattern."""
        matches = sorted(directory.glob(pattern))
        if not matches:
            msg = f"Missing {description} file (pattern '{pattern}') in {directory}"
            raise ShapeLoadError(msg)
        return matches[0]

    @staticmethod
    def _find_file_optional(directory: Path, pattern: str) -> Path | None:
        """Find a file matching a pattern, or None if not found."""
        matches = sorted(directory.glob(pattern))
        return matches[0] if matches else None
