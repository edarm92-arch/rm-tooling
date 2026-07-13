"""Port: the ``ImportAnalyzer`` interface every language adapter implements.

An analyzer turns a source file into a list of :class:`RawImport` and resolves
each import to a repo-relative file (best effort). ``supports_graph`` says
whether the adapter is precise enough to back cycle detection — regex adapters
set it False on purpose (containment is safe with regex; a full graph is not).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar


@dataclass(frozen=True)
class RawImport:
    """One import as seen in a source file, before resolution to a file.

    * ``module`` — dotted name (Python) or specifier path (TS/JS).
    * ``level`` — Python relative-import level (0 = absolute).
    * ``names`` — names pulled by a ``from X import a, b`` (help resolve to a file).
    * ``relative`` — TS/JS specifier that starts with ``.`` (path-resolvable).
    """

    module: str
    level: int = 0
    names: tuple[str, ...] = field(default_factory=tuple)
    relative: bool = False


class ImportAnalyzer(ABC):
    """Adapter contract. Extensions in ``LANGUAGES`` include the leading dot."""

    LANGUAGES: ClassVar[frozenset[str]]
    supports_graph: ClassVar[bool]

    @property
    def name(self) -> str:
        return type(self).__name__

    @abstractmethod
    def extract_imports(self, repo: Path, rel: str) -> list[RawImport]:
        """Return the imports found in ``repo/rel``."""

    @abstractmethod
    def prepare(self, rel_files: list[str]) -> Any:
        """Build whatever index resolution needs from the repo file list."""

    @abstractmethod
    def resolve(self, importer_rel: str, imp: RawImport, index: Any) -> str | None:
        """Resolve ``imp`` (seen in ``importer_rel``) to a repo file, or None."""
