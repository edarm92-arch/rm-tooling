"""Glob matching with ``**`` support against repo-relative posix paths.

``PurePath.match`` does not treat ``**`` as spanning directory boundaries, so
patterns like ``app/**/db.py`` would not match. We translate the (small) glob
subset the policy files use into an anchored regex. Shared by inference and by
every check that resolves declared globs (file limits, layering).
"""

from __future__ import annotations

import re
from functools import lru_cache


@lru_cache(maxsize=512)
def glob_to_regex(glob: str) -> str:
    """Translate a glob (supporting ``**``, ``*``, ``?``) to an anchored regex."""
    i = 0
    out = ["^"]
    while i < len(glob):
        if glob[i:i + 3] == "**/":
            out.append("(?:.*/)?")
            i += 3
        elif glob[i:i + 2] == "**":
            out.append(".*")
            i += 2
        else:
            c = glob[i]
            if c == "*":
                out.append("[^/]*")
            elif c == "?":
                out.append("[^/]")
            elif c in ".()[]{}+^$|\\":
                out.append("\\" + c)
            else:
                out.append(c)
            i += 1
    out.append("$")
    return "".join(out)


def match_glob(rel_posix: str, glob: str) -> bool:
    """True if ``rel_posix`` (a repo-relative posix path) matches ``glob``."""
    return re.match(glob_to_regex(glob), rel_posix) is not None


def match_any(rel_posix: str, globs: list[str]) -> bool:
    """True if ``rel_posix`` matches any glob in ``globs``."""
    return any(match_glob(rel_posix, g) for g in globs)
