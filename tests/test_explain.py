from __future__ import annotations

from rm_validate.commands.explain import explain


def test_explain_layering_check_lists_required_keys() -> None:
    text, code = explain("engines_must_be_pure")
    assert code == 0
    assert "fitness_function: engines_must_be_pure" in text
    assert "requires layering_patterns" in text
    assert "engines" in text


def test_explain_circular_is_layer_agnostic() -> None:
    text, code = explain("no_circular_dependencies")
    assert code == 0
    assert "layer-agnostic" in text or "none" in text


def test_explain_capability_check() -> None:
    text, code = explain("db_migrations_present")
    assert code == 0
    assert "has_database" in text


def test_explain_unknown_check() -> None:
    text, code = explain("does_not_exist")
    assert code == 1
    assert "unknown check" in text
