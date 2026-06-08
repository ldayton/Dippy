"""Path resolution for command-argument inspection.

Resolves path-like command tokens to filesystem paths so handlers can
inspect the referenced file (e.g. static-analyze a script before approving).
"""

from __future__ import annotations

import os
from pathlib import Path


def resolve_arg_path(token: str, cwd: Path) -> Path:
    """Resolve a command-line path token to a filesystem path for inspection.

    Expands ``~`` and ``~user``, then anchors relative paths to ``cwd`` —
    matching the path normalization described in the security model. Variables
    (``$HOME``) are intentionally left literal: the shell expands those after
    approval, so we never guess their value from the hook's own environment.

    Never raises: an unresolvable token (e.g. an unknown user) is left literal,
    so the resulting path simply won't exist and the caller degrades to asking
    for confirmation.
    """
    path = Path(os.path.expanduser(token))
    if not path.is_absolute():
        path = cwd / path
    return path.resolve()
