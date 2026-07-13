from __future__ import annotations

from pathlib import Path

import pytest

from rm_validate.config import Config, ConfigError
from rm_validate.profiles import resolve_profile


def test_profile_extends_chain() -> None:
    static = resolve_profile("static")
    app = resolve_profile("app")
    platform = resolve_profile("platform")
    assert static["has_database"] is False
    assert app["has_database"] is True and app["has_auth"] is True
    assert app["multi_tenant"] is False
    assert platform["multi_tenant"] is True and platform["exposes_mcp"] is True


def test_unknown_profile() -> None:
    with pytest.raises(ValueError):
        resolve_profile("nope")


def _load(tmp_path: Path, text: str) -> Config:
    p = tmp_path / "rm-policy.yaml"
    p.write_text(text, encoding="utf-8")
    return Config.load(p)


def test_overrides_win_over_preset(tmp_path: Path) -> None:
    cfg = _load(tmp_path, "extends: app\ncapabilities:\n  has_auth: false\n")
    assert cfg.capabilities["has_database"] is True
    assert cfg.capabilities["has_auth"] is False


def test_unknown_capability_is_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        _load(tmp_path, "extends: static\ncapabilities:\n  has_blockchain: true\n")


def test_unknown_fitness_function_is_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        _load(tmp_path, "extends: static\nfitness_functions:\n  make_it_fast: true\n")


def test_missing_layering_reported(tmp_path: Path) -> None:
    cfg = _load(
        tmp_path,
        "extends: static\nfitness_functions:\n  engines_must_be_pure: true\n",
    )
    missing = cfg.missing_layering()
    assert ("engines_must_be_pure", "engines") in missing


def test_layering_present_no_missing(tmp_path: Path) -> None:
    cfg = _load(
        tmp_path,
        "extends: static\n"
        "fitness_functions:\n  engines_must_be_pure: true\n"
        "layering_patterns:\n  engines: ['**/engines/**']\n",
    )
    assert cfg.missing_layering() == []


def test_invalid_mode(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        _load(tmp_path, "extends: static\nenforcement:\n  mode: loud\n")
