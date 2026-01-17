"""
Centralized AST analyzer for Dippy.

Single recursive walk of bash AST with consistent decision-making.
Unknown constructs default to ask. Decisions bubble up (deny > ask > allow).
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from dippy.core.config import Config, match_redirect
from dippy.core.patterns import PREFIX_COMMANDS, SIMPLE_SAFE, UNSAFE_PATTERNS
from dippy.cli import get_handler, get_description
from dippy.vendor.parable import parse, ParseError


@dataclass
class Decision:
    """Result of analyzing an AST node."""

    action: Literal["allow", "ask", "deny"]
    reason: str
    # For tracing: child decisions that contributed to this one
    children: list["Decision"] = field(default_factory=list)

    def __repr__(self) -> str:
        return f"Decision({self.action!r}, {self.reason!r})"


def analyze(command: str, config: Config, cwd: Path) -> Decision:
    """
    Analyze a bash command string.

    Parses the command and recursively analyzes all nodes.
    Returns the combined decision (most restrictive wins).
    """
    command = command.strip()
    if not command:
        return Decision("ask", "empty command")

    try:
        nodes = parse(command)
    except ParseError as e:
        return Decision("ask", f"parse error: {e.message}")

    if not nodes:
        return Decision("ask", "empty command")

    decisions = [_analyze_node(node, config, cwd) for node in nodes]
    return _combine(decisions)


def _analyze_node(node, config: Config, cwd: Path) -> Decision:
    """Recursively analyze a single AST node."""
    kind = getattr(node, "kind", None)

    if kind == "command":
        return _analyze_command(node, config, cwd)

    elif kind == "pipeline":
        # All commands in pipeline must be safe
        decisions = [_analyze_node(cmd, config, cwd) for cmd in node.commands]
        result = _combine(decisions)
        if result.action == "allow":
            reasons = [d.reason for d in decisions]
            return Decision("allow", ", ".join(reasons), children=decisions)
        return result

    elif kind == "list":
        # All parts must be safe (skip operators like && ||)
        parts = [p for p in node.parts if getattr(p, "kind", None) != "operator"]
        decisions = [_analyze_node(p, config, cwd) for p in parts]
        result = _combine(decisions)
        if result.action == "allow":
            reasons = [d.reason for d in decisions]
            return Decision("allow", ", ".join(reasons), children=decisions)
        return result

    elif kind == "if":
        decisions = [_analyze_node(node.condition, config, cwd)]
        decisions.append(_analyze_node(node.then_body, config, cwd))
        if hasattr(node, "else_body") and node.else_body:
            decisions.append(_analyze_node(node.else_body, config, cwd))
        # Also check redirects on the if itself
        decisions.extend(_analyze_redirects(node, config, cwd))
        return _combine(decisions)

    elif kind in ("while", "until"):
        decisions = [
            _analyze_node(node.condition, config, cwd),
            _analyze_node(node.body, config, cwd),
        ]
        decisions.extend(_analyze_redirects(node, config, cwd))
        return _combine(decisions)

    elif kind == "for":
        decisions = [_analyze_node(node.body, config, cwd)]
        decisions.extend(_analyze_redirects(node, config, cwd))
        return _combine(decisions)

    elif kind == "for-arith":
        decisions = [_analyze_node(node.body, config, cwd)]
        decisions.extend(_analyze_redirects(node, config, cwd))
        return _combine(decisions)

    elif kind == "select":
        decisions = [_analyze_node(node.body, config, cwd)]
        decisions.extend(_analyze_redirects(node, config, cwd))
        return _combine(decisions)

    elif kind == "case":
        decisions = []
        for pattern in node.patterns:
            if hasattr(pattern, "body") and pattern.body:
                decisions.append(_analyze_node(pattern.body, config, cwd))
        decisions.extend(_analyze_redirects(node, config, cwd))
        return _combine(decisions) if decisions else Decision("allow", "empty case")

    elif kind == "function":
        # Function definition - analyze the body
        # Note: the function isn't executed when defined, but we still
        # want to know if it contains dangerous commands
        return _analyze_node(node.body, config, cwd)

    elif kind == "subshell":
        return _analyze_node(node.body, config, cwd)

    elif kind == "brace-group":
        return _analyze_node(node.body, config, cwd)

    elif kind == "time":
        # time command - analyze the pipeline being timed
        return _analyze_node(node.pipeline, config, cwd)

    elif kind == "negation":
        # ! command - negates exit status, analyze the inner command
        return _analyze_node(node.pipeline, config, cwd)

    elif kind == "coproc":
        # coproc [NAME] command - analyze the inner command
        return _analyze_node(node.command, config, cwd)

    elif kind == "cond-expr":
        # [[ expression ]] - check for command substitutions in operands
        decisions = []
        if hasattr(node, "body") and node.body:
            decisions.extend(_analyze_cond_node(node.body, config, cwd))
        decisions.extend(_analyze_redirects(node, config, cwd))
        return _combine(decisions) if decisions else Decision("allow", "conditional")

    elif kind == "arith-cmd":
        # (( expr )) - check for command substitutions in the expression
        decisions = []
        for cmdsub in _find_cmdsubs_in_arith(node.expression):
            inner_decision = _analyze_node(cmdsub.command, config, cwd)
            if inner_decision.action != "allow":
                return Decision(
                    inner_decision.action,
                    f"arithmetic cmdsub: {inner_decision.reason}",
                    children=[inner_decision],
                )
            decisions.append(inner_decision)
        if decisions:
            return _combine(decisions)
        return Decision("allow", "arithmetic")

    elif kind == "comment":
        return Decision("allow", "comment")

    elif kind == "empty":
        return Decision("allow", "empty")

    else:
        # Unknown node type - default to ask
        return Decision("ask", f"unrecognized construct: {kind}")


def _analyze_command(node, config: Config, cwd: Path) -> Decision:
    """Analyze a simple command node."""
    decisions = []

    # Get base command for injection check
    words = [_get_word_value(w) for w in node.words]
    # Skip env var assignments to find base command
    base_idx = 0
    while (
        base_idx < len(words)
        and "=" in words[base_idx]
        and not words[base_idx].startswith("-")
    ):
        base_idx += 1
    base = words[base_idx] if base_idx < len(words) else ""
    has_handler = get_handler(base) is not None
    is_simple_safe = base in SIMPLE_SAFE

    # 1. Check for process substitutions and command substitutions in words
    for position, word in enumerate(node.words):
        parts = getattr(word, "parts", [])
        word_value = getattr(word, "value", "")
        # Check if this is a pure cmdsub (entire word is just a cmdsub)
        is_pure_cmdsub = (
            len(parts) == 1
            and getattr(parts[0], "kind", None) == "cmdsub"
            and word_value.startswith("$(")
            and word_value.endswith(")")
        )

        for part in parts:
            part_kind = getattr(part, "kind", None)
            if part_kind == "procsub":
                # Process substitution: <(...) or >(...)
                inner_decision = _analyze_node(part.command, config, cwd)
                if inner_decision.action != "allow":
                    direction = getattr(part, "direction", "?")
                    return Decision(
                        inner_decision.action,
                        f"process substitution {direction}(...): {inner_decision.reason}",
                        children=[inner_decision],
                    )
                decisions.append(inner_decision)
            elif part_kind == "cmdsub":
                # Command substitution: $(...)
                inner_decision = _analyze_node(part.command, config, cwd)
                if inner_decision.action != "allow":
                    return Decision(
                        inner_decision.action,
                        f"command substitution: {inner_decision.reason}",
                        children=[inner_decision],
                    )
                decisions.append(inner_decision)
                # Check for injection risk: pure cmdsub in arg position of handler CLI
                if (
                    is_pure_cmdsub
                    and has_handler
                    and not is_simple_safe
                    and position > base_idx
                ):
                    inner_cmd = _get_word_value(word).strip("$()")
                    return Decision("ask", f"cmdsub injection risk: {inner_cmd}")

    # 2. Check redirects
    redirect_decisions = _analyze_redirects(node, config, cwd)
    for rd in redirect_decisions:
        if rd.action != "allow":
            return rd
    decisions.extend(redirect_decisions)

    # 3. Check the command itself
    if not words:
        return Decision("allow", "empty command")

    cmd_decision = _analyze_simple_command(words, config, cwd)
    decisions.append(cmd_decision)

    return _combine(decisions)


def _analyze_redirects(node, config: Config, cwd: Path) -> list[Decision]:
    """Analyze redirects on a node."""
    decisions = []
    redirects = getattr(node, "redirects", [])

    for r in redirects:
        r_kind = getattr(r, "kind", None)
        if r_kind == "heredoc":
            continue  # Heredocs are data, not commands

        op = getattr(r, "op", "")
        target = _get_word_value(r.target) if r.target else ""

        # Skip safe redirects
        if target == "/dev/null" or target.startswith("&"):
            continue

        # Check output redirects against config
        if op in (">", ">>", "&>", "&>>", "2>", "2>>"):
            redirect_match = match_redirect(target, config, cwd)
            if redirect_match:
                if redirect_match.decision == "allow":
                    decisions.append(Decision("allow", f"redirect to {target}"))
                elif redirect_match.decision == "deny":
                    msg = redirect_match.message or redirect_match.pattern
                    decisions.append(Decision("deny", f"redirect to {target}: {msg}"))
                else:  # ask
                    msg = redirect_match.message or redirect_match.pattern
                    decisions.append(Decision("ask", f"redirect to {target}: {msg}"))
            else:
                # No rule matched - default ask for output redirects
                decisions.append(Decision("ask", f"redirect to {target}"))

    return decisions


def _analyze_simple_command(words: list[str], config: Config, cwd: Path) -> Decision:
    """Analyze a simple command (list of words)."""
    if not words:
        return Decision("allow", "empty")

    # Skip leading environment variable assignments (FOO=bar)
    i = 0
    while i < len(words) and "=" in words[i] and not words[i].startswith("-"):
        i += 1

    if i >= len(words):
        return Decision("allow", "env assignment")

    base = words[i]
    tokens = words[i:]

    # 1. Check config rules first (highest priority)
    from dippy.core.config import SimpleCommand, match_command

    cmd = SimpleCommand(words=words)
    config_match = match_command(cmd, config, cwd)
    if config_match:
        if config_match.decision == "allow":
            return Decision("allow", f"{base} ({config_match.pattern})")
        elif config_match.decision == "deny":
            msg = config_match.message or config_match.pattern
            return Decision("deny", f"{base}: {msg}")
        else:  # ask
            msg = config_match.message or config_match.pattern
            return Decision("ask", f"{base}: {msg}")

    # 2. Handle prefix commands (time, env, timeout, etc.)
    if base in PREFIX_COMMANDS and len(tokens) > 1:
        if base == "command" and len(tokens) > 1 and tokens[1] in ("-v", "-V"):
            return Decision("allow", "command -v")

        # Skip numeric arguments and flags until we find the actual command
        j = 1
        while j < len(tokens):
            token = tokens[j]
            if token.isdigit() or token.replace(".", "").isdigit():
                j += 1
                continue
            if token.startswith("-") and token != "--":
                j += 1
                continue
            if token == "--":
                j += 1
            break

        if j < len(tokens):
            return _analyze_simple_command(tokens[j:], config, cwd)
        return Decision("ask", base)

    # 3. Simple safe commands
    if base in SIMPLE_SAFE:
        return Decision("allow", base)

    # 4. Version/help checks
    if _is_version_or_help(tokens):
        return Decision("allow", f"{base} --help")

    # 5. CLI-specific handlers
    handler = get_handler(base)
    if handler:
        result = handler.classify(tokens)
        desc = result.description or get_description(tokens, base)
        # Check handler-provided redirect targets against config
        if result.redirect_targets:
            for target in result.redirect_targets:
                redirect_match = match_redirect(target, config, cwd)
                if redirect_match:
                    if redirect_match.decision == "deny":
                        msg = redirect_match.message or redirect_match.pattern
                        return Decision("deny", f"{desc}: {msg}")
                    elif redirect_match.decision == "ask":
                        msg = redirect_match.message or redirect_match.pattern
                        return Decision("ask", f"{desc}: {msg}")
                    # allow - continue checking other targets
                else:
                    # No matching rule - ask by default for file writes
                    return Decision("ask", desc)
        if result.action == "approve":
            return Decision("allow", desc)
        elif result.action == "delegate" and result.inner_command:
            # Delegate to inner command (e.g., bash -c 'inner')
            inner_decision = analyze(result.inner_command, config, cwd)
            return inner_decision
        else:
            return Decision("ask", desc)

    # 6. Check unsafe patterns
    command_str = " ".join(words)
    for pattern in UNSAFE_PATTERNS:
        if pattern.search(command_str):
            return Decision("ask", base)

    # 7. Unknown command - default ask (show more context than just base)
    return Decision("ask", get_description(tokens, base))


def _is_version_or_help(tokens: list[str]) -> bool:
    """Check if command is a version/help check."""
    if len(tokens) < 2:
        return False

    if len(tokens) == 2 and tokens[1] in ("help", "version"):
        return True

    if len(tokens) == 2 and tokens[1] in ("--version", "--help", "-h"):
        return True

    if tokens[-1] in ("--help", "-h") and len(tokens) <= 4:
        return True

    return False


def _get_word_value(word) -> str:
    """Extract string value from a word node, stripping outer quotes."""
    if isinstance(word, str):
        value = word
    else:
        value = getattr(word, "value", str(word))
    return _strip_quotes(value)


def _strip_quotes(value: str) -> str:
    """Strip surrounding quotes from a value."""
    if len(value) >= 2:
        if (value[0] == '"' and value[-1] == '"') or (
            value[0] == "'" and value[-1] == "'"
        ):
            return value[1:-1]
    return value


def _find_cmdsubs_in_arith(node) -> list:
    """Recursively find command substitutions in an arithmetic expression AST."""
    results = []
    if node is None:
        return results
    kind = getattr(node, "kind", None)
    if kind == "cmdsub":
        results.append(node)
        return results
    # Walk all child attributes that might contain nested expressions
    for attr in ("value", "target", "left", "right", "operand", "index", "expression"):
        child = getattr(node, attr, None)
        if child is not None:
            results.extend(_find_cmdsubs_in_arith(child))
    return results


def _analyze_cond_node(node, config: Config, cwd: Path) -> list[Decision]:
    """Recursively analyze a conditional expression node for cmdsubs."""
    if node is None:
        return []
    kind = getattr(node, "kind", None)
    if kind == "unary-test":
        # -f file, -z string - check operand for cmdsubs
        return _analyze_word_parts(node.operand, config, cwd)
    elif kind == "binary-test":
        # $a == $b - check both operands for cmdsubs
        decisions = []
        decisions.extend(_analyze_word_parts(node.left, config, cwd))
        decisions.extend(_analyze_word_parts(node.right, config, cwd))
        return decisions
    elif kind in ("cond-and", "cond-or"):
        # expr1 && expr2, expr1 || expr2 - recurse both sides
        decisions = []
        decisions.extend(_analyze_cond_node(node.left, config, cwd))
        decisions.extend(_analyze_cond_node(node.right, config, cwd))
        return decisions
    elif kind == "cond-not":
        # ! expr - recurse into operand
        return _analyze_cond_node(node.operand, config, cwd)
    elif kind == "cond-paren":
        # ( expr ) - recurse into inner
        return _analyze_cond_node(node.inner, config, cwd)
    return []


def _analyze_word_parts(word, config: Config, cwd: Path) -> list[Decision]:
    """Analyze word parts for command/process substitutions."""
    decisions = []
    parts = getattr(word, "parts", [])
    for part in parts:
        part_kind = getattr(part, "kind", None)
        if part_kind == "cmdsub":
            inner_decision = _analyze_node(part.command, config, cwd)
            if inner_decision.action != "allow":
                decisions.append(
                    Decision(
                        inner_decision.action,
                        f"conditional cmdsub: {inner_decision.reason}",
                        children=[inner_decision],
                    )
                )
            else:
                decisions.append(inner_decision)
        elif part_kind == "procsub":
            inner_decision = _analyze_node(part.command, config, cwd)
            if inner_decision.action != "allow":
                direction = getattr(part, "direction", "?")
                decisions.append(
                    Decision(
                        inner_decision.action,
                        f"conditional procsub {direction}(...): {inner_decision.reason}",
                        children=[inner_decision],
                    )
                )
            else:
                decisions.append(inner_decision)
    return decisions


def _combine(decisions: list[Decision]) -> Decision:
    """Combine multiple decisions - most restrictive wins, all reasons at that level."""
    if not decisions:
        return Decision("allow", "empty")

    # Collect reasons by decision level
    deny_reasons = [d.reason for d in decisions if d.action == "deny"]
    ask_reasons = [d.reason for d in decisions if d.action == "ask"]
    allow_reasons = [d.reason for d in decisions if d.action == "allow"]

    # deny > ask > allow
    if deny_reasons:
        return Decision("deny", ", ".join(deny_reasons), children=decisions)

    if ask_reasons:
        return Decision("ask", ", ".join(ask_reasons), children=decisions)

    # All allowed
    return Decision("allow", ", ".join(allow_reasons), children=decisions)
