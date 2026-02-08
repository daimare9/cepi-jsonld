"""Tests for ShapeRegistry and ShapeDefinition."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread

import pytest
import yaml

from ceds_jsonld.exceptions import ShapeLoadError
from ceds_jsonld.registry import ShapeDefinition, ShapeRegistry


class TestShapeRegistryLoading:
    """Test loading shapes from the shipped ontologies."""

    def test_load_person_shape(self):
        registry = ShapeRegistry()
        shape = registry.load_shape("person")
        assert isinstance(shape, ShapeDefinition)
        assert shape.name == "person"

    def test_person_shacl_path_exists(self, person_shape_def):
        assert person_shape_def.shacl_path.exists()
        assert person_shape_def.shacl_path.suffix == ".ttl"

    def test_person_context_is_dict(self, person_shape_def):
        assert isinstance(person_shape_def.context, dict)
        assert "@context" in person_shape_def.context

    def test_person_mapping_config_has_required_keys(self, person_shape_def):
        cfg = person_shape_def.mapping_config
        assert cfg["type"] == "Person"
        assert "properties" in cfg
        assert "base_uri" in cfg
        assert "id_source" in cfg

    def test_person_mapping_has_expected_properties(self, person_shape_def):
        props = person_shape_def.mapping_config["properties"]
        expected = {
            "hasPersonDemographicRace",
            "hasPersonIdentification",
            "hasPersonBirth",
            "hasPersonName",
            "hasPersonSexGender",
        }
        assert expected == set(props)

    def test_person_sample_path_exists(self, person_shape_def):
        assert person_shape_def.sample_path is not None
        assert person_shape_def.sample_path.exists()

    def test_person_example_path_exists(self, person_shape_def):
        assert person_shape_def.example_path is not None
        assert person_shape_def.example_path.exists()


class TestShapeRegistryAPI:
    """Test registry management operations."""

    def test_list_shapes_initially_empty(self):
        registry = ShapeRegistry()
        assert registry.list_shapes() == []

    def test_list_shapes_after_load(self):
        registry = ShapeRegistry()
        registry.load_shape("person")
        assert registry.list_shapes() == ["person"]

    def test_get_shape_returns_same_instance(self):
        registry = ShapeRegistry()
        loaded = registry.load_shape("person")
        fetched = registry.get_shape("person")
        assert loaded is fetched

    def test_get_shape_not_loaded_raises(self):
        registry = ShapeRegistry()
        with pytest.raises(KeyError, match="person"):
            registry.get_shape("person")

    def test_list_available_includes_person(self):
        registry = ShapeRegistry()
        available = registry.list_available()
        assert "person" in available

    def test_list_available_excludes_base(self):
        registry = ShapeRegistry()
        available = registry.list_available()
        assert "base" not in available

    def test_add_search_dir_nonexistent_raises(self, tmp_path):
        registry = ShapeRegistry()
        with pytest.raises(FileNotFoundError):
            registry.add_search_dir(tmp_path / "nonexistent")


class TestShapeLoadErrors:
    """Test error handling for malformed or missing shapes."""

    def test_load_nonexistent_shape_raises(self):
        registry = ShapeRegistry()
        with pytest.raises(ShapeLoadError, match="nonexistent_shape"):
            registry.load_shape("nonexistent_shape")

    def test_load_from_empty_dir_raises(self, tmp_path):
        empty_dir = tmp_path / "empty_shape"
        empty_dir.mkdir()
        registry = ShapeRegistry()
        with pytest.raises(ShapeLoadError, match="SHACL"):
            registry.load_shape("empty_shape", path=empty_dir)

    def test_load_with_explicit_path(self):
        """Explicit path should work even outside search dirs."""
        registry = ShapeRegistry()
        person_dir = Path(__file__).parent.parent / "src" / "ceds_jsonld" / "ontologies" / "person"
        shape = registry.load_shape("person_explicit", path=person_dir)
        assert shape.name == "person_explicit"
        assert shape.mapping_config["type"] == "Person"


# ===================================================================
# fetch_shape tests (with local HTTP server)
# ===================================================================

# Minimal valid SHACL
_MINI_SHACL = """\
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix ex: <http://example.org/> .

ex:TestShape a sh:NodeShape ;
    sh:targetClass ex:TestClass ;
    sh:closed true ;
    sh:property ex:nameProperty .

ex:nameProperty a sh:PropertyShape ;
    sh:path ex:name .
"""

_MINI_CONTEXT = json.dumps({
    "@context": {"@vocab": "http://example.org/", "ex": "http://example.org/"}
})

_MINI_MAPPING = yaml.dump({
    "shape": "TestShape",
    "context_url": "http://example.org/context.json",
    "base_uri": "ex:test/",
    "id_source": "ID",
    "type": "Test",
    "properties": {
        "name": {
            "type": "Name",
            "cardinality": "single",
            "fields": {"name": {"source": "Name", "target": "name"}},
        }
    },
})


class _FakeHandler(BaseHTTPRequestHandler):
    """Serve test shape files from in-memory data."""

    files: dict[str, bytes] = {}

    def do_GET(self):  # noqa: N802
        path = self.path.lstrip("/")
        if path in self.files:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(self.files[path])
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):  # noqa: A002
        pass  # Silence test output


@pytest.fixture()
def http_server():
    """Start a local HTTP server serving test shape files."""
    _FakeHandler.files = {
        "test_SHACL.ttl": _MINI_SHACL.encode(),
        "test_context.json": _MINI_CONTEXT.encode(),
        "test_mapping.yaml": _MINI_MAPPING.encode(),
    }
    server = HTTPServer(("127.0.0.1", 0), _FakeHandler)
    port = server.server_address[1]
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


class TestFetchShape:
    """Tests for URI-based shape fetching."""

    def test_fetch_and_load(self, http_server, tmp_path):
        registry = ShapeRegistry()
        base = http_server
        shape = registry.fetch_shape(
            "test",
            shacl_url=f"{base}/test_SHACL.ttl",
            context_url=f"{base}/test_context.json",
            mapping_url=f"{base}/test_mapping.yaml",
            cache_dir=tmp_path,
        )
        assert isinstance(shape, ShapeDefinition)
        assert shape.name == "test"
        assert shape.mapping_config["type"] == "Test"
        assert shape.shacl_path.exists()

    def test_cached_files_reused(self, http_server, tmp_path):
        registry = ShapeRegistry()
        base = http_server
        kwargs = {
            "shacl_url": f"{base}/test_SHACL.ttl",
            "context_url": f"{base}/test_context.json",
            "mapping_url": f"{base}/test_mapping.yaml",
            "cache_dir": tmp_path,
        }
        shape1 = registry.fetch_shape("test", **kwargs)
        # Modify the cache file to prove it's reused (not re-downloaded)
        cached_mapping = tmp_path / "test" / "test_mapping.yaml"
        original_content = cached_mapping.read_text(encoding="utf-8")
        assert cached_mapping.exists()
        # Second call should use cache
        shape2 = registry.fetch_shape("test", **kwargs)
        assert shape2.mapping_config["type"] == "Test"

    def test_force_redownload(self, http_server, tmp_path):
        registry = ShapeRegistry()
        base = http_server
        kwargs = {
            "shacl_url": f"{base}/test_SHACL.ttl",
            "context_url": f"{base}/test_context.json",
            "mapping_url": f"{base}/test_mapping.yaml",
            "cache_dir": tmp_path,
        }
        registry.fetch_shape("test", **kwargs)
        # Overwrite cache with garbage
        (tmp_path / "test" / "test_mapping.yaml").write_text("corrupted!")
        # Force should re-download fresh
        shape = registry.fetch_shape("test", force=True, **kwargs)
        assert shape.mapping_config["type"] == "Test"

    def test_missing_mapping_url_requires_cached(self, http_server, tmp_path):
        registry = ShapeRegistry()
        base = http_server
        # No mapping_url and no cached mapping → error
        with pytest.raises(ShapeLoadError, match="mapping"):
            registry.fetch_shape(
                "test",
                shacl_url=f"{base}/test_SHACL.ttl",
                context_url=f"{base}/test_context.json",
                cache_dir=tmp_path,
            )

    def test_missing_mapping_url_with_cached_mapping(self, http_server, tmp_path):
        registry = ShapeRegistry()
        base = http_server
        # First fetch with mapping URL to populate cache
        registry.fetch_shape(
            "test",
            shacl_url=f"{base}/test_SHACL.ttl",
            context_url=f"{base}/test_context.json",
            mapping_url=f"{base}/test_mapping.yaml",
            cache_dir=tmp_path,
        )
        # Second fetch without mapping URL should work from cache
        shape = registry.fetch_shape(
            "test",
            shacl_url=f"{base}/test_SHACL.ttl",
            context_url=f"{base}/test_context.json",
            cache_dir=tmp_path,
        )
        assert shape.mapping_config["type"] == "Test"

    def test_bad_url_raises(self, tmp_path):
        registry = ShapeRegistry()
        with pytest.raises(ShapeLoadError, match="Failed to download"):
            registry.fetch_shape(
                "test",
                shacl_url="http://127.0.0.1:1/nonexistent.ttl",
                context_url="http://127.0.0.1:1/nonexistent.json",
                cache_dir=tmp_path,
            )
