#!/usr/bin/env python3
"""Check for banned Python constructions in Dippy source.

Banned constructions:

    Construction          Reason                            Use instead
    --------------------  --------------------------------  --------------------------
    import shlex          Dippy is the parsing authority    parable for parsing
    from shlex import     via Parable, not stdlib           custom quote/join if needed
"""

import ast
import os
import sys

BANNED_MODULES = frozenset({"shlex"})


def find_python_files(directory):
    """Find all .py files recursively, excluding vendor directory."""
    result = []
    for root, dirs, files in os.walk(directory):
        # Skip vendor directory
        if "vendor" in dirs:
            dirs.remove("vendor")
        for f in files:
            if f.endswith(".py"):
                result.append(os.path.join(root, f))
    result.sort()
    return result


def check_file(filepath):
    with open(filepath) as f:
        source = f.read()

    tree = ast.parse(source, filepath)
    errors = []

    for node in ast.walk(tree):
        lineno = getattr(node, "lineno", 0)

        # import shlex
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in BANNED_MODULES:
                    errors.append(
                        (lineno, f"import {alias.name}: banned, use parable for parsing")
                    )

        # from shlex import ...
        if isinstance(node, ast.ImportFrom):
            if node.module in BANNED_MODULES:
                errors.append(
                    (lineno, f"from {node.module} import: banned, use parable for parsing")
                )

    return errors


def main():
    src_dir = "src"
    if len(sys.argv) > 1:
        src_dir = sys.argv[1]

    if not os.path.isdir(src_dir):
        print(f"Directory not found: {src_dir}")
        sys.exit(1)

    files = find_python_files(src_dir)
    if not files:
        print(f"No Python files found in: {src_dir}")
        sys.exit(1)

    all_errors = []
    for filepath in files:
        try:
            errors = check_file(filepath)
            for lineno, description in errors:
                all_errors.append((filepath, lineno, description))
        except SyntaxError as e:
            print(f"Syntax error in {filepath}: {e}")
            sys.exit(1)

    if not all_errors:
        sys.exit(0)

    print(f"Found {len(all_errors)} banned construction(s):")
    for filepath, lineno, description in sorted(all_errors):
        print(f"  {filepath}:{lineno}: {description}")
    sys.exit(1)


if __name__ == "__main__":
    main()
