# orjson Reference — ceds-jsonld

**Version:** 3.11.7
**Docs:** https://github.com/ijl/orjson
**Last updated:** 2025-01-20

## Installation

```bash
pip install orjson
```

## Role in This Project

orjson is the **primary JSON serializer** for all JSON-LD output. It is ~10x faster than stdlib `json` for serialization and ~2x faster for deserialization. It outputs `bytes` (not `str`), which is correct for writing to files or sending over the network.

## API Reference

### dumps()

```python
def dumps(
    __obj: Any,
    default: Optional[Callable[[Any], Any]] = ...,
    option: Optional[int] = ...,
) -> bytes:
```

Serializes Python objects to JSON as UTF-8 `bytes`.

**Natively supported types:** `str`, `dict`, `list`, `tuple`, `int`, `float`, `bool`, `None`, `dataclasses.dataclass`, `typing.TypedDict`, `datetime.datetime`, `datetime.date`, `datetime.time`, `uuid.UUID`, `numpy.ndarray`, `orjson.Fragment`

**Returns:** `bytes` (not `str` — this is the key difference from `json.dumps`)

**Raises:** `orjson.JSONEncodeError` (subclass of `TypeError`) on unsupported types

### loads()

```python
def loads(__obj: Union[bytes, bytearray, memoryview, str]) -> Any:
```

Deserializes JSON to Python objects. Accepts `bytes`, `bytearray`, `memoryview`, or `str`.

**Returns:** `dict`, `list`, `int`, `float`, `str`, `bool`, or `None`

**Raises:** `orjson.JSONDecodeError` (subclass of `json.JSONDecodeError` and `ValueError`)

### Fragment

```python
orjson.Fragment(b'{"already": "serialized"}')
```

Include pre-serialized JSON blobs without re-parsing. Useful for caching `@context` as a serialized blob.

### Option Flags

Combine with bitwise OR: `option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS`

| Option | Description |
|--------|-------------|
| `OPT_INDENT_2` | Pretty-print with 2-space indent (equiv. to `indent=2`) |
| `OPT_SORT_KEYS` | Sort dict keys (equiv. to `sort_keys=True`) — has perf penalty |
| `OPT_APPEND_NEWLINE` | Append `\n` to output |
| `OPT_NAIVE_UTC` | Serialize naive datetimes as UTC |
| `OPT_UTC_Z` | Use `Z` instead of `+00:00` for UTC |
| `OPT_OMIT_MICROSECONDS` | Drop microseconds from datetimes |
| `OPT_NON_STR_KEYS` | Allow non-string dict keys |
| `OPT_SERIALIZE_NUMPY` | Serialize numpy arrays natively |
| `OPT_STRICT_INTEGER` | Enforce 53-bit integer limit |
| `OPT_PASSTHROUGH_DATACLASS` | Send dataclasses to `default` |
| `OPT_PASSTHROUGH_DATETIME` | Send datetimes to `default` |
| `OPT_PASSTHROUGH_SUBCLASS` | Send subclasses of builtins to `default` |

## Usage Patterns for This Project

### Standard Serialization (Production)

```python
import orjson

def serialize_jsonld(doc: dict) -> bytes:
    """Serialize a JSON-LD document to compact JSON bytes."""
    return orjson.dumps(doc)
```

### Pretty-Print (Development/Debugging)

```python
def serialize_jsonld_pretty(doc: dict) -> bytes:
    """Serialize with indentation for human readability."""
    return orjson.dumps(doc, option=orjson.OPT_INDENT_2)
```

### Safe Import Pattern (Fallback)

```python
try:
    import orjson
    def dumps(obj: Any) -> bytes:
        return orjson.dumps(obj, option=orjson.OPT_INDENT_2)
    def loads(data: bytes | str) -> Any:
        return orjson.loads(data)
except ImportError:
    import json
    def dumps(obj: Any) -> bytes:
        return json.dumps(obj, indent=2).encode("utf-8")
    def loads(data: bytes | str) -> Any:
        return json.loads(data)
```

### Writing to File

```python
import orjson
from pathlib import Path

path = Path("output/person_001.json")
path.write_bytes(orjson.dumps(doc, option=orjson.OPT_INDENT_2))
```

### Custom Type Handling

```python
def default(obj):
    """Handle types orjson doesn't natively serialize."""
    if isinstance(obj, set):
        return sorted(obj)  # Convert sets to sorted lists
    if isinstance(obj, bytes):
        return obj.decode("utf-8")
    raise TypeError(f"Type is not JSON serializable: {type(obj)}")

orjson.dumps(data, default=default)
```

## Gotchas & Notes

- **Returns `bytes`, not `str`.** Use `.decode("utf-8")` if you need a string, or use `Path.write_bytes()` for files.
- **NaN/Infinity serialize as `null`** (unlike stdlib which produces invalid JSON).
- **Strict UTF-8** — raises on surrogates that stdlib silently accepts.
- `OPT_SORT_KEYS` has a measurable performance penalty — only use for tests or deterministic output.
- No `object_hook` on deserialization — use a data validation library for structured parsing.
- No streaming/incremental parsing — load/dump entire documents at once.
- Only indent=2 is supported, no other indent levels.

## Performance Notes

| Benchmark | orjson | json stdlib | Speedup |
|-----------|--------|-------------|---------|
| github.json serialize | 0.01ms | 0.13ms | 13.6x |
| twitter.json serialize | 0.1ms | 1.3ms | 11.1x |
| twitter.json deserialize | 0.5ms | 2.2ms | 4.2x |
| Pretty-print (github.json) | 0.02ms | 0.54ms | 34x |

orjson is consistently 10-34x faster for serialization and 2-4x faster for deserialization.
