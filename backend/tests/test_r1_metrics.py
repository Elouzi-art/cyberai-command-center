"""R1 : aucune métrique inventée."""

import pytest
from pydantic import ValidationError

from app.providers import MetricValue


def test_unavailable_has_null_value() -> None:
    m = MetricValue.unavailable()
    assert m.model_dump() == {"value": None, "available": False}


def test_unavailable_with_value_rejected() -> None:
    with pytest.raises(ValidationError):
        MetricValue(value=100, available=False)


def test_available_without_value_rejected() -> None:
    with pytest.raises(ValidationError):
        MetricValue(value=None, available=True)
