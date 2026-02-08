"""Tests for serializer module (orjson with stdlib fallback)."""

from __future__ import annotations

import pytest

from ceds_jsonld import serializer


class TestDumpsLoads:
    """Test serialization and deserialization."""

    def test_round_trip_dict(self):
        obj = {"@type": "Person", "name": "Jane"}
        data = serializer.dumps(obj)
        assert isinstance(data, bytes)
        result = serializer.loads(data)
        assert result == obj

    def test_round_trip_list(self):
        obj = [{"a": 1}, {"b": 2}]
        data = serializer.dumps(obj)
        result = serializer.loads(data)
        assert result == obj

    def test_pretty_output(self):
        obj = {"key": "value"}
        data = serializer.dumps(obj, pretty=True)
        text = data.decode("utf-8")
        assert "\n" in text  # Pretty-printed should have newlines

    def test_compact_output(self):
        obj = {"key": "value"}
        data = serializer.dumps(obj, pretty=False)
        text = data.decode("utf-8")
        # Compact should not have leading newlines (may have space in stdlib json)
        assert text.startswith("{")

    def test_unicode_preserved(self):
        obj = {"name": "Ñoño Ü"}
        data = serializer.dumps(obj)
        result = serializer.loads(data)
        assert result["name"] == "Ñoño Ü"

    def test_loads_accepts_string(self):
        result = serializer.loads('{"a": 1}')
        assert result == {"a": 1}

    def test_loads_accepts_bytes(self):
        result = serializer.loads(b'{"a": 1}')
        assert result == {"a": 1}


class TestFileIO:
    """Test file read/write helpers."""

    def test_write_and_read_json(self, tmp_path):
        path = tmp_path / "test.json"
        obj = {"@type": "Person", "@id": "cepi:person/123"}
        serializer.write_json(obj, path)
        assert path.exists()
        result = serializer.read_json(path)
        assert result == obj

    def test_write_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "sub" / "dir" / "test.json"
        serializer.write_json({"key": "value"}, path)
        assert path.exists()

    def test_write_returns_byte_count(self, tmp_path):
        path = tmp_path / "test.json"
        n = serializer.write_json({"a": 1}, path, pretty=False)
        assert n > 0
        assert n == path.stat().st_size

    def test_read_nonexistent_raises(self, tmp_path):
        from ceds_jsonld.exceptions import SerializationError

        with pytest.raises(SerializationError):
            serializer.read_json(tmp_path / "nonexistent.json")


class TestBackend:
    """Test backend detection."""

    def test_backend_is_string(self):
        assert serializer.get_backend() in ("orjson", "json")
