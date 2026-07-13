"""Core value types shared by every check.

A check receives a :class:`CheckContext` and returns a list of
:class:`Finding`. Findings carry enough structure for ``reporting.py`` to
render ``file · rule · value vs. limit · severity`` and to compute the exit
code. Nothing here knows anything about a specific project.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # avoid import cycles; these are only needed for typing
    from rm_validate.analyzers.base import ImportAnalyzer
    from rm_validate.config import Config
    from rm_validate.inference import InferenceResult


class Severity(StrEnum):
    """Severity of a single finding.

    ``ERROR`` blocks a merge only when ``enforcement.mode == blocking``.
    ``WARNING`` never blocks. Config-integrity findings set
    :attr:`Finding.config_integrity` and block regardless of mode.
    """

    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class Finding:
    """One reported observation from a check."""

    check: str
    severity: Severity
    message: str
    rule: str = ""
    value: str = ""
    limit: str = ""
    path: str | None = None
    # Integrity findings (missing ADR, missing layering_patterns, capability
    # under-declaration) fail even in ``warning`` mode: the repo asked for a
    # check but did not supply the data to run it, or actively misdeclared.
    config_integrity: bool = False

    def key(self) -> str:
        """Stable identity used by the baseline/ratchet (order-independent)."""
        return f"{self.check}|{self.path or ''}|{self.rule}|{self.value}"


@dataclass
class CheckContext:
    """Everything a check needs, resolved once per ``check`` run."""

    repo: Path
    config: Config
    inferred: InferenceResult
    # Cached first-party python files (kept for inference/back-compat).
    py_files: list[Path] = field(default_factory=list)
    # All in-scope repo files (minus excludes) — the resolution universe.
    all_files: list[Path] = field(default_factory=list)
    # Cache of per-analyzer prepared resolution indexes and rel-path list.
    _indices: dict[Any, Any] = field(default_factory=dict)
    _all_rel: list[str] | None = None

    def all_rel(self) -> list[str]:
        if self._all_rel is None:
            self._all_rel = [p.relative_to(self.repo).as_posix() for p in self.all_files]
        return self._all_rel

    def index_for(self, analyzer: ImportAnalyzer) -> Any:
        """Prepare (and cache) an analyzer's resolution index over all files."""
        if analyzer not in self._indices:
            self._indices[analyzer] = analyzer.prepare(self.all_rel())
        return self._indices[analyzer]
