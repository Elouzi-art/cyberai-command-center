"""R3/R4/R5 : les contrats JSON sont valides et les exemples conformes."""

import json
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[2] / "schemas"


def load(path: Path) -> dict:  # type: ignore[type-arg]
    return json.loads(path.read_text())  # type: ignore[no-any-return]


@pytest.mark.parametrize("schema", sorted(ROOT.glob("*.v1.json")))
def test_schema_is_valid(schema: Path) -> None:
    jsonschema.Draft202012Validator.check_schema(load(schema))


@pytest.mark.parametrize("example", sorted((ROOT / "examples").glob("*.valid.json")))
def test_valid_examples(example: Path) -> None:
    name = example.name.replace(".valid.json", ".v1.json")
    jsonschema.validate(load(example), load(ROOT / name))


def test_unavailable_metric_with_value_is_invalid() -> None:
    schema = load(ROOT / "provider_metric.v1.json")
    bad = load(ROOT / "examples" / "provider_metric.invalid.json")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)
