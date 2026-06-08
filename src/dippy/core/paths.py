"""Path resolution for command-argument inspection.

Resolves path-like command tokens to filesystem paths so handlers can
inspect the referenced file (e.g. static-analyze a script before approving).
"""

from __future__ import annotations

import os
from pathlib import Path


def resolve_arg_path(token: str, cwd: Path) -> Path:
    """Resolve a command-line path token to a filesystem path for inspection.

    Expands ``~``, ``~user``, and ``$VAR``/``${VAR}``, then anchors relative
    paths to ``cwd``. Never raises: an unresolvable token (unknown user,
    undefined variable) is left literal, so the resulting path simply won't
    exist and the caller degrades to asking for confirmation.
    """
    expanded = os.path.expandvars(os.path.expanduser(token))
    path = Path(expanded)
    if not path.is_absolute():
        path = cwd / path
    return path.resolve()
