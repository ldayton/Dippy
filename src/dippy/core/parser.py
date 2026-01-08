"""
Bash command parsing utilities using bashlex.

Provides safe tokenization and AST inspection for analyzing shell commands.
"""

import shlex
from typing import Optional

try:
    import bashlex
    BASHLEX_AVAILABLE = True
except ImportError:
    BASHLEX_AVAILABLE = False


def tokenize(command: str) -> list[str]:
    """
    Tokenize a bash command into a list of tokens.
    
    Falls back to shlex if bashlex fails (e.g., for complex constructs).
    """
    if not command or not command.strip():
        return []
    
    # Try bashlex first for accurate bash parsing
    if BASHLEX_AVAILABLE:
        try:
            parts = bashlex.parse(command)
            tokens = extract_tokens(parts)
            if tokens:
                return tokens
        except (bashlex.errors.ParsingError, Exception):
            pass
    
    # Fallback to shlex
    try:
        return shlex.split(command)
    except ValueError:
        # Last resort: simple whitespace split
        return command.split()


def extract_tokens(parts: list) -> list[str]:
    """Extract word tokens from bashlex AST nodes."""
    tokens = []
    
    for part in parts:
        tokens.extend(_extract_from_node(part))
    
    return tokens


def _extract_from_node(node) -> list[str]:
    """Recursively extract tokens from a bashlex AST node."""
    tokens = []
    
    if node.kind == 'word':
        tokens.append(node.word)
    elif node.kind == 'command':
        for part in node.parts:
            tokens.extend(_extract_from_node(part))
    elif node.kind == 'pipeline':
        for part in node.parts:
            tokens.extend(_extract_from_node(part))
    elif node.kind == 'list':
        for part in node.parts:
            tokens.extend(_extract_from_node(part))
    elif node.kind == 'compound':
        for part in node.list:
            tokens.extend(_extract_from_node(part))
    elif hasattr(node, 'parts'):
        for part in node.parts:
            tokens.extend(_extract_from_node(part))
    
    return tokens


def get_base_command(command: str) -> Optional[str]:
    """
    Extract the base command from a shell command string.
    
    Handles:
    - Simple commands: "ls -la" -> "ls"
    - Env vars: "FOO=bar cmd" -> "cmd"
    - Subshells: Extracts first command
    
    Returns None if command cannot be parsed.
    """
    tokens = tokenize(command)
    if not tokens:
        return None
    
    # Skip environment variable assignments
    for token in tokens:
        if '=' not in token or token.startswith('-'):
            return token
    
    return tokens[0] if tokens else None


def has_output_redirect(command: str) -> bool:
    """Check if command contains output redirection (>, >>)."""
    if not BASHLEX_AVAILABLE:
        # Simple fallback check
        return '>' in command
    
    try:
        parts = bashlex.parse(command)
        return _check_redirect(parts)
    except (bashlex.errors.ParsingError, Exception):
        # Conservative: assume redirect if we can't parse
        return '>' in command


def _check_redirect(nodes: list, source: str = "") -> bool:
    """Recursively check for output redirects in AST.

    Flags redirects to files, but allows:
    - 2>/dev/null (discard stderr)
    - 2>&1 (merge stderr to stdout)
    """
    for node in nodes:
        if node.kind == 'redirect':
            if node.type in ('>', '>>'):
                fd = getattr(node, 'input', None)
                # Get the redirect target
                output = getattr(node, 'output', None)
                target = ""
                if output and hasattr(output, 'word'):
                    target = output.word

                # Allow safe stderr redirects
                if fd == 2:
                    if target in ('/dev/null',):
                        continue  # Safe: discard stderr
                    # 2>&1 is handled differently by bashlex, but check anyway
                    if target.startswith('&'):
                        continue  # Safe: merge to another fd

                # Any other redirect to a file needs confirmation
                return True
        if hasattr(node, 'parts'):
            if _check_redirect(node.parts, source):
                return True
        if hasattr(node, 'list'):
            if _check_redirect(node.list, source):
                return True
    return False


def is_piped(command: str) -> bool:
    """Check if command is part of a pipeline."""
    if not BASHLEX_AVAILABLE:
        return '|' in command

    try:
        parts = bashlex.parse(command)
        for part in parts:
            if part.kind == 'pipeline' and len(part.parts) > 1:
                return True
        return False
    except (bashlex.errors.ParsingError, Exception):
        return '|' in command


def has_command_list(command: str) -> bool:
    """Check if command has && or || operators (command lists)."""
    if not BASHLEX_AVAILABLE:
        return '&&' in command or '||' in command

    try:
        parts = bashlex.parse(command)
        return _has_list_operator(parts)
    except (bashlex.errors.ParsingError, Exception):
        return '&&' in command or '||' in command


def _has_list_operator(nodes: list) -> bool:
    """Recursively check for list operators in AST."""
    for node in nodes:
        if node.kind == 'list':
            return True
        if hasattr(node, 'parts'):
            if _has_list_operator(node.parts):
                return True
        if hasattr(node, 'list'):
            if _has_list_operator(node.list):
                return True
    return False


def split_command_list(command: str) -> list[str]:
    """
    Split a command list on && and || into individual commands.

    "ls && rm foo || echo bar" -> ["ls", "rm foo", "echo bar"]
    """
    if not BASHLEX_AVAILABLE:
        # Simple fallback - split on && and ||
        import re
        parts = re.split(r'\s*(?:&&|\|\|)\s*', command)
        return [p.strip() for p in parts if p.strip()]

    try:
        parts = bashlex.parse(command)
        commands = []
        _extract_list_commands(parts, command, commands)
        return commands if commands else [command]
    except (bashlex.errors.ParsingError, Exception):
        import re
        parts = re.split(r'\s*(?:&&|\|\|)\s*', command)
        return [p.strip() for p in parts if p.strip()]


def _extract_list_commands(nodes: list, source: str, commands: list):
    """Extract individual commands from a command list."""
    for node in nodes:
        if node.kind == 'list':
            for part in node.parts:
                _extract_list_commands([part], source, commands)
        elif node.kind == 'pipeline':
            # A pipeline as part of a list - get the whole pipeline
            cmd_text = source[node.pos[0]:node.pos[1]].strip()
            if cmd_text:
                commands.append(cmd_text)
        elif node.kind == 'command':
            cmd_text = source[node.pos[0]:node.pos[1]].strip()
            if cmd_text:
                commands.append(cmd_text)
        elif hasattr(node, 'parts'):
            _extract_list_commands(node.parts, source, commands)
        elif hasattr(node, 'list'):
            _extract_list_commands(node.list, source, commands)


def split_pipeline(command: str) -> list[str]:
    """
    Split a pipeline into individual commands.
    
    "ls | grep foo | wc -l" -> ["ls", "grep foo", "wc -l"]
    """
    if not BASHLEX_AVAILABLE:
        # Simple fallback
        return [cmd.strip() for cmd in command.split('|') if cmd.strip()]
    
    try:
        parts = bashlex.parse(command)
        commands = []
        
        for part in parts:
            if part.kind == 'pipeline':
                for subpart in part.parts:
                    # Skip pipe nodes, only include command nodes
                    if subpart.kind == 'command':
                        cmd_text = command[subpart.pos[0]:subpart.pos[1]].strip()
                        if cmd_text:
                            commands.append(cmd_text)
            elif part.kind == 'command':
                cmd_text = command[part.pos[0]:part.pos[1]].strip()
                if cmd_text:
                    commands.append(cmd_text)
        
        return commands if commands else [command]
    except (bashlex.errors.ParsingError, Exception):
        return [cmd.strip() for cmd in command.split('|') if cmd.strip()]
