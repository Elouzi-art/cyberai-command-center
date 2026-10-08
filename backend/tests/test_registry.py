from pathlib import Path

import pytest

from app.providers.registry import ConfigError, load_providers


def _cfg(tmp_path: Path, body: str) -> str:
    p = tmp_path / "config.yaml"
    p.write_text(body)
    return str(p)


def test_missing_key_for_enabled_cloud_provider_fails(tmp_path: Path) -> None:
    path = _cfg(
        tmp_path,
        """providers:
  - {id: c, type: openai_compatible, model: m, base_url: "https://api.example.com/v1",
      api_key_env: KEY}
""",
    )
    with pytest.raises(ConfigError):
        load_providers(path, {})


def test_disabled_provider_is_not_loaded_and_needs_no_key(tmp_path: Path) -> None:
    path = _cfg(
        tmp_path,
        """providers:
  - {id: c, type: openai_compatible, model: m, enabled: false}
  - {id: o, type: ollama, model: llama}
""",
    )
    assert list(load_providers(path, {})) == ["o"]


def test_non_http_url_rejected(tmp_path: Path) -> None:
    path = _cfg(
        tmp_path,
        "providers:\n  - {id: o, type: ollama, model: m, base_url: 'file:///etc/passwd'}\n",
    )
    with pytest.raises(ConfigError):
        load_providers(path, {})
