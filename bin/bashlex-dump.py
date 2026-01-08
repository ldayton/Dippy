#!/usr/bin/env python3
"""
Debug helper for inspecting bashlex AST.

Usage:
    python bin/bashlex-dump.py 'command to parse'

This helps understand how bashlex parses commands, which is useful
when adding new patterns to Dippy.
"""

import sys

try:
    import bashlex
except ImportError:
    print("Error: bashlex not installed. Run: pip install bashlex")
    sys.exit(1)


def dump_node(node, indent=0):
    """Recursively dump a bashlex AST node."""
    prefix = "  " * indent
    
    if hasattr(node, 'kind'):
        print(f"{prefix}kind: {node.kind}")
    
    if hasattr(node, 'word'):
        print(f"{prefix}word: {node.word!r}")
    
    if hasattr(node, 'type'):
        print(f"{prefix}type: {node.type}")
    
    if hasattr(node, 'pos'):
        print(f"{prefix}pos: {node.pos}")
    
    if hasattr(node, 'parts'):
        print(f"{prefix}parts:")
        for part in node.parts:
            dump_node(part, indent + 1)
    
    if hasattr(node, 'list'):
        print(f"{prefix}list:")
        for item in node.list:
            dump_node(item, indent + 1)


def main():
    if len(sys.argv) < 2:
        print("Usage: bashlex-dump.py 'command'")
        print("Example: bashlex-dump.py 'git status | grep foo'")
        sys.exit(1)
    
    command = sys.argv[1]
    print(f"Parsing: {command!r}")
    print("-" * 40)
    
    try:
        parts = bashlex.parse(command)
        for i, part in enumerate(parts):
            print(f"Part {i}:")
            dump_node(part, 1)
            print()
    except bashlex.errors.ParsingError as e:
        print(f"Parse error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
