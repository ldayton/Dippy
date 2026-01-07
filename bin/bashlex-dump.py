#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.14"
# dependencies = [
#   "bashlex>=0.18",
# ]
# ///
"""Debug script to inspect bashlex AST structure."""

import sys
import bashlex


def show(node, indent=0):
    attrs = {k: v for k, v in vars(node).items() if not k.startswith("_")}
    print(" " * indent + f"{node.kind}: {attrs}")
    if hasattr(node, "parts"):
        for p in node.parts:
            show(p, indent + 2)
    if hasattr(node, "list"):
        for p in node.list:
            show(p, indent + 2)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "echo foo 2>/dev/null"
    print(f"Parsing: {cmd}\n")
    for p in bashlex.parse(cmd):
        show(p)


if __name__ == "__main__":
    main()
