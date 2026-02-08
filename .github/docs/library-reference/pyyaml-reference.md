# PyYAML Reference — ceds-jsonld

**Version:** 6.0.2
**Docs:** https://pyyaml.org/wiki/PyYAMLDocumentation
**Last updated:** 2025-01-20

## Installation

```bash
pip install pyyaml
```

## Role in This Project

PyYAML is used to load mapping configuration files (`_mapping.yaml`) that define how source data fields map to JSON-LD properties. These configs drive the `FieldMapper` and `JSONLDBuilder` classes.

## API Reference

### Loading (Deserialization)

```python
import yaml

# PREFERRED: safe_load — only standard YAML tags, no arbitrary Python objects
data = yaml.safe_load(stream)               # Single document
data_list = list(yaml.safe_load_all(stream)) # Multiple documents

# AVOID: load — can execute arbitrary Python code
data = yaml.load(stream, Loader=yaml.SafeLoader)  # Equivalent to safe_load
```

**`stream`** can be: `str`, `bytes`, or an open file object.

**Returns:** Python objects — `dict`, `list`, `str`, `int`, `float`, `bool`, `None`, `datetime.datetime`

### Dumping (Serialization)

```python
# PREFERRED: safe_dump — only standard YAML tags
output = yaml.safe_dump(data)                        # Returns str
output = yaml.safe_dump(data, default_flow_style=False)  # Block style (readable)

# To file
with open("output.yaml", "w") as f:
    yaml.safe_dump(data, f, default_flow_style=False)

# Multiple documents
yaml.safe_dump_all([doc1, doc2, doc3], stream)
```

### Key Parameters for dump/safe_dump

| Parameter | Default | Description |
|-----------|---------|-------------|
| `default_flow_style` | `None` | `False` for block style, `True` for flow style |
| `default_style` | `None` | Quote style for scalars: `None`, `'`, `"`, `\|`, `>` |
| `indent` | `None` | Number of spaces for indentation |
| `width` | `None` | Line width for wrapping |
| `allow_unicode` | `None` | Allow unicode characters unescaped |
| `encoding` | `None` | Output encoding (Python 3: None=str, 'utf-8'=bytes) |
| `explicit_start` | `None` | Include `---` document start marker |
| `sort_keys` | `True` | Sort dict keys alphabetically |

### YAML Tag Mapping

| YAML Tag | Python Type |
|----------|-------------|
| `!!null` | `None` |
| `!!bool` | `bool` |
| `!!int` | `int` |
| `!!float` | `float` |
| `!!str` | `str` |
| `!!seq` | `list` |
| `!!map` | `dict` |
| `!!timestamp` | `datetime.datetime` |
| `!!binary` | `bytes` |

### Error Handling

```python
try:
    data = yaml.safe_load(stream)
except yaml.YAMLError as exc:
    if hasattr(exc, "problem_mark"):
        mark = exc.problem_mark
        print(f"Error at line {mark.line + 1}, column {mark.column + 1}")
    print(f"YAML error: {exc}")
```

## Usage Patterns for This Project

### Loading a Mapping Config

```python
from pathlib import Path
import yaml

def load_mapping_config(shape_dir: Path) -> dict:
    """Load the mapping YAML for a shape."""
    mapping_path = shape_dir / f"{shape_dir.name}_mapping.yaml"
    if not mapping_path.exists():
        raise FileNotFoundError(f"Mapping config not found: {mapping_path}")

    with mapping_path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    validate_mapping_config(config)
    return config
```

### Validating a Mapping Config

```python
REQUIRED_TOP_KEYS = {"shape", "type", "properties"}
REQUIRED_PROP_KEYS = {"type", "cardinality", "fields"}

def validate_mapping_config(config: dict) -> None:
    """Validate that a mapping config has all required fields."""
    missing = REQUIRED_TOP_KEYS - set(config.keys())
    if missing:
        raise ValueError(f"Mapping config missing keys: {missing}")

    for prop_name, prop_def in config.get("properties", {}).items():
        missing_prop = REQUIRED_PROP_KEYS - set(prop_def.keys())
        if missing_prop:
            raise ValueError(
                f"Property '{prop_name}' missing keys: {missing_prop}"
            )
```

### Writing Test Fixtures

```python
import yaml

def save_test_mapping(config: dict, path: Path) -> None:
    """Save a mapping config for testing."""
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(
            config,
            f,
            default_flow_style=False,
            sort_keys=False,  # Preserve insertion order
            allow_unicode=True,
        )
```

## Gotchas & Notes

- **Always use `safe_load`** — `yaml.load()` without `Loader=SafeLoader` can execute arbitrary code.
- **`sort_keys=True` is the default** for `dump`/`safe_dump`. Use `sort_keys=False` to preserve dict order.
- **Implicit type casting:** YAML auto-converts `yes`/`no`/`on`/`off` to booleans. Quote strings that look like booleans: `"yes"`.
- **The Norway problem:** `NO` (country code) becomes `False`. Quote it: `"NO"`.
- **Tabs are not allowed** for indentation in YAML — only spaces.
- **Multiline strings:** Use `|` for literal blocks (preserves newlines) or `>` for folded blocks (joins lines).
- **Empty values:** `key:` (no value) → `None` in Python. Use `key: ""` for empty string.

## Performance Notes

- PyYAML is not performance-critical in this project — configs are loaded once at startup.
- For extremely large YAML files, consider `yaml.CSafeLoader` (requires LibYAML C library).
- Our mapping YAMLs are <100 lines — parsing is <1ms.
