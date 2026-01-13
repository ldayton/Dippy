"""Parable - A recursive descent parser for bash."""


class ParseError(Exception):
    """Raised when parsing fails."""

    def __init__(self, message: str, pos: int = None, line: int = None):
        self.message = message
        self.pos = pos
        self.line = line
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        if self.line is not None and self.pos is not None:
            return (
                f"Parse error at line {self.line}, position {self.pos}: {self.message}"
            )
        elif self.pos is not None:
            return f"Parse error at position {self.pos}: {self.message}"
        return f"Parse error: {self.message}"


def _is_hex_digit(c: str) -> bool:
    return (c >= "0" and c <= "9") or (c >= "a" and c <= "f") or (c >= "A" and c <= "F")


def _is_octal_digit(c: str) -> bool:
    return c >= "0" and c <= "7"


# ANSI-C escape sequence byte values
ANSI_C_ESCAPES = {
    "a": 0x07,  # bell
    "b": 0x08,  # backspace
    "e": 0x1B,  # escape
    "E": 0x1B,  # escape (alt)
    "f": 0x0C,  # form feed
    "n": 0x0A,  # newline
    "r": 0x0D,  # carriage return
    "t": 0x09,  # tab
    "v": 0x0B,  # vertical tab
    "\\": 0x5C,  # backslash
    '"': 0x22,  # double quote
    "?": 0x3F,  # question mark
}


def _get_ansi_escape(c: str) -> int:
    """Look up simple ANSI-C escape byte value. Returns -1 if not found."""
    return ANSI_C_ESCAPES.get(c, -1)


def _is_whitespace(c: str) -> bool:
    return c == " " or c == "\t" or c == "\n"


def _is_whitespace_no_newline(c: str) -> bool:
    return c == " " or c == "\t"


def _substring(s: str, start: int, end: int) -> str:
    """Extract substring from start to end (exclusive)."""
    return s[start:end]


def _starts_with_at(s: str, pos: int, prefix: str) -> bool:
    """Check if s starts with prefix at position pos."""
    return s.startswith(prefix, pos)


def _sublist(lst: list, start: int, end: int) -> list:
    """Extract sublist from start to end (exclusive)."""
    return lst[start:end]


def _repeat_str(s: str, n: int) -> str:
    """Repeat string s n times."""
    result = []
    i = 0
    while i < n:
        result.append(s)
        i += 1
    return "".join(result)


def _append_redirects(base: str, redirects: list | None) -> str:
    """Append redirect sexp strings to a base sexp string."""
    if redirects:
        parts = []
        for r in redirects:
            parts.append(r.to_sexp())
        return base + " " + " ".join(parts)
    return base


class Node:
    """Base class for all AST nodes."""

    kind: str

    def to_sexp(self) -> str:
        """Convert node to S-expression string for testing."""
        raise NotImplementedError


class Word(Node):
    """A word token, possibly containing expansions."""

    value: str
    parts: list[Node]

    def __init__(self, value: str, parts: list[Node] = None):
        self.kind = "word"
        self.value = value
        if parts is None:
            parts = []
        self.parts = parts

    def to_sexp(self) -> str:
        value = self.value
        # Expand ALL $'...' ANSI-C quotes (handles escapes and strips $)
        value = self._expand_all_ansi_c_quotes(value)
        # Strip $ from locale strings $"..." (quote-aware)
        value = self._strip_locale_string_dollars(value)
        # Normalize whitespace in array assignments: name=(a  b\tc) -> name=(a b c)
        value = self._normalize_array_whitespace(value)
        # Format command substitutions with bash-oracle pretty-printing (before escaping)
        value = self._format_command_substitutions(value)
        # Strip line continuations (backslash-newline) from arithmetic expressions
        value = self._strip_arith_line_continuations(value)
        # Double CTLESC (0x01) bytes - bash-oracle uses this for quoting control chars
        # Exception: don't double when preceded by odd number of backslashes (escaped)
        value = self._double_ctlesc_smart(value)
        # Prefix DEL (0x7f) with CTLESC - bash-oracle quotes this control char
        value = value.replace("\x7f", "\x01\x7f")
        # Escape backslashes for s-expression output
        value = value.replace("\\", "\\\\")
        # Escape double quotes, newlines, and tabs
        escaped = value.replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")
        return '(word "' + escaped + '")'

    def _append_with_ctlesc(self, result: bytearray, byte_val: int):
        """Append byte to result (CTLESC doubling happens later in to_sexp)."""
        result.append(byte_val)

    def _double_ctlesc_smart(self, value: str) -> str:
        """Double CTLESC bytes unless escaped by backslash inside double quotes."""
        result = []
        in_single = False
        in_double = False
        for c in value:
            # Track quote state
            if c == "'" and not in_double:
                in_single = not in_single
            elif c == '"' and not in_single:
                in_double = not in_double
            result.append(c)
            if c == "\x01":
                # Only count backslashes in double-quoted context (where they escape)
                # In single quotes, backslashes are literal, so always double CTLESC
                if in_double:
                    bs_count = 0
                    for j in range(len(result) - 2, -1, -1):
                        if result[j] == "\\":
                            bs_count += 1
                        else:
                            break
                    if bs_count % 2 == 0:
                        result.append("\x01")
                else:
                    # Outside double quotes (including single quotes): always double
                    result.append("\x01")
        return "".join(result)

    def _expand_ansi_c_escapes(self, value: str) -> str:
        """Expand ANSI-C escape sequences in $'...' strings.

        Uses bytes internally so \\x escapes can form valid UTF-8 sequences.
        Invalid UTF-8 is replaced with U+FFFD.
        """
        if not (value.startswith("'") and value.endswith("'")):
            return value
        inner = _substring(value, 1, len(value) - 1)
        result = bytearray()
        i = 0
        while i < len(inner):
            if inner[i] == "\\" and i + 1 < len(inner):
                c = inner[i + 1]
                # Check simple escapes first
                simple = _get_ansi_escape(c)
                if simple >= 0:
                    result.append(simple)
                    i += 2
                elif c == "'":
                    # bash-oracle outputs \' as '\'' (shell quoting trick)
                    result.extend(b"'\\''")
                    i += 2
                elif c == "x":
                    # Check for \x{...} brace syntax (bash 5.3+)
                    if i + 2 < len(inner) and inner[i + 2] == "{":
                        # Find closing brace or end of hex digits
                        j = i + 3
                        while j < len(inner) and _is_hex_digit(inner[j]):
                            j += 1
                        hex_str = _substring(inner, i + 3, j)
                        if j < len(inner) and inner[j] == "}":
                            j += 1  # consume }
                        # If no hex digits, treat as NUL (truncates)
                        if not hex_str:
                            return "'" + result.decode("utf-8", errors="replace") + "'"
                        byte_val = int(hex_str, 16) & 0xFF  # Take low byte
                        if byte_val == 0:
                            return "'" + result.decode("utf-8", errors="replace") + "'"
                        self._append_with_ctlesc(result, byte_val)
                        i = j
                    else:
                        # Hex escape \xHH (1-2 hex digits) - raw byte
                        j = i + 2
                        while j < len(inner) and j < i + 4 and _is_hex_digit(inner[j]):
                            j += 1
                        if j > i + 2:
                            byte_val = int(_substring(inner, i + 2, j), 16)
                            if byte_val == 0:
                                # NUL truncates string
                                return (
                                    "'" + result.decode("utf-8", errors="replace") + "'"
                                )
                            self._append_with_ctlesc(result, byte_val)
                            i = j
                        else:
                            result.append(ord(inner[i]))
                            i += 1
                elif c == "u":
                    # Unicode escape \uHHHH (1-4 hex digits) - encode as UTF-8
                    j = i + 2
                    while j < len(inner) and j < i + 6 and _is_hex_digit(inner[j]):
                        j += 1
                    if j > i + 2:
                        codepoint = int(_substring(inner, i + 2, j), 16)
                        if codepoint == 0:
                            # NUL truncates string
                            return "'" + result.decode("utf-8", errors="replace") + "'"
                        result.extend(chr(codepoint).encode("utf-8"))
                        i = j
                    else:
                        result.append(ord(inner[i]))
                        i += 1
                elif c == "U":
                    # Unicode escape \UHHHHHHHH (1-8 hex digits) - encode as UTF-8
                    j = i + 2
                    while j < len(inner) and j < i + 10 and _is_hex_digit(inner[j]):
                        j += 1
                    if j > i + 2:
                        codepoint = int(_substring(inner, i + 2, j), 16)
                        if codepoint == 0:
                            # NUL truncates string
                            return "'" + result.decode("utf-8", errors="replace") + "'"
                        result.extend(chr(codepoint).encode("utf-8"))
                        i = j
                    else:
                        result.append(ord(inner[i]))
                        i += 1
                elif c == "c":
                    # Control character \cX - mask with 0x1f
                    if i + 3 <= len(inner):
                        ctrl_char = inner[i + 2]
                        ctrl_val = ord(ctrl_char) & 0x1F
                        if ctrl_val == 0:
                            # NUL truncates string
                            return "'" + result.decode("utf-8", errors="replace") + "'"
                        self._append_with_ctlesc(result, ctrl_val)
                        i += 3
                    else:
                        result.append(ord(inner[i]))
                        i += 1
                elif c == "0":
                    # Nul or octal \0 or \0NNN
                    j = i + 2
                    while j < len(inner) and j < i + 5 and _is_octal_digit(inner[j]):
                        j += 1
                    if j > i + 2:
                        byte_val = int(_substring(inner, i + 1, j), 8)
                        if byte_val == 0:
                            # NUL truncates string
                            return "'" + result.decode("utf-8", errors="replace") + "'"
                        self._append_with_ctlesc(result, byte_val)
                        i = j
                    else:
                        # Just \0 - NUL truncates string
                        return "'" + result.decode("utf-8", errors="replace") + "'"
                elif c >= "1" and c <= "7":
                    # Octal escape \NNN (1-3 digits) - raw byte
                    j = i + 1
                    while j < len(inner) and j < i + 4 and _is_octal_digit(inner[j]):
                        j += 1
                    byte_val = int(_substring(inner, i + 1, j), 8)
                    if byte_val == 0:
                        # NUL truncates string
                        return "'" + result.decode("utf-8", errors="replace") + "'"
                    self._append_with_ctlesc(result, byte_val)
                    i = j
                else:
                    # Unknown escape - preserve as-is
                    result.append(0x5C)
                    result.append(ord(c))
                    i += 2
            else:
                result.extend(inner[i].encode("utf-8"))
                i += 1
        # Decode as UTF-8, replacing invalid sequences with U+FFFD
        return "'" + result.decode("utf-8", errors="replace") + "'"

    def _expand_all_ansi_c_quotes(self, value: str) -> str:
        """Find and expand ALL $'...' ANSI-C quoted strings in value."""
        result = []
        i = 0
        in_single_quote = False
        in_double_quote = False
        in_backtick = False  # Track backtick substitutions - don't expand inside
        brace_depth = 0  # Track ${...} nesting - inside braces, $'...' is expanded
        while i < len(value):
            ch = value[i]
            # Track backtick context - don't expand $'...' inside backticks
            if ch == "`" and not in_single_quote:
                in_backtick = not in_backtick
                result.append(ch)
                i += 1
                continue
            # Inside backticks, just copy everything as-is
            if in_backtick:
                if ch == "\\" and i + 1 < len(value):
                    result.append(ch)
                    result.append(value[i + 1])
                    i += 2
                else:
                    result.append(ch)
                    i += 1
                continue
            # Track brace depth for parameter expansions
            if not in_single_quote:
                if _starts_with_at(value, i, "${"):
                    brace_depth += 1
                    result.append("${")
                    i += 2
                    continue
                elif ch == "}" and brace_depth > 0:
                    brace_depth -= 1
                    result.append(ch)
                    i += 1
                    continue
            # Inside ${...}, we can expand $'...' even if originally in double quotes
            effective_in_dquote = in_double_quote and brace_depth == 0
            # Track quote state to avoid matching $' inside regular quotes
            if ch == "'" and not effective_in_dquote:
                # Toggle quote state unless this is $' (handled below)
                if not (not in_single_quote and i > 0 and value[i - 1] == "$"):
                    in_single_quote = not in_single_quote
                result.append(ch)
                i += 1
            elif ch == '"' and not in_single_quote:
                in_double_quote = not in_double_quote
                result.append(ch)
                i += 1
            elif ch == "\\" and i + 1 < len(value) and not in_single_quote:
                # Backslash escape - skip both chars to avoid misinterpreting \" or \'
                result.append(ch)
                result.append(value[i + 1])
                i += 2
            elif (
                _starts_with_at(value, i, "$'")
                and not in_single_quote
                and not effective_in_dquote
            ):
                # ANSI-C quoted string - find matching closing quote
                j = i + 2
                while j < len(value):
                    if value[j] == "\\" and j + 1 < len(value):
                        j += 2  # Skip escaped char
                    elif value[j] == "'":
                        j += 1  # Include closing quote
                        break
                    else:
                        j += 1
                # Extract and expand the $'...' sequence
                ansi_str = _substring(value, i, j)  # e.g. $'hello\nworld'
                # Strip the $ and expand escapes
                expanded = self._expand_ansi_c_escapes(
                    _substring(ansi_str, 1, len(ansi_str))
                )  # Pass 'hello\nworld'
                # Inside ${...}, strip quotes for default/alternate value operators
                # but keep them for pattern replacement operators
                if (
                    brace_depth > 0
                    and expanded.startswith("'")
                    and expanded.endswith("'")
                ):
                    inner = _substring(expanded, 1, len(expanded) - 1)
                    # Only strip if non-empty and no CTLESC
                    if inner and inner.find("\x01") == -1:
                        # Check if we're in a pattern context (/, //, %, %%, #, ##)
                        # by scanning backward for pattern operators
                        result_str = "".join(result)
                        in_pattern = False
                        # Look for pattern operators after ${
                        for op in ["//", "/", "%%", "%", "##", "#"]:
                            if op in result_str:
                                in_pattern = True
                                break
                        if not in_pattern:
                            expanded = inner
                result.append(expanded)
                i = j
            else:
                result.append(ch)
                i += 1
        return "".join(result)

    def _strip_locale_string_dollars(self, value: str) -> str:
        """Strip $ from locale strings $"..." while tracking quote context."""
        result = []
        i = 0
        in_single_quote = False
        in_double_quote = False
        while i < len(value):
            ch = value[i]
            if ch == "'" and not in_double_quote:
                in_single_quote = not in_single_quote
                result.append(ch)
                i += 1
            elif ch == '"' and not in_single_quote:
                in_double_quote = not in_double_quote
                result.append(ch)
                i += 1
            elif ch == "\\" and i + 1 < len(value):
                # Escape - copy both chars
                result.append(ch)
                result.append(value[i + 1])
                i += 2
            elif (
                _starts_with_at(value, i, '$"')
                and not in_single_quote
                and not in_double_quote
            ):
                # Locale string $"..." outside quotes - strip the $ and enter double quote
                result.append('"')
                in_double_quote = True
                i += 2
            else:
                result.append(ch)
                i += 1
        return "".join(result)

    def _normalize_array_whitespace(self, value: str) -> str:
        """Normalize whitespace inside array assignments: arr=(a  b\tc) -> arr=(a b c)."""
        # Match array assignment pattern: name=( or name+=(
        if not value.endswith(")"):
            return value
        # Parse identifier: starts with letter/underscore, then alnum/underscore
        i = 0
        if not (i < len(value) and (value[i].isalpha() or value[i] == "_")):
            return value
        i += 1
        while i < len(value) and (value[i].isalnum() or value[i] == "_"):
            i += 1
        # Optional + for +=
        if i < len(value) and value[i] == "+":
            i += 1
        # Must have =(
        if not (i + 1 < len(value) and value[i] == "=" and value[i + 1] == "("):
            return value
        prefix = _substring(value, 0, i + 1)  # e.g., "arr=" or "arr+="
        # Extract content inside parentheses
        inner = _substring(value, len(prefix) + 1, len(value) - 1)
        result = self._normalize_array_inner(inner)
        return prefix + "(" + result + ")"

    def _normalize_array_inner(self, inner: str) -> str:
        """Normalize whitespace inside array content, handling nested constructs."""
        normalized = []
        i = 0
        in_whitespace = True  # Start true to skip leading whitespace
        brace_depth = 0  # Track ${...} nesting
        while i < len(inner):
            ch = inner[i]
            if _is_whitespace(ch):
                if not in_whitespace and normalized and brace_depth == 0:
                    normalized.append(" ")
                    in_whitespace = True
                if brace_depth > 0:
                    normalized.append(ch)
                i += 1
            elif ch == "'":
                # Single-quoted string - preserve as-is
                in_whitespace = False
                j = i + 1
                while j < len(inner) and inner[j] != "'":
                    j += 1
                normalized.append(_substring(inner, i, j + 1))
                i = j + 1
            elif ch == '"':
                # Double-quoted string - strip line continuations
                in_whitespace = False
                j = i + 1
                dq_content = ['"']
                while j < len(inner):
                    if inner[j] == "\\" and j + 1 < len(inner):
                        if inner[j + 1] == "\n":
                            # Skip line continuation
                            j += 2
                        else:
                            dq_content.append(inner[j])
                            dq_content.append(inner[j + 1])
                            j += 2
                    elif inner[j] == '"':
                        dq_content.append('"')
                        j += 1
                        break
                    else:
                        dq_content.append(inner[j])
                        j += 1
                normalized.append("".join(dq_content))
                i = j
            elif ch == "\\" and i + 1 < len(inner):
                if inner[i + 1] == "\n":
                    # Line continuation - skip both backslash and newline
                    i += 2
                else:
                    # Escape sequence - preserve
                    in_whitespace = False
                    normalized.append(_substring(inner, i, i + 2))
                    i += 2
            elif (
                ch == "$"
                and i + 2 < len(inner)
                and inner[i + 1] == "("
                and inner[i + 2] == "("
            ):
                # Arithmetic expansion $(( - find matching )) and preserve as-is
                in_whitespace = False
                j = i + 3
                depth = 1
                while j < len(inner) and depth > 0:
                    if j + 1 < len(inner) and inner[j] == "(" and inner[j + 1] == "(":
                        depth += 1
                        j += 2
                    elif j + 1 < len(inner) and inner[j] == ")" and inner[j + 1] == ")":
                        depth -= 1
                        j += 2
                    else:
                        j += 1
                normalized.append(_substring(inner, i, j))
                i = j
            elif ch == "$" and i + 1 < len(inner) and inner[i + 1] == "(":
                # Command substitution - find matching ) and preserve as-is
                # (formatting is handled later by _format_command_substitutions)
                in_whitespace = False
                j = i + 2
                depth = 1
                while j < len(inner) and depth > 0:
                    if inner[j] == "(" and j > 0 and inner[j - 1] == "$":
                        depth += 1
                    elif inner[j] == ")":
                        depth -= 1
                    elif inner[j] == "'":
                        j += 1
                        while j < len(inner) and inner[j] != "'":
                            j += 1
                    elif inner[j] == '"':
                        j += 1
                        while j < len(inner):
                            if inner[j] == "\\" and j + 1 < len(inner):
                                j += 2
                                continue
                            if inner[j] == '"':
                                break
                            j += 1
                    j += 1
                # Preserve command substitution as-is
                normalized.append(_substring(inner, i, j))
                i = j
            elif ch == "$" and i + 1 < len(inner) and inner[i + 1] == "{":
                # Start of ${...} expansion
                in_whitespace = False
                normalized.append("${")
                brace_depth += 1
                i += 2
            elif ch == "{" and brace_depth > 0:
                # Nested brace inside expansion
                normalized.append(ch)
                brace_depth += 1
                i += 1
            elif ch == "}" and brace_depth > 0:
                # End of expansion
                normalized.append(ch)
                brace_depth -= 1
                i += 1
            elif ch == "#" and brace_depth == 0:
                # Comment - skip to end of line (only at top level)
                while i < len(inner) and inner[i] != "\n":
                    i += 1
            else:
                in_whitespace = False
                normalized.append(ch)
                i += 1
        # Strip trailing whitespace
        return "".join(normalized).rstrip()

    def _strip_arith_line_continuations(self, value: str) -> str:
        """Strip backslash-newline (line continuation) from inside $((...))."""
        result = []
        i = 0
        while i < len(value):
            # Check for $(( arithmetic expression
            if _starts_with_at(value, i, "$(("):
                # Find matching ))
                start = i
                i += 3
                depth = 1
                arith_content = []
                while i < len(value) and depth > 0:
                    if _starts_with_at(value, i, "(("):
                        arith_content.append("((")
                        depth += 1
                        i += 2
                    elif _starts_with_at(value, i, "))"):
                        depth -= 1
                        if depth > 0:
                            arith_content.append("))")
                        i += 2
                    elif (
                        value[i] == "\\" and i + 1 < len(value) and value[i + 1] == "\n"
                    ):
                        # Skip backslash-newline (line continuation)
                        i += 2
                    else:
                        arith_content.append(value[i])
                        i += 1
                if depth == 0:
                    # Found proper )) closing - this is arithmetic
                    result.append("$((" + "".join(arith_content) + "))")
                else:
                    # Didn't find )) - not arithmetic (likely $( + ( subshell), pass through
                    result.append(_substring(value, start, i))
            else:
                result.append(value[i])
                i += 1
        return "".join(result)

    def _collect_cmdsubs(self, node) -> list:
        """Recursively collect CommandSubstitution nodes from an AST node."""
        result = []
        node_kind = getattr(node, "kind", None)
        if node_kind == "cmdsub":
            result.append(node)
        elif node_kind == "array":
            # Array node - collect from each element's parts
            elements = getattr(node, "elements", [])
            for elem in elements:
                parts = getattr(elem, "parts", [])
                for p in parts:
                    if getattr(p, "kind", None) == "cmdsub":
                        result.append(p)
                    else:
                        result.extend(self._collect_cmdsubs(p))
        else:
            expr = getattr(node, "expression", None)
            if expr is not None:
                # ArithmeticExpansion, ArithBinaryOp, etc.
                result.extend(self._collect_cmdsubs(expr))
        left = getattr(node, "left", None)
        if left is not None:
            result.extend(self._collect_cmdsubs(left))
        right = getattr(node, "right", None)
        if right is not None:
            result.extend(self._collect_cmdsubs(right))
        operand = getattr(node, "operand", None)
        if operand is not None:
            result.extend(self._collect_cmdsubs(operand))
        condition = getattr(node, "condition", None)
        if condition is not None:
            result.extend(self._collect_cmdsubs(condition))
        true_value = getattr(node, "true_value", None)
        if true_value is not None:
            result.extend(self._collect_cmdsubs(true_value))
        false_value = getattr(node, "false_value", None)
        if false_value is not None:
            result.extend(self._collect_cmdsubs(false_value))
        return result

    def _format_command_substitutions(self, value: str) -> str:
        """Replace $(...) and >(...) / <(...) with bash-oracle-formatted AST output."""
        # Collect command substitutions from all parts, including nested ones
        cmdsub_parts = []
        procsub_parts = []
        for p in self.parts:
            if p.kind == "cmdsub":
                cmdsub_parts.append(p)
            elif p.kind == "procsub":
                procsub_parts.append(p)
            else:
                cmdsub_parts.extend(self._collect_cmdsubs(p))
        # Check if we have ${ or ${| brace command substitutions to format
        has_brace_cmdsub = value.find("${ ") != -1 or value.find("${|") != -1
        # Check if there's an untracked $( that isn't $((, skipping over quotes only
        has_untracked_cmdsub = False
        idx = 0
        in_double = False
        while idx < len(value):
            if value[idx] == '"':
                in_double = not in_double
                idx += 1
            elif value[idx] == "'" and not in_double:
                # Skip over single-quoted string (contents are literal)
                # But only when not inside double quotes
                idx += 1
                while idx < len(value) and value[idx] != "'":
                    idx += 1
                if idx < len(value):
                    idx += 1  # skip closing quote
            elif _starts_with_at(value, idx, "$(") and not _starts_with_at(
                value, idx, "$(("
            ):
                has_untracked_cmdsub = True
                break
            else:
                idx += 1
        if (
            not cmdsub_parts
            and not procsub_parts
            and not has_brace_cmdsub
            and not has_untracked_cmdsub
        ):
            return value
        result = []
        i = 0
        cmdsub_idx = 0
        procsub_idx = 0
        in_double_quote = False
        while i < len(value):
            # Check for $( command substitution (but not $(( arithmetic or escaped \$()
            if (
                _starts_with_at(value, i, "$(")
                and not _starts_with_at(value, i, "$((")
                and (i == 0 or value[i - 1] != "\\")
            ):
                # Find matching close paren using bash-aware matching
                j = _find_cmdsub_end(value, i + 2)
                # Format this command substitution
                if cmdsub_idx < len(cmdsub_parts):
                    node = cmdsub_parts[cmdsub_idx]
                    formatted = _format_cmdsub_node(node.command)
                    cmdsub_idx += 1
                else:
                    # No AST node (e.g., inside arithmetic) - parse content on the fly
                    inner = _substring(value, i + 2, j - 1)
                    try:
                        parser = Parser(inner)
                        parsed = parser.parse_list()
                        formatted = _format_cmdsub_node(parsed) if parsed else inner
                    except Exception:
                        formatted = inner
                # Add space after $( if content starts with ( to avoid $((
                if formatted.startswith("("):
                    result.append("$( " + formatted + ")")
                else:
                    result.append("$(" + formatted + ")")
                i = j
            # Check for backtick command substitution
            elif value[i] == "`" and cmdsub_idx < len(cmdsub_parts):
                # Find matching backtick
                j = i + 1
                while j < len(value):
                    if value[j] == "\\" and j + 1 < len(value):
                        j += 2
                        continue
                    if value[j] == "`":
                        j += 1
                        break
                    j += 1
                # Keep backtick substitutions as-is (bash-oracle doesn't reformat them)
                result.append(_substring(value, i, j))
                cmdsub_idx += 1
                i = j
            # Check for >( or <( process substitution
            elif (
                _starts_with_at(value, i, ">(") or _starts_with_at(value, i, "<(")
            ) and procsub_idx < len(procsub_parts):
                direction = value[i]
                # Find matching close paren
                j = _find_cmdsub_end(value, i + 2)
                # Format this process substitution (with in_procsub=True for no-space subshells)
                node = procsub_parts[procsub_idx]
                formatted = _format_cmdsub_node(node.command, in_procsub=True)
                result.append(direction + "(" + formatted + ")")
                procsub_idx += 1
                i = j
            # Check for ${ (space) or ${| brace command substitution
            # But not if the $ is escaped by a backslash
            elif (
                _starts_with_at(value, i, "${ ") or _starts_with_at(value, i, "${|")
            ) and (i == 0 or value[i - 1] != "\\"):
                prefix = _substring(value, i, i + 3)
                # Find matching close brace
                j = i + 3
                depth = 1
                while j < len(value) and depth > 0:
                    if value[j] == "{":
                        depth += 1
                    elif value[j] == "}":
                        depth -= 1
                    j += 1
                # Parse and format the inner content
                inner = _substring(value, i + 2, j - 1)  # Content between ${ and }
                # Check if content is all whitespace - normalize to single space
                if inner.strip() == "":
                    result.append("${ }")
                else:
                    try:
                        parser = Parser(inner.lstrip(" |"))
                        parsed = parser.parse_list()
                        if parsed:
                            formatted = _format_cmdsub_node(parsed)
                            result.append(prefix + formatted + "; }")
                        else:
                            result.append("${ }")
                    except Exception:
                        result.append(_substring(value, i, j))
                i = j
            # Process regular ${...} parameter expansions (recursively format cmdsubs inside)
            # But not if the $ is escaped by a backslash
            elif _starts_with_at(value, i, "${") and (i == 0 or value[i - 1] != "\\"):
                # Find matching close brace, respecting nesting and quotes
                j = i + 2
                depth = 1
                in_single = False
                in_double = False
                while j < len(value) and depth > 0:
                    c = value[j]
                    if c == "\\" and j + 1 < len(value) and not in_single:
                        j += 2
                        continue
                    if c == "'" and not in_double:
                        in_single = not in_single
                    elif c == '"' and not in_single:
                        in_double = not in_double
                    elif not in_single and not in_double:
                        if c == "{":
                            depth += 1
                        elif c == "}":
                            depth -= 1
                    j += 1
                # Recursively format any cmdsubs inside the param expansion
                inner = _substring(value, i + 2, j - 1)
                formatted_inner = self._format_command_substitutions(inner)
                result.append("${" + formatted_inner + "}")
                i = j
            # Track double-quote state (single quotes inside double quotes are literal)
            elif value[i] == '"':
                in_double_quote = not in_double_quote
                result.append(value[i])
                i += 1
            # Skip single-quoted strings (contents are literal, don't look for cmdsubs)
            # But only when NOT inside double quotes (where single quotes are literal)
            elif value[i] == "'" and not in_double_quote:
                j = i + 1
                while j < len(value) and value[j] != "'":
                    j += 1
                if j < len(value):
                    j += 1  # include closing quote
                result.append(_substring(value, i, j))
                i = j
            else:
                result.append(value[i])
                i += 1
        return "".join(result)

    def get_cond_formatted_value(self) -> str:
        """Return value with command substitutions formatted for cond-term output."""
        # Expand ANSI-C quotes
        value = self._expand_all_ansi_c_quotes(self.value)
        # Strip $ from locale strings $"..."
        value = self._strip_locale_string_dollars(value)
        # Format command substitutions
        value = self._format_command_substitutions(value)
        # Bash doubles CTLESC (\x01) characters in output
        value = value.replace("\x01", "\x01\x01")
        return value.rstrip("\n")


class Command(Node):
    """A simple command (words + redirections)."""

    words: list[Word]
    redirects: list[Node]

    def __init__(self, words: list[Word], redirects: list[Node] = None):
        self.kind = "command"
        self.words = words
        if redirects is None:
            redirects = []
        self.redirects = redirects

    def to_sexp(self) -> str:
        parts = []
        for w in self.words:
            parts.append(w.to_sexp())
        for r in self.redirects:
            parts.append(r.to_sexp())
        inner = " ".join(parts)
        if not inner:
            return "(command)"
        return "(command " + inner + ")"


class Pipeline(Node):
    """A pipeline of commands."""

    commands: list[Node]

    def __init__(self, commands: list[Node]):
        self.kind = "pipeline"
        self.commands = commands

    def to_sexp(self) -> str:
        if len(self.commands) == 1:
            return self.commands[0].to_sexp()
        # Build list of (cmd, needs_pipe_both_redirect) filtering out PipeBoth markers
        cmds = []
        i = 0
        while i < len(self.commands):
            cmd = self.commands[i]
            if cmd.kind == "pipe-both":
                i += 1
                continue
            # Check if next element is PipeBoth
            needs_redirect = (
                i + 1 < len(self.commands) and self.commands[i + 1].kind == "pipe-both"
            )
            cmds.append((cmd, needs_redirect))
            i += 1
        if len(cmds) == 1:
            pair = cmds[0]
            cmd = pair[0]
            needs = pair[1]
            return self._cmd_sexp(cmd, needs)
        # Nest right-associatively: (pipe a (pipe b c))
        last_pair = cmds[len(cmds) - 1]
        last_cmd = last_pair[0]
        last_needs = last_pair[1]
        result = self._cmd_sexp(last_cmd, last_needs)
        j = len(cmds) - 2
        while j >= 0:
            pair = cmds[j]
            cmd = pair[0]
            needs = pair[1]
            if needs and cmd.kind != "command":
                # Compound command: redirect as sibling in pipe
                result = "(pipe " + cmd.to_sexp() + ' (redirect ">&" 1) ' + result + ")"
            else:
                result = "(pipe " + self._cmd_sexp(cmd, needs) + " " + result + ")"
            j -= 1
        return result

    def _cmd_sexp(self, cmd: Node, needs_redirect: bool) -> str:
        """Get s-expression for a command, optionally injecting pipe-both redirect."""
        if not needs_redirect:
            return cmd.to_sexp()
        if cmd.kind == "command":
            # Inject redirect inside command
            parts = []
            for w in cmd.words:
                parts.append(w.to_sexp())
            for r in cmd.redirects:
                parts.append(r.to_sexp())
            parts.append('(redirect ">&" 1)')
            return "(command " + " ".join(parts) + ")"
        # Compound command handled by caller
        return cmd.to_sexp()


class List(Node):
    """A list of pipelines with operators."""

    parts: list[Node]  # alternating: pipeline, operator, pipeline, ...

    def __init__(self, parts: list[Node]):
        self.kind = "list"
        self.parts = parts

    def to_sexp(self) -> str:
        # parts = [cmd, op, cmd, op, cmd, ...]
        # Bash precedence: && and || bind tighter than ; and &
        parts = list(self.parts)
        op_names = {
            "&&": "and",
            "||": "or",
            ";": "semi",
            "\n": "semi",
            "&": "background",
        }
        # Strip trailing ; or \n (bash ignores it)
        while (
            len(parts) > 1
            and parts[len(parts) - 1].kind == "operator"
            and (parts[len(parts) - 1].op == ";" or parts[len(parts) - 1].op == "\n")
        ):
            parts = _sublist(parts, 0, len(parts) - 1)
        if len(parts) == 1:
            return parts[0].to_sexp()
        # Handle trailing & as unary background operator
        # & only applies to the immediately preceding pipeline, not the whole list
        if parts[len(parts) - 1].kind == "operator" and parts[len(parts) - 1].op == "&":
            # Find rightmost ; or \n to split there
            for i in range(len(parts) - 3, 0, -2):
                if parts[i].kind == "operator" and (
                    parts[i].op == ";" or parts[i].op == "\n"
                ):
                    left = _sublist(parts, 0, i)
                    right = _sublist(parts, i + 1, len(parts) - 1)  # exclude trailing &
                    if len(left) > 1:
                        left_sexp = List(left).to_sexp()
                    else:
                        left_sexp = left[0].to_sexp()
                    if len(right) > 1:
                        right_sexp = List(right).to_sexp()
                    else:
                        right_sexp = right[0].to_sexp()
                    return "(semi " + left_sexp + " (background " + right_sexp + "))"
            # No ; or \n found, background the whole list (minus trailing &)
            inner_parts = _sublist(parts, 0, len(parts) - 1)
            if len(inner_parts) == 1:
                return "(background " + inner_parts[0].to_sexp() + ")"
            inner_list = List(inner_parts)
            return "(background " + inner_list.to_sexp() + ")"
        # Process by precedence: first split on ; and &, then on && and ||
        return self._to_sexp_with_precedence(parts, op_names)

    def _to_sexp_with_precedence(self, parts: list, op_names: dict) -> str:
        # Process operators by precedence: ; (lowest), then &, then && and ||
        # Split on ; or \n first (rightmost for left-associativity)
        for i in range(len(parts) - 2, 0, -2):
            if parts[i].kind == "operator" and (
                parts[i].op == ";" or parts[i].op == "\n"
            ):
                left = _sublist(parts, 0, i)
                right = _sublist(parts, i + 1, len(parts))
                if len(left) > 1:
                    left_sexp = List(left).to_sexp()
                else:
                    left_sexp = left[0].to_sexp()
                if len(right) > 1:
                    right_sexp = List(right).to_sexp()
                else:
                    right_sexp = right[0].to_sexp()
                return "(semi " + left_sexp + " " + right_sexp + ")"
        # Then split on & (rightmost for left-associativity)
        for i in range(len(parts) - 2, 0, -2):
            if parts[i].kind == "operator" and parts[i].op == "&":
                left = _sublist(parts, 0, i)
                right = _sublist(parts, i + 1, len(parts))
                if len(left) > 1:
                    left_sexp = List(left).to_sexp()
                else:
                    left_sexp = left[0].to_sexp()
                if len(right) > 1:
                    right_sexp = List(right).to_sexp()
                else:
                    right_sexp = right[0].to_sexp()
                return "(background " + left_sexp + " " + right_sexp + ")"
        # No ; or &, process high-prec ops (&&, ||) left-associatively
        result = parts[0].to_sexp()
        for i in range(1, len(parts) - 1, 2):
            op = parts[i]
            cmd = parts[i + 1]
            op_name = op_names.get(op.op, op.op)
            result = "(" + op_name + " " + result + " " + cmd.to_sexp() + ")"
        return result


class Operator(Node):
    """An operator token (&&, ||, ;, &, |)."""

    op: str

    def __init__(self, op: str):
        self.kind = "operator"
        self.op = op

    def to_sexp(self) -> str:
        names = {
            "&&": "and",
            "||": "or",
            ";": "semi",
            "&": "bg",
            "|": "pipe",
        }
        return "(" + names.get(self.op, self.op) + ")"


class PipeBoth(Node):
    """Marker for |& pipe (stdout + stderr)."""

    def __init__(self):
        self.kind = "pipe-both"

    def to_sexp(self) -> str:
        return "(pipe-both)"


class Empty(Node):
    """Empty input."""

    def __init__(self):
        self.kind = "empty"

    def to_sexp(self) -> str:
        return ""


class Comment(Node):
    """A comment (# to end of line)."""

    text: str

    def __init__(self, text: str):
        self.kind = "comment"
        self.text = text

    def to_sexp(self) -> str:
        # bash-oracle doesn't output comments
        return ""


class Redirect(Node):
    """A redirection."""

    op: str
    target: Word
    fd: int | None = None

    def __init__(self, op: str, target: Word, fd: int = None):
        self.kind = "redirect"
        self.op = op
        self.target = target
        self.fd = fd

    def to_sexp(self) -> str:
        # Strip fd prefix from operator (e.g., "2>" -> ">", "{fd}>" -> ">")
        op = self.op.lstrip("0123456789")
        # Strip {varname} prefix if present
        if op.startswith("{"):
            j = 1
            if j < len(op) and (op[j].isalpha() or op[j] == "_"):
                j += 1
                while j < len(op) and (op[j].isalnum() or op[j] == "_"):
                    j += 1
                if j < len(op) and op[j] == "}":
                    op = _substring(op, j + 1, len(op))
        target_val = self.target.value
        # Expand ANSI-C $'...' quotes (converts escapes like \n to actual newline)
        target_val = self.target._expand_all_ansi_c_quotes(target_val)
        # Strip $ from locale strings $"..."
        target_val = self.target._strip_locale_string_dollars(target_val)
        # Format command/process substitutions (uses self.target for parts access)
        target_val = self.target._format_command_substitutions(target_val)
        # For fd duplication, target starts with & (e.g., "&1", "&2", "&-")
        if target_val.startswith("&"):
            # Determine the real operator
            if op == ">":
                op = ">&"
            elif op == "<":
                op = "<&"
            fd_target = _substring(target_val, 1, len(target_val)).rstrip(
                "-"
            )  # "&1" -> "1", "&1-" -> "1"
            if fd_target.isdigit():
                return '(redirect "' + op + '" ' + fd_target + ")"
            elif target_val == "&-":
                return '(redirect ">&-" 0)'
            else:
                # Variable fd dup like >&$fd or >&$fd- (move) - strip the & and trailing -
                return '(redirect "' + op + '" "' + fd_target + '")'
        # Handle case where op is already >& or <&
        if op == ">&" or op == "<&":
            if target_val.isdigit():
                return '(redirect "' + op + '" ' + target_val + ")"
            # Variable fd dup with move indicator (trailing -)
            target_val = target_val.rstrip("-")
            return '(redirect "' + op + '" "' + target_val + '")'
        return '(redirect "' + op + '" "' + target_val + '")'


class HereDoc(Node):
    """A here document <<DELIM ... DELIM."""

    delimiter: str
    content: str
    strip_tabs: bool = False
    quoted: bool = False
    fd: int | None = None

    def __init__(
        self,
        delimiter: str,
        content: str,
        strip_tabs: bool = False,
        quoted: bool = False,
        fd: int = None,
    ):
        self.kind = "heredoc"
        self.delimiter = delimiter
        self.content = content
        self.strip_tabs = strip_tabs
        self.quoted = quoted
        self.fd = fd

    def to_sexp(self) -> str:
        op = "<<-" if self.strip_tabs else "<<"
        return f'(redirect "{op}" "{self.content}")'


class Subshell(Node):
    """A subshell ( list )."""

    body: Node
    redirects: list["Redirect | HereDoc"] | None = None

    def __init__(self, body: Node, redirects: list["Redirect | HereDoc"] | None = None):
        self.kind = "subshell"
        self.body = body
        self.redirects = redirects

    def to_sexp(self) -> str:
        base = "(subshell " + self.body.to_sexp() + ")"
        return _append_redirects(base, self.redirects)


class BraceGroup(Node):
    """A brace group { list; }."""

    body: Node
    redirects: list["Redirect | HereDoc"] | None = None

    def __init__(self, body: Node, redirects: list["Redirect | HereDoc"] | None = None):
        self.kind = "brace-group"
        self.body = body
        self.redirects = redirects

    def to_sexp(self) -> str:
        base = "(brace-group " + self.body.to_sexp() + ")"
        return _append_redirects(base, self.redirects)


class If(Node):
    """An if statement."""

    condition: Node
    then_body: Node
    else_body: Node | None = None
    redirects: list[Node]

    def __init__(
        self,
        condition: Node,
        then_body: Node,
        else_body: Node = None,
        redirects: list[Node] = None,
    ):
        self.kind = "if"
        self.condition = condition
        self.then_body = then_body
        self.else_body = else_body
        if redirects is None:
            redirects = []
        self.redirects = redirects

    def to_sexp(self) -> str:
        result = "(if " + self.condition.to_sexp() + " " + self.then_body.to_sexp()
        if self.else_body:
            result = result + " " + self.else_body.to_sexp()
        result = result + ")"
        for r in self.redirects:
            result = result + " " + r.to_sexp()
        return result


class While(Node):
    """A while loop."""

    condition: Node
    body: Node
    redirects: list[Node]

    def __init__(self, condition: Node, body: Node, redirects: list[Node] = None):
        self.kind = "while"
        self.condition = condition
        self.body = body
        if redirects is None:
            redirects = []
        self.redirects = redirects

    def to_sexp(self) -> str:
        base = "(while " + self.condition.to_sexp() + " " + self.body.to_sexp() + ")"
        return _append_redirects(base, self.redirects)


class Until(Node):
    """An until loop."""

    condition: Node
    body: Node
    redirects: list[Node]

    def __init__(self, condition: Node, body: Node, redirects: list[Node] = None):
        self.kind = "until"
        self.condition = condition
        self.body = body
        if redirects is None:
            redirects = []
        self.redirects = redirects

    def to_sexp(self) -> str:
        base = "(until " + self.condition.to_sexp() + " " + self.body.to_sexp() + ")"
        return _append_redirects(base, self.redirects)


class For(Node):
    """A for loop."""

    var: str
    words: list[Word] | None
    body: Node
    redirects: list[Node]

    def __init__(
        self,
        var: str,
        words: list[Word] | None,
        body: Node,
        redirects: list[Node] = None,
    ):
        self.kind = "for"
        self.var = var
        self.words = words
        self.body = body
        if redirects is None:
            redirects = []
        self.redirects = redirects

    def to_sexp(self) -> str:
        # bash-oracle format: (for (word "var") (in (word "a") ...) body)
        suffix = ""
        if self.redirects:
            redirect_parts = []
            for r in self.redirects:
                redirect_parts.append(r.to_sexp())
            suffix = " " + " ".join(redirect_parts)
        var_escaped = self.var.replace("\\", "\\\\").replace('"', '\\"')
        if self.words is None:
            # No 'in' clause - bash-oracle implies (in (word "\"$@\""))
            return (
                '(for (word "'
                + var_escaped
                + '") (in (word "\\"$@\\"")) '
                + self.body.to_sexp()
                + ")"
                + suffix
            )
        elif len(self.words) == 0:
            # Empty 'in' clause - bash-oracle outputs (in)
            return (
                '(for (word "'
                + var_escaped
                + '") (in) '
                + self.body.to_sexp()
                + ")"
                + suffix
            )
        else:
            word_parts = []
            for w in self.words:
                word_parts.append(w.to_sexp())
            word_strs = " ".join(word_parts)
            return (
                '(for (word "'
                + var_escaped
                + '") (in '
                + word_strs
                + ") "
                + self.body.to_sexp()
                + ")"
                + suffix
            )


class ForArith(Node):
    """A C-style for loop: for ((init; cond; incr)); do ... done."""

    init: str
    cond: str
    incr: str
    body: Node
    redirects: list[Node]

    def __init__(
        self, init: str, cond: str, incr: str, body: Node, redirects: list[Node] = None
    ):
        self.kind = "for-arith"
        self.init = init
        self.cond = cond
        self.incr = incr
        self.body = body
        if redirects is None:
            redirects = []
        self.redirects = redirects

    def to_sexp(self) -> str:
        # bash-oracle format: (arith-for (init (word "x")) (test (word "y")) (step (word "z")) body)
        def format_arith_val(s: str) -> str:
            # Use Word's methods to expand ANSI-C quotes and strip locale $
            w = Word(s, [])
            val = w._expand_all_ansi_c_quotes(s)
            val = w._strip_locale_string_dollars(val)
            val = val.replace("\\", "\\\\").replace('"', '\\"')
            return val

        suffix = ""
        if self.redirects:
            redirect_parts = []
            for r in self.redirects:
                redirect_parts.append(r.to_sexp())
            suffix = " " + " ".join(redirect_parts)
        init_val = self.init if self.init else "1"
        cond_val = _normalize_fd_redirects(self.cond) if self.cond else "1"
        incr_val = self.incr if self.incr else "1"
        init_str = format_arith_val(init_val)
        cond_str = format_arith_val(cond_val)
        incr_str = format_arith_val(incr_val)
        body_str = self.body.to_sexp()
        return f'(arith-for (init (word "{init_str}")) (test (word "{cond_str}")) (step (word "{incr_str}")) {body_str}){suffix}'


class Select(Node):
    """A select statement."""

    var: str
    words: list[Word] | None
    body: Node
    redirects: list[Node]

    def __init__(
        self,
        var: str,
        words: list[Word] | None,
        body: Node,
        redirects: list[Node] = None,
    ):
        self.kind = "select"
        self.var = var
        self.words = words
        self.body = body
        if redirects is None:
            redirects = []
        self.redirects = redirects

    def to_sexp(self) -> str:
        # bash-oracle format: (select (word "var") (in (word "a") ...) body)
        suffix = ""
        if self.redirects:
            redirect_parts = []
            for r in self.redirects:
                redirect_parts.append(r.to_sexp())
            suffix = " " + " ".join(redirect_parts)
        var_escaped = self.var.replace("\\", "\\\\").replace('"', '\\"')
        if self.words is not None:
            word_parts = []
            for w in self.words:
                word_parts.append(w.to_sexp())
            word_strs = " ".join(word_parts)
            if self.words:
                in_clause = "(in " + word_strs + ")"
            else:
                in_clause = "(in)"
        else:
            # No 'in' clause means implicit "$@"
            in_clause = '(in (word "\\"$@\\""))'
        return (
            '(select (word "'
            + var_escaped
            + '") '
            + in_clause
            + " "
            + self.body.to_sexp()
            + ")"
            + suffix
        )


class Case(Node):
    """A case statement."""

    word: Word
    patterns: list["CasePattern"]
    redirects: list[Node]

    def __init__(
        self, word: Word, patterns: list["CasePattern"], redirects: list[Node] = None
    ):
        self.kind = "case"
        self.word = word
        self.patterns = patterns
        if redirects is None:
            redirects = []
        self.redirects = redirects

    def to_sexp(self) -> str:
        parts = []
        parts.append("(case " + self.word.to_sexp())
        for p in self.patterns:
            parts.append(p.to_sexp())
        base = " ".join(parts) + ")"
        return _append_redirects(base, self.redirects)


def _consume_single_quote(s: str, start: int) -> tuple:
    """Consume '...' from start. Returns (end_index, chars_list)."""
    chars = ["'"]
    i = start + 1
    while i < len(s) and s[i] != "'":
        chars.append(s[i])
        i += 1
    if i < len(s):
        chars.append(s[i])
        i += 1
    return (i, chars)


def _consume_double_quote(s: str, start: int) -> tuple:
    """Consume "..." from start, handling escapes. Returns (end_index, chars_list)."""
    chars = ['"']
    i = start + 1
    while i < len(s) and s[i] != '"':
        if s[i] == "\\" and i + 1 < len(s):
            chars.append(s[i])
            i += 1
        chars.append(s[i])
        i += 1
    if i < len(s):
        chars.append(s[i])
        i += 1
    return (i, chars)


def _has_bracket_close(s: str, start: int, depth: int) -> bool:
    """Check if there's a ] before | or ) at depth 0."""
    i = start
    while i < len(s):
        if s[i] == "]":
            return True
        if (s[i] == "|" or s[i] == ")") and depth == 0:
            return False
        i += 1
    return False


def _consume_bracket_class(s: str, start: int, depth: int) -> tuple:
    """Consume [...] bracket expression. Returns (end_index, chars_list, was_bracket)."""
    # First scan to see if this is a valid bracket expression
    scan_pos = start + 1
    # Skip [! or [^ at start
    if scan_pos < len(s) and (s[scan_pos] == "!" or s[scan_pos] == "^"):
        scan_pos += 1
    # Handle ] as first char
    if scan_pos < len(s) and s[scan_pos] == "]":
        if _has_bracket_close(s, scan_pos + 1, depth):
            scan_pos += 1
    # Scan for closing ]
    is_bracket = False
    while scan_pos < len(s):
        if s[scan_pos] == "]":
            is_bracket = True
            break
        if s[scan_pos] == ")" and depth == 0:
            break
        scan_pos += 1
    if not is_bracket:
        return (start + 1, ["["], False)
    # Valid bracket - consume it
    chars = ["["]
    i = start + 1
    # Handle [! or [^
    if i < len(s) and (s[i] == "!" or s[i] == "^"):
        chars.append(s[i])
        i += 1
    # Handle ] as first char
    if i < len(s) and s[i] == "]":
        if _has_bracket_close(s, i + 1, depth):
            chars.append(s[i])
            i += 1
    # Consume until ]
    while i < len(s) and s[i] != "]":
        chars.append(s[i])
        i += 1
    if i < len(s):
        chars.append(s[i])
        i += 1
    return (i, chars, True)


class CasePattern(Node):
    """A pattern clause in a case statement."""

    pattern: str
    body: Node | None
    terminator: str = ";;"  # ";;", ";&", or ";;&"

    def __init__(self, pattern: str, body: Node | None, terminator: str = ";;"):
        self.kind = "pattern"
        self.pattern = pattern
        self.body = body
        self.terminator = terminator

    def to_sexp(self) -> str:
        # bash-oracle format: (pattern ((word "a") (word "b")) body)
        # Split pattern by | respecting escapes, extglobs, quotes, and brackets
        alternatives = []
        current = []
        i = 0
        depth = 0  # Track extglob/paren depth
        while i < len(self.pattern):
            ch = self.pattern[i]
            if ch == "\\" and i + 1 < len(self.pattern):
                current.append(_substring(self.pattern, i, i + 2))
                i += 2
            elif (
                (ch == "@" or ch == "?" or ch == "*" or ch == "+" or ch == "!")
                and i + 1 < len(self.pattern)
                and self.pattern[i + 1] == "("
            ):
                # Start of extglob: @(, ?(, *(, +(, !(
                current.append(ch)
                current.append("(")
                depth += 1
                i += 2
            elif ch == "$" and i + 1 < len(self.pattern) and self.pattern[i + 1] == "(":
                # $( command sub or $(( arithmetic - track depth
                current.append(ch)
                current.append("(")
                depth += 1
                i += 2
            elif ch == "(" and depth > 0:
                current.append(ch)
                depth += 1
                i += 1
            elif ch == ")" and depth > 0:
                current.append(ch)
                depth -= 1
                i += 1
            elif ch == "[":
                result = _consume_bracket_class(self.pattern, i, depth)
                i = result[0]
                current.extend(result[1])
            elif ch == "'" and depth == 0:
                result = _consume_single_quote(self.pattern, i)
                i = result[0]
                current.extend(result[1])
            elif ch == '"' and depth == 0:
                result = _consume_double_quote(self.pattern, i)
                i = result[0]
                current.extend(result[1])
            elif ch == "|" and depth == 0:
                alternatives.append("".join(current))
                current = []
                i += 1
            else:
                current.append(ch)
                i += 1
        alternatives.append("".join(current))
        word_list = []
        for alt in alternatives:
            # Use Word.to_sexp() to properly expand ANSI-C quotes and escape
            word_list.append(Word(alt).to_sexp())
        pattern_str = " ".join(word_list)
        parts = ["(pattern (" + pattern_str + ")"]
        if self.body:
            parts.append(" " + self.body.to_sexp())
        else:
            parts.append(" ()")
        # bash-oracle doesn't output fallthrough/falltest markers
        parts.append(")")
        return "".join(parts)


class Function(Node):
    """A function definition."""

    name: str
    body: Node

    def __init__(self, name: str, body: Node):
        self.kind = "function"
        self.name = name
        self.body = body

    def to_sexp(self) -> str:
        return '(function "' + self.name + '" ' + self.body.to_sexp() + ")"


class ParamExpansion(Node):
    """A parameter expansion ${var} or ${var:-default}."""

    param: str
    op: str | None = None
    arg: str | None = None

    def __init__(self, param: str, op: str = None, arg: str = None):
        self.kind = "param"
        self.param = param
        self.op = op
        self.arg = arg

    def to_sexp(self) -> str:
        escaped_param = self.param.replace("\\", "\\\\").replace('"', '\\"')
        if self.op is not None:
            escaped_op = self.op.replace("\\", "\\\\").replace('"', '\\"')
            if self.arg is not None:
                arg_val = self.arg
            else:
                arg_val = ""
            escaped_arg = arg_val.replace("\\", "\\\\").replace('"', '\\"')
            return (
                '(param "'
                + escaped_param
                + '" "'
                + escaped_op
                + '" "'
                + escaped_arg
                + '")'
            )
        return '(param "' + escaped_param + '")'


class ParamLength(Node):
    """A parameter length expansion ${#var}."""

    param: str

    def __init__(self, param: str):
        self.kind = "param-len"
        self.param = param

    def to_sexp(self) -> str:
        escaped = self.param.replace("\\", "\\\\").replace('"', '\\"')
        return '(param-len "' + escaped + '")'


class ParamIndirect(Node):
    """An indirect parameter expansion ${!var} or ${!var<op><arg>}."""

    param: str
    op: str | None
    arg: str | None

    def __init__(self, param: str, op: str | None = None, arg: str | None = None):
        self.kind = "param-indirect"
        self.param = param
        self.op = op
        self.arg = arg

    def to_sexp(self) -> str:
        escaped = self.param.replace("\\", "\\\\").replace('"', '\\"')
        if self.op is not None:
            escaped_op = self.op.replace("\\", "\\\\").replace('"', '\\"')
            if self.arg is not None:
                arg_val = self.arg
            else:
                arg_val = ""
            escaped_arg = arg_val.replace("\\", "\\\\").replace('"', '\\"')
            return (
                '(param-indirect "'
                + escaped
                + '" "'
                + escaped_op
                + '" "'
                + escaped_arg
                + '")'
            )
        return '(param-indirect "' + escaped + '")'


class CommandSubstitution(Node):
    """A command substitution $(...) or `...`."""

    command: Node

    def __init__(self, command: Node):
        self.kind = "cmdsub"
        self.command = command

    def to_sexp(self) -> str:
        return "(cmdsub " + self.command.to_sexp() + ")"


class ArithmeticExpansion(Node):
    """An arithmetic expansion $((...)) with parsed internals."""

    expression: "Node | None"  # Parsed arithmetic expression, or None for empty

    def __init__(self, expression: "Node | None"):
        self.kind = "arith"
        self.expression = expression

    def to_sexp(self) -> str:
        if self.expression is None:
            return "(arith)"
        return "(arith " + self.expression.to_sexp() + ")"


class ArithmeticCommand(Node):
    """An arithmetic command ((...)) with parsed internals."""

    expression: "Node | None"  # Parsed arithmetic expression, or None for empty
    redirects: list[Node]
    raw_content: str  # Raw expression text for bash-oracle-compatible output

    def __init__(
        self,
        expression: "Node | None",
        redirects: list[Node] = None,
        raw_content: str = "",
    ):
        self.kind = "arith-cmd"
        self.expression = expression
        if redirects is None:
            redirects = []
        self.redirects = redirects
        self.raw_content = raw_content

    def to_sexp(self) -> str:
        # bash-oracle format: (arith (word "content"))
        # Redirects are siblings: (arith (word "...")) (redirect ...)
        escaped = (
            self.raw_content.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
        )
        result = '(arith (word "' + escaped + '"))'
        if self.redirects:
            redirect_parts = []
            for r in self.redirects:
                redirect_parts.append(r.to_sexp())
            redirect_sexps = " ".join(redirect_parts)
            return result + " " + redirect_sexps
        return result


# Arithmetic expression nodes


class ArithNumber(Node):
    """A numeric literal in arithmetic context."""

    value: str  # Raw string (may be hex, octal, base#n)

    def __init__(self, value: str):
        self.kind = "number"
        self.value = value

    def to_sexp(self) -> str:
        return '(number "' + self.value + '")'


class ArithVar(Node):
    """A variable reference in arithmetic context (without $)."""

    name: str

    def __init__(self, name: str):
        self.kind = "var"
        self.name = name

    def to_sexp(self) -> str:
        return '(var "' + self.name + '")'


class ArithBinaryOp(Node):
    """A binary operation in arithmetic."""

    op: str
    left: Node
    right: Node

    def __init__(self, op: str, left: Node, right: Node):
        self.kind = "binary-op"
        self.op = op
        self.left = left
        self.right = right

    def to_sexp(self) -> str:
        return (
            '(binary-op "'
            + self.op
            + '" '
            + self.left.to_sexp()
            + " "
            + self.right.to_sexp()
            + ")"
        )


class ArithUnaryOp(Node):
    """A unary operation in arithmetic."""

    op: str
    operand: Node

    def __init__(self, op: str, operand: Node):
        self.kind = "unary-op"
        self.op = op
        self.operand = operand

    def to_sexp(self) -> str:
        return '(unary-op "' + self.op + '" ' + self.operand.to_sexp() + ")"


class ArithPreIncr(Node):
    """Pre-increment ++var."""

    operand: Node

    def __init__(self, operand: Node):
        self.kind = "pre-incr"
        self.operand = operand

    def to_sexp(self) -> str:
        return "(pre-incr " + self.operand.to_sexp() + ")"


class ArithPostIncr(Node):
    """Post-increment var++."""

    operand: Node

    def __init__(self, operand: Node):
        self.kind = "post-incr"
        self.operand = operand

    def to_sexp(self) -> str:
        return "(post-incr " + self.operand.to_sexp() + ")"


class ArithPreDecr(Node):
    """Pre-decrement --var."""

    operand: Node

    def __init__(self, operand: Node):
        self.kind = "pre-decr"
        self.operand = operand

    def to_sexp(self) -> str:
        return "(pre-decr " + self.operand.to_sexp() + ")"


class ArithPostDecr(Node):
    """Post-decrement var--."""

    operand: Node

    def __init__(self, operand: Node):
        self.kind = "post-decr"
        self.operand = operand

    def to_sexp(self) -> str:
        return "(post-decr " + self.operand.to_sexp() + ")"


class ArithAssign(Node):
    """Assignment operation (=, +=, -=, etc.)."""

    op: str
    target: Node
    value: Node

    def __init__(self, op: str, target: Node, value: Node):
        self.kind = "assign"
        self.op = op
        self.target = target
        self.value = value

    def to_sexp(self) -> str:
        return (
            '(assign "'
            + self.op
            + '" '
            + self.target.to_sexp()
            + " "
            + self.value.to_sexp()
            + ")"
        )


class ArithTernary(Node):
    """Ternary conditional expr ? expr : expr."""

    condition: Node
    if_true: Node
    if_false: Node

    def __init__(self, condition: Node, if_true: Node, if_false: Node):
        self.kind = "ternary"
        self.condition = condition
        self.if_true = if_true
        self.if_false = if_false

    def to_sexp(self) -> str:
        return (
            "(ternary "
            + self.condition.to_sexp()
            + " "
            + self.if_true.to_sexp()
            + " "
            + self.if_false.to_sexp()
            + ")"
        )


class ArithComma(Node):
    """Comma operator expr, expr."""

    left: Node
    right: Node

    def __init__(self, left: Node, right: Node):
        self.kind = "comma"
        self.left = left
        self.right = right

    def to_sexp(self) -> str:
        return "(comma " + self.left.to_sexp() + " " + self.right.to_sexp() + ")"


class ArithSubscript(Node):
    """Array subscript arr[expr]."""

    array: str
    index: Node

    def __init__(self, array: str, index: Node):
        self.kind = "subscript"
        self.array = array
        self.index = index

    def to_sexp(self) -> str:
        return '(subscript "' + self.array + '" ' + self.index.to_sexp() + ")"


class ArithEscape(Node):
    """An escaped character in arithmetic expression."""

    char: str

    def __init__(self, char: str):
        self.kind = "escape"
        self.char = char

    def to_sexp(self) -> str:
        return '(escape "' + self.char + '")'


class ArithDeprecated(Node):
    """A deprecated arithmetic expansion $[expr]."""

    expression: str

    def __init__(self, expression: str):
        self.kind = "arith-deprecated"
        self.expression = expression

    def to_sexp(self) -> str:
        escaped = (
            self.expression.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
        )
        return '(arith-deprecated "' + escaped + '")'


class ArithConcat(Node):
    """A concatenation of prefix + expansion in arithmetic (e.g., 0x$var)."""

    parts: list[Node]

    def __init__(self, parts: list[Node]):
        self.kind = "arith-concat"
        self.parts = parts

    def to_sexp(self) -> str:
        sexps = []
        for p in self.parts:
            sexps.append(p.to_sexp())
        return "(arith-concat " + " ".join(sexps) + ")"


class AnsiCQuote(Node):
    """An ANSI-C quoted string $'...'."""

    content: str

    def __init__(self, content: str):
        self.kind = "ansi-c"
        self.content = content

    def to_sexp(self) -> str:
        escaped = (
            self.content.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        )
        return '(ansi-c "' + escaped + '")'


class LocaleString(Node):
    """A locale-translated string $"..."."""

    content: str

    def __init__(self, content: str):
        self.kind = "locale"
        self.content = content

    def to_sexp(self) -> str:
        escaped = (
            self.content.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        )
        return '(locale "' + escaped + '")'


class ProcessSubstitution(Node):
    """A process substitution <(...) or >(...)."""

    direction: str  # "<" for input, ">" for output
    command: Node

    def __init__(self, direction: str, command: Node):
        self.kind = "procsub"
        self.direction = direction
        self.command = command

    def to_sexp(self) -> str:
        return '(procsub "' + self.direction + '" ' + self.command.to_sexp() + ")"


class Negation(Node):
    """Pipeline negation with !."""

    pipeline: Node

    def __init__(self, pipeline: Node):
        self.kind = "negation"
        self.pipeline = pipeline

    def to_sexp(self) -> str:
        if self.pipeline is None:
            # Bare "!" with no command - bash-oracle shows empty command
            return "(negation (command))"
        return "(negation " + self.pipeline.to_sexp() + ")"


class Time(Node):
    """Time measurement with time keyword."""

    pipeline: Node
    posix: bool = False  # -p flag

    def __init__(self, pipeline: Node, posix: bool = False):
        self.kind = "time"
        self.pipeline = pipeline
        self.posix = posix

    def to_sexp(self) -> str:
        if self.pipeline is None:
            # Bare "time" with no command - bash-oracle shows empty command
            if self.posix:
                return "(time -p (command))"
            else:
                return "(time (command))"
        if self.posix:
            return "(time -p " + self.pipeline.to_sexp() + ")"
        return "(time " + self.pipeline.to_sexp() + ")"


class ConditionalExpr(Node):
    """A conditional expression [[ expression ]]."""

    body: "Node | str"  # Parsed node or raw string for backwards compat
    redirects: list[Node]

    def __init__(self, body: "Node | str", redirects: list[Node] = None):
        self.kind = "cond-expr"
        self.body = body
        if redirects is None:
            redirects = []
        self.redirects = redirects

    def to_sexp(self) -> str:
        # bash-oracle format: (cond ...) not (cond-expr ...)
        # Redirects are siblings, not children: (cond ...) (redirect ...)
        body_kind = getattr(self.body, "kind", None)
        if body_kind is None:
            # body is a string
            escaped = (
                self.body.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
            )
            result = '(cond "' + escaped + '")'
        else:
            result = "(cond " + self.body.to_sexp() + ")"
        if self.redirects:
            redirect_parts = []
            for r in self.redirects:
                redirect_parts.append(r.to_sexp())
            redirect_sexps = " ".join(redirect_parts)
            return result + " " + redirect_sexps
        return result


class UnaryTest(Node):
    """A unary test in [[ ]], e.g., -f file, -z string."""

    op: str
    operand: Word

    def __init__(self, op: str, operand: Word):
        self.kind = "unary-test"
        self.op = op
        self.operand = operand

    def to_sexp(self) -> str:
        # bash-oracle format: (cond-unary "-f" (cond-term "file"))
        # cond-term preserves content as-is (no backslash escaping)
        operand_val = self.operand.get_cond_formatted_value()
        return '(cond-unary "' + self.op + '" (cond-term "' + operand_val + '"))'


class BinaryTest(Node):
    """A binary test in [[ ]], e.g., $a == $b, file1 -nt file2."""

    op: str
    left: Word
    right: Word

    def __init__(self, op: str, left: Word, right: Word):
        self.kind = "binary-test"
        self.op = op
        self.left = left
        self.right = right

    def to_sexp(self) -> str:
        # bash-oracle format: (cond-binary "==" (cond-term "x") (cond-term "y"))
        # cond-term preserves content as-is (no backslash escaping)
        left_val = self.left.get_cond_formatted_value()
        right_val = self.right.get_cond_formatted_value()
        return (
            '(cond-binary "'
            + self.op
            + '" (cond-term "'
            + left_val
            + '") (cond-term "'
            + right_val
            + '"))'
        )


class CondAnd(Node):
    """Logical AND in [[ ]], e.g., expr1 && expr2."""

    left: Node
    right: Node

    def __init__(self, left: Node, right: Node):
        self.kind = "cond-and"
        self.left = left
        self.right = right

    def to_sexp(self) -> str:
        return "(cond-and " + self.left.to_sexp() + " " + self.right.to_sexp() + ")"


class CondOr(Node):
    """Logical OR in [[ ]], e.g., expr1 || expr2."""

    left: Node
    right: Node

    def __init__(self, left: Node, right: Node):
        self.kind = "cond-or"
        self.left = left
        self.right = right

    def to_sexp(self) -> str:
        return "(cond-or " + self.left.to_sexp() + " " + self.right.to_sexp() + ")"


class CondNot(Node):
    """Logical NOT in [[ ]], e.g., ! expr."""

    operand: Node

    def __init__(self, operand: Node):
        self.kind = "cond-not"
        self.operand = operand

    def to_sexp(self) -> str:
        # bash-oracle ignores negation - just output the operand
        return self.operand.to_sexp()


class CondParen(Node):
    """Parenthesized group in [[ ]], e.g., ( expr )."""

    inner: Node

    def __init__(self, inner: Node):
        self.kind = "cond-paren"
        self.inner = inner

    def to_sexp(self) -> str:
        return "(cond-expr " + self.inner.to_sexp() + ")"


class Array(Node):
    """An array literal (word1 word2 ...)."""

    elements: list[Word]

    def __init__(self, elements: list[Word]):
        self.kind = "array"
        self.elements = elements

    def to_sexp(self) -> str:
        if not self.elements:
            return "(array)"
        parts = []
        for e in self.elements:
            parts.append(e.to_sexp())
        inner = " ".join(parts)
        return "(array " + inner + ")"


class Coproc(Node):
    """A coprocess coproc [NAME] command."""

    command: Node
    name: str | None = None

    def __init__(self, command: Node, name: str = None):
        self.kind = "coproc"
        self.command = command
        self.name = name

    def to_sexp(self) -> str:
        # Use provided name for compound commands, "COPROC" for simple commands
        if self.name:
            name = self.name
        else:
            name = "COPROC"
        return '(coproc "' + name + '" ' + self.command.to_sexp() + ")"


def _format_cond_body(node: Node) -> str:
    """Format the body of a [[ ]] conditional expression."""
    kind = node.kind
    if kind == "unary-test":
        operand_val = node.operand.get_cond_formatted_value()
        return node.op + " " + operand_val
    if kind == "binary-test":
        left_val = node.left.get_cond_formatted_value()
        right_val = node.right.get_cond_formatted_value()
        return left_val + " " + node.op + " " + right_val
    if kind == "cond-and":
        return _format_cond_body(node.left) + " && " + _format_cond_body(node.right)
    if kind == "cond-or":
        return _format_cond_body(node.left) + " || " + _format_cond_body(node.right)
    if kind == "cond-not":
        return "! " + _format_cond_body(node.body)
    if kind == "cond-paren":
        return "( " + _format_cond_body(node.body) + " )"
    return ""


def _format_cmdsub_node(node: Node, indent: int = 0, in_procsub: bool = False) -> str:
    """Format an AST node for command substitution output (bash-oracle pretty-print format)."""
    sp = _repeat_str(" ", indent)
    inner_sp = _repeat_str(" ", indent + 4)
    if node.kind == "empty":
        return ""
    if node.kind == "command":
        parts = []
        for w in node.words:
            val = w._expand_all_ansi_c_quotes(w.value)
            # Strip $ from locale strings $"..." (quote-aware)
            val = w._strip_locale_string_dollars(val)
            val = w._format_command_substitutions(val)
            parts.append(val)
        for r in node.redirects:
            parts.append(_format_redirect(r))
        return " ".join(parts)
    if node.kind == "pipeline":
        # Build list of (cmd, needs_pipe_both_redirect) filtering out PipeBoth markers
        cmds = []
        i = 0
        while i < len(node.commands):
            cmd = node.commands[i]
            if cmd.kind == "pipe-both":
                i += 1
                continue
            # Check if next element is PipeBoth
            needs_redirect = (
                i + 1 < len(node.commands) and node.commands[i + 1].kind == "pipe-both"
            )
            cmds.append((cmd, needs_redirect))
            i += 1
        # Format pipeline, handling heredocs specially
        result_parts = []
        idx = 0
        while idx < len(cmds):
            cmd, needs_redirect = cmds[idx]
            formatted = _format_cmdsub_node(cmd, indent)
            if needs_redirect:
                formatted = formatted + " 2>&1"
            is_last = idx == len(cmds) - 1
            # Check if command has actual heredoc redirects
            has_heredoc = False
            if cmd.kind == "command" and cmd.redirects:
                for r in cmd.redirects:
                    if r.kind == "heredoc":
                        has_heredoc = True
                        break
            if not is_last and has_heredoc:
                # Heredoc present - insert pipe after heredoc delimiter, before content
                # Pattern: "... <<DELIM\ncontent\nDELIM\n" -> "... <<DELIM |\ncontent\nDELIM\n"
                first_nl = formatted.find("\n")
                if first_nl != -1:
                    formatted = formatted[:first_nl] + " |" + formatted[first_nl:]
                result_parts.append(formatted)
            else:
                result_parts.append(formatted)
            idx += 1
        # Join with " | " for commands without heredocs, or just join if heredocs handled
        result = ""
        idx = 0
        while idx < len(result_parts):
            part = result_parts[idx]
            if idx > 0:
                # If previous part ends with heredoc (newline), add indented command
                if result.endswith("\n"):
                    result = result + "  " + part
                else:
                    result = result + " | " + part
            else:
                result = part
            idx += 1
        return result
    if node.kind == "list":
        # Join commands with operators
        result = []
        for p in node.parts:
            if p.kind == "operator":
                if p.op == ";":
                    result.append(";")
                elif p.op == "\n":
                    # Skip newline if it follows a semicolon (redundant separator)
                    if result and result[len(result) - 1] == ";":
                        continue
                    result.append("\n")
                elif p.op == "&":
                    result.append(" &")
                else:
                    result.append(" " + p.op)
            else:
                if result and not result[len(result) - 1].endswith((" ", "\n")):
                    result.append(" ")
                result.append(_format_cmdsub_node(p, indent))
        # Strip trailing ; or newline
        s = "".join(result)
        while s.endswith(";") or s.endswith("\n"):
            s = _substring(s, 0, len(s) - 1)
        return s
    if node.kind == "if":
        cond = _format_cmdsub_node(node.condition, indent)
        then_body = _format_cmdsub_node(node.then_body, indent + 4)
        result = "if " + cond + "; then\n" + inner_sp + then_body + ";"
        if node.else_body:
            else_body = _format_cmdsub_node(node.else_body, indent + 4)
            result = result + "\n" + sp + "else\n" + inner_sp + else_body + ";"
        result = result + "\n" + sp + "fi"
        return result
    if node.kind == "while":
        cond = _format_cmdsub_node(node.condition, indent)
        body = _format_cmdsub_node(node.body, indent + 4)
        result = "while " + cond + "; do\n" + inner_sp + body + ";\n" + sp + "done"
        if node.redirects:
            for r in node.redirects:
                result = result + " " + _format_redirect(r)
        return result
    if node.kind == "until":
        cond = _format_cmdsub_node(node.condition, indent)
        body = _format_cmdsub_node(node.body, indent + 4)
        result = "until " + cond + "; do\n" + inner_sp + body + ";\n" + sp + "done"
        if node.redirects:
            for r in node.redirects:
                result = result + " " + _format_redirect(r)
        return result
    if node.kind == "for":
        var = node.var
        body = _format_cmdsub_node(node.body, indent + 4)
        if node.words:
            word_vals = []
            for w in node.words:
                word_vals.append(w.value)
            words = " ".join(word_vals)
            result = (
                "for "
                + var
                + " in "
                + words
                + ";\ndo\n"
                + inner_sp
                + body
                + ";\n"
                + sp
                + "done"
            )
        else:
            result = "for " + var + ";\ndo\n" + inner_sp + body + ";\n" + sp + "done"
        if node.redirects:
            for r in node.redirects:
                result = result + " " + _format_redirect(r)
        return result
    if node.kind == "for-arith":
        body = _format_cmdsub_node(node.body, indent + 4)
        result = (
            "for (("
            + node.init
            + "; "
            + node.cond
            + "; "
            + node.incr
            + "))\ndo\n"
            + inner_sp
            + body
            + ";\n"
            + sp
            + "done"
        )
        if node.redirects:
            for r in node.redirects:
                result = result + " " + _format_redirect(r)
        return result
    if node.kind == "case":
        word = node.word.value
        patterns = []
        i = 0
        while i < len(node.patterns):
            p = node.patterns[i]
            pat = p.pattern.replace("|", " | ")
            if p.body:
                body = _format_cmdsub_node(p.body, indent + 8)
            else:
                body = ""
            term = p.terminator  # ;;, ;&, or ;;&
            pat_indent = _repeat_str(" ", indent + 8)
            term_indent = _repeat_str(" ", indent + 4)
            if i == 0:
                # First pattern on same line as 'in'
                patterns.append(
                    " " + pat + ")\n" + pat_indent + body + "\n" + term_indent + term
                )
            else:
                patterns.append(
                    pat + ")\n" + pat_indent + body + "\n" + term_indent + term
                )
            i += 1
        pattern_str = ("\n" + _repeat_str(" ", indent + 4)).join(patterns)
        redirects = ""
        if node.redirects:
            redirect_parts = []
            for r in node.redirects:
                redirect_parts.append(_format_redirect(r))
            redirects = " " + " ".join(redirect_parts)
        return "case " + word + " in" + pattern_str + "\n" + sp + "esac" + redirects
    if node.kind == "function":
        name = node.name
        # Get the body content - if it's a BraceGroup, unwrap it
        inner_body = node.body.body if node.body.kind == "brace-group" else node.body
        body = _format_cmdsub_node(inner_body, indent + 4).rstrip(";")
        return f"function {name} () \n{{ \n{inner_sp}{body}\n}}"
    if node.kind == "subshell":
        body = _format_cmdsub_node(node.body, indent, in_procsub)
        redirects = ""
        if node.redirects:
            redirect_parts = []
            for r in node.redirects:
                redirect_parts.append(_format_redirect(r))
            redirects = " ".join(redirect_parts)
        if in_procsub:
            if redirects:
                return "(" + body + ") " + redirects
            return "(" + body + ")"
        if redirects:
            return "( " + body + " ) " + redirects
        return "( " + body + " )"
    if node.kind == "brace-group":
        body = _format_cmdsub_node(node.body, indent)
        body = body.rstrip(";")  # Strip trailing semicolons before adding our own
        redirects = ""
        if node.redirects:
            redirect_parts = []
            for r in node.redirects:
                redirect_parts.append(_format_redirect(r))
            redirects = " ".join(redirect_parts)
        if redirects:
            return "{ " + body + "; } " + redirects
        return "{ " + body + "; }"
    if node.kind == "arith-cmd":
        return "((" + node.raw_content + "))"
    if node.kind == "cond-expr":
        body = _format_cond_body(node.body)
        return "[[ " + body + " ]]"
    if node.kind == "negation":
        if node.pipeline:
            return "\\! " + _format_cmdsub_node(node.pipeline, indent)
        return "\\!"
    if node.kind == "time":
        prefix = "time -p " if node.posix else "time "
        if node.pipeline:
            return prefix + _format_cmdsub_node(node.pipeline, indent)
        return prefix.rstrip()
    # Fallback: return empty for unknown types
    return ""


def _format_redirect(r: "Redirect | HereDoc") -> str:
    """Format a redirect for command substitution output."""
    if r.kind == "heredoc":
        # Include heredoc content: <<DELIM\ncontent\nDELIM\n
        if r.strip_tabs:
            op = "<<-"
        else:
            op = "<<"
        if r.quoted:
            delim = "'" + r.delimiter + "'"
        else:
            delim = r.delimiter
        return op + delim + "\n" + r.content + r.delimiter + "\n"
    op = r.op
    # Normalize default fd: 1> -> >, 0< -> <
    if op == "1>":
        op = ">"
    elif op == "0<":
        op = "<"
    target = r.target.value
    # For fd duplication (target starts with &), handle normalization
    if target.startswith("&"):
        # Normalize N<&- to N>&- (close always uses >)
        if target == "&-" and op.endswith("<"):
            op = _substring(op, 0, len(op) - 1) + ">"
        # Check if target is a literal fd (digit or -)
        after_amp = _substring(target, 1, len(target))
        is_literal_fd = after_amp == "-" or (
            len(after_amp) > 0 and after_amp[0].isdigit()
        )
        if is_literal_fd:
            # Add default fd for bare >&N or <&N
            if op == ">":
                op = "1>"
            elif op == "<":
                op = "0<"
        else:
            # Variable target: use bare >& or <&
            if op == "1>":
                op = ">"
            elif op == "0<":
                op = "<"
        return op + target
    return op + " " + target


def _normalize_fd_redirects(s: str) -> str:
    """Normalize fd redirects in a raw string: >&2 -> 1>&2, <&N -> 0<&N."""
    # Match >&N or <&N not preceded by a digit, add default fd
    result = []
    i = 0
    while i < len(s):
        # Check for >&N or <&N
        if i + 2 < len(s) and s[i + 1] == "&" and s[i + 2].isdigit():
            prev_is_digit = i > 0 and s[i - 1].isdigit()
            if s[i] == ">" and not prev_is_digit:
                result.append("1>&")
                result.append(s[i + 2])
                i += 3
                continue
            elif s[i] == "<" and not prev_is_digit:
                result.append("0<&")
                result.append(s[i + 2])
                i += 3
                continue
        result.append(s[i])
        i += 1
    return "".join(result)


def _find_cmdsub_end(value: str, start: int) -> int:
    """Find the end of a $(...) command substitution, handling case statements.

    Starts after the opening $(. Returns position after the closing ).
    """
    depth = 1
    i = start
    in_single = False
    in_double = False
    case_depth = 0  # Track nested case statements
    in_case_patterns = False  # After 'in' but before first ;; or esac
    arith_depth = 0  # Track nested arithmetic expressions
    while i < len(value) and depth > 0:
        c = value[i]
        # Handle escapes
        if c == "\\" and i + 1 < len(value) and not in_single:
            i += 2
            continue
        # Handle quotes
        if c == "'" and not in_double:
            in_single = not in_single
            i += 1
            continue
        if c == '"' and not in_single:
            in_double = not in_double
            i += 1
            continue
        if in_single:
            i += 1
            continue
        if in_double:
            # Inside double quotes, $() command substitution is still active
            if _starts_with_at(value, i, "$(") and not _starts_with_at(value, i, "$(("):
                # Recursively find end of nested command substitution
                j = _find_cmdsub_end(value, i + 2)
                i = j
                continue
            # Skip other characters inside double quotes
            i += 1
            continue
        # Handle comments - skip from # to end of line
        # Only treat # as comment if preceded by whitespace or at start
        if c == "#" and (
            i == start
            or value[i - 1] == " "
            or value[i - 1] == "\t"
            or value[i - 1] == "\n"
            or value[i - 1] == ";"
            or value[i - 1] == "|"
            or value[i - 1] == "&"
            or value[i - 1] == "("
            or value[i - 1] == ")"
        ):
            while i < len(value) and value[i] != "\n":
                i += 1
            continue
        # Handle here-strings (<<< word) - must check before heredocs
        if _starts_with_at(value, i, "<<<"):
            i += 3  # Skip <<<
            # Skip whitespace
            while i < len(value) and (value[i] == " " or value[i] == "\t"):
                i += 1
            # Skip the word (may be quoted)
            if i < len(value) and value[i] == '"':
                i += 1
                while i < len(value) and value[i] != '"':
                    if value[i] == "\\" and i + 1 < len(value):
                        i += 2
                    else:
                        i += 1
                if i < len(value):
                    i += 1  # Skip closing quote
            elif i < len(value) and value[i] == "'":
                i += 1
                while i < len(value) and value[i] != "'":
                    i += 1
                if i < len(value):
                    i += 1  # Skip closing quote
            else:
                # Unquoted word - skip until whitespace or special char
                while i < len(value) and value[i] not in " \t\n;|&<>()":
                    i += 1
            continue
        # Handle arithmetic expressions $((
        if _starts_with_at(value, i, "$(("):
            arith_depth += 1
            i += 3
            continue
        # Handle arithmetic close ))
        if arith_depth > 0 and _starts_with_at(value, i, "))"):
            arith_depth -= 1
            i += 2
            continue
        # Handle heredocs (but not << inside arithmetic, which is shift operator)
        if arith_depth == 0 and _starts_with_at(value, i, "<<"):
            i = _skip_heredoc(value, i)
            continue
        # Check for 'case' keyword
        if _starts_with_at(value, i, "case") and _is_word_boundary(value, i, 4):
            case_depth += 1
            in_case_patterns = False
            i += 4
            continue
        # Check for 'in' keyword (after case)
        if (
            case_depth > 0
            and _starts_with_at(value, i, "in")
            and _is_word_boundary(value, i, 2)
        ):
            in_case_patterns = True
            i += 2
            continue
        # Check for 'esac' keyword
        if _starts_with_at(value, i, "esac") and _is_word_boundary(value, i, 4):
            if case_depth > 0:
                case_depth -= 1
                in_case_patterns = False
            i += 4
            continue
        # Check for ';;' (end of case pattern, next pattern or esac follows)
        if _starts_with_at(value, i, ";;"):
            i += 2
            continue
        # Handle parens
        if c == "(":
            # In case patterns, ( before pattern name is optional and not a grouping paren
            if not (in_case_patterns and case_depth > 0):
                depth += 1
        elif c == ")":
            # In case patterns, ) after pattern name is not a grouping paren
            if in_case_patterns and case_depth > 0:
                # This ) is a case pattern terminator, skip it
                pass
            else:
                depth -= 1
        i += 1
    return i


def _skip_heredoc(value: str, start: int) -> int:
    """Skip past a heredoc starting at <<. Returns position after heredoc content."""
    i = start + 2  # Skip <<
    # Handle <<- (strip tabs)
    if i < len(value) and value[i] == "-":
        i += 1
    # Skip whitespace before delimiter
    while i < len(value) and _is_whitespace_no_newline(value[i]):
        i += 1
    # Extract delimiter - may be quoted
    delim_start = i
    quote_char = None
    if i < len(value) and (value[i] == '"' or value[i] == "'"):
        quote_char = value[i]
        i += 1
        delim_start = i
        while i < len(value) and value[i] != quote_char:
            i += 1
        delimiter = _substring(value, delim_start, i)
        if i < len(value):
            i += 1  # Skip closing quote
    elif i < len(value) and value[i] == "\\":
        # Backslash-quoted delimiter like <<\EOF
        i += 1
        delim_start = i
        while i < len(value) and not _is_whitespace(value[i]):
            i += 1
        delimiter = _substring(value, delim_start, i)
    else:
        # Unquoted delimiter
        while i < len(value) and not _is_whitespace(value[i]):
            i += 1
        delimiter = _substring(value, delim_start, i)
    # Skip to end of line (heredoc content starts on next line)
    while i < len(value) and value[i] != "\n":
        i += 1
    if i < len(value):
        i += 1  # Skip newline
    # Find the end delimiter on its own line
    while i < len(value):
        line_start = i
        # Find end of this line
        line_end = i
        while line_end < len(value) and value[line_end] != "\n":
            line_end += 1
        line = _substring(value, line_start, line_end)
        # Check if this line is the delimiter (possibly with leading tabs for <<-)
        if start + 2 < len(value) and value[start + 2] == "-":
            stripped = line.lstrip("\t")
        else:
            stripped = line
        if stripped == delimiter:
            # Found end - return position after delimiter line
            if line_end < len(value):
                return line_end + 1
            else:
                return line_end
        if line_end < len(value):
            i = line_end + 1
        else:
            i = line_end
    return i


def _is_word_boundary(s: str, pos: int, word_len: int) -> bool:
    """Check if the word at pos is a standalone word (not part of larger word)."""
    # Check character before
    if pos > 0 and s[pos - 1].isalnum():
        return False
    # Check character after
    end = pos + word_len
    if end < len(s) and s[end].isalnum():
        return False
    return True


# Reserved words that cannot be command names
RESERVED_WORDS = {
    "if",
    "then",
    "elif",
    "else",
    "fi",
    "while",
    "until",
    "for",
    "select",
    "do",
    "done",
    "case",
    "esac",
    "in",
    "function",
    "coproc",
}

# Metacharacters that break words (unquoted)
# Note: {} are NOT metacharacters - they're only special at command position
# for brace groups. In words like {a,b,c}, braces are literal.
METACHAR = set(" \t\n|&;()<>")

COND_UNARY_OPS = {
    "-a",
    "-b",
    "-c",
    "-d",
    "-e",
    "-f",
    "-g",
    "-h",
    "-k",
    "-p",
    "-r",
    "-s",
    "-t",
    "-u",
    "-w",
    "-x",
    "-G",
    "-L",
    "-N",
    "-O",
    "-S",
    "-z",
    "-n",
    "-o",
    "-v",
    "-R",
}

COND_BINARY_OPS = {
    "==",
    "!=",
    "=~",
    "=",
    "<",
    ">",
    "-eq",
    "-ne",
    "-lt",
    "-le",
    "-gt",
    "-ge",
    "-nt",
    "-ot",
    "-ef",
}

COMPOUND_KEYWORDS = {"while", "until", "for", "if", "case", "select"}


def _is_quote(c: str) -> bool:
    return c == "'" or c == '"'


def _is_metachar(c: str) -> bool:
    return (
        c == " "
        or c == "\t"
        or c == "\n"
        or c == "|"
        or c == "&"
        or c == ";"
        or c == "("
        or c == ")"
        or c == "<"
        or c == ">"
    )


def _is_extglob_prefix(c: str) -> bool:
    return c == "@" or c == "?" or c == "*" or c == "+" or c == "!"


def _is_redirect_char(c: str) -> bool:
    return c == "<" or c == ">"


def _is_special_param(c: str) -> bool:
    return (
        c == "?" or c == "$" or c == "!" or c == "#" or c == "@" or c == "*" or c == "-"
    )


def _is_digit(c: str) -> bool:
    return c >= "0" and c <= "9"


def _is_semicolon_or_newline(c: str) -> bool:
    return c == ";" or c == "\n"


def _is_right_bracket(c: str) -> bool:
    return c == ")" or c == "}"


def _is_word_start_context(c: str) -> bool:
    """Check if char is a valid context for starting a word (whitespace or metachar except >)."""
    return (
        c == " "
        or c == "\t"
        or c == "\n"
        or c == ";"
        or c == "|"
        or c == "&"
        or c == "<"
        or c == "("
    )


def _is_word_end_context(c: str) -> bool:
    """Check if char ends a word context (whitespace or metachar)."""
    return (
        c == " "
        or c == "\t"
        or c == "\n"
        or c == ";"
        or c == "|"
        or c == "&"
        or c == "<"
        or c == ">"
        or c == "("
        or c == ")"
    )


def _is_special_param_or_digit(c: str) -> bool:
    return _is_special_param(c) or _is_digit(c)


def _is_param_expansion_op(c: str) -> bool:
    return (
        c == ":"
        or c == "-"
        or c == "="
        or c == "+"
        or c == "?"
        or c == "#"
        or c == "%"
        or c == "/"
        or c == "^"
        or c == ","
        or c == "@"
        or c == "*"
        or c == "["
    )


def _is_simple_param_op(c: str) -> bool:
    return c == "-" or c == "=" or c == "?" or c == "+"


def _is_escape_char_in_dquote(c: str) -> bool:
    return c == "$" or c == "`" or c == "\\"


def _is_list_terminator(c: str) -> bool:
    return c == "\n" or c == "|" or c == ";" or c == "(" or c == ")"


def _is_semicolon_or_amp(c: str) -> bool:
    return c == ";" or c == "&"


def _is_paren(c: str) -> bool:
    return c == "(" or c == ")"


def _is_caret_or_bang(c: str) -> bool:
    return c == "!" or c == "^"


def _is_at_or_star(c: str) -> bool:
    return c == "@" or c == "*"


def _is_digit_or_dash(c: str) -> bool:
    return _is_digit(c) or c == "-"


def _is_newline_or_right_paren(c: str) -> bool:
    return c == "\n" or c == ")"


def _is_newline_or_right_bracket(c: str) -> bool:
    return c == "\n" or c == ")" or c == "}"


def _is_semicolon_newline_brace(c: str) -> bool:
    return c == ";" or c == "\n" or c == "{"


def _str_contains(haystack: str, needle: str) -> bool:
    """Check if haystack contains needle substring."""
    return haystack.find(needle) != -1


class Parser:
    """Recursive descent parser for bash."""

    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.length = len(source)
        self._pending_heredoc_end = None

    def at_end(self) -> bool:
        """Check if we've reached the end of input."""
        return self.pos >= self.length

    def peek(self) -> str | None:
        """Return current character without consuming."""
        if self.at_end():
            return None
        return self.source[self.pos]

    def advance(self) -> str | None:
        """Consume and return current character."""
        if self.at_end():
            return None
        ch = self.source[self.pos]
        self.pos += 1
        return ch

    def skip_whitespace(self) -> None:
        """Skip spaces, tabs, comments, and backslash-newline continuations."""
        while not self.at_end():
            ch = self.peek()
            if _is_whitespace_no_newline(ch):
                self.advance()
            elif ch == "#":
                # Skip comment to end of line (but not the newline itself)
                while not self.at_end() and self.peek() != "\n":
                    self.advance()
            elif (
                ch == "\\"
                and self.pos + 1 < self.length
                and self.source[self.pos + 1] == "\n"
            ):
                # Backslash-newline is line continuation - skip both
                self.advance()
                self.advance()
            else:
                break

    def skip_whitespace_and_newlines(self) -> None:
        """Skip spaces, tabs, newlines, comments, and backslash-newline continuations."""
        while not self.at_end():
            ch = self.peek()
            if _is_whitespace(ch):
                self.advance()
                # After advancing past a newline, skip any pending heredoc content
                if ch == "\n":
                    if (
                        self._pending_heredoc_end is not None
                        and self._pending_heredoc_end > self.pos
                    ):
                        self.pos = self._pending_heredoc_end
                        self._pending_heredoc_end = None
            elif ch == "#":
                # Skip comment to end of line
                while not self.at_end() and self.peek() != "\n":
                    self.advance()
            elif (
                ch == "\\"
                and self.pos + 1 < self.length
                and self.source[self.pos + 1] == "\n"
            ):
                # Backslash-newline is line continuation - skip both
                self.advance()
                self.advance()
            else:
                break

    def _collect_redirects(self) -> list | None:
        """Collect trailing redirects after a compound command."""
        redirects = []
        while True:
            self.skip_whitespace()
            redirect = self.parse_redirect()
            if redirect is None:
                break
            redirects.append(redirect)
        return redirects if redirects else None

    def _parse_loop_body(self, context: str) -> Node:
        """Parse a loop body that can be either do/done or brace group."""
        if self.peek() == "{":
            brace = self.parse_brace_group()
            if brace is None:
                raise ParseError(
                    f"Expected brace group body in {context}", pos=self.pos
                )
            return brace.body
        if self.consume_word("do"):
            body = self.parse_list_until({"done"})
            if body is None:
                raise ParseError("Expected commands after 'do'", pos=self.pos)
            self.skip_whitespace_and_newlines()
            if not self.consume_word("done"):
                raise ParseError(f"Expected 'done' to close {context}", pos=self.pos)
            return body
        raise ParseError(f"Expected 'do' or '{{' in {context}", pos=self.pos)

    def peek_word(self) -> str | None:
        """Peek at the next word without consuming it."""
        saved_pos = self.pos
        self.skip_whitespace()

        if self.at_end() or _is_metachar(self.peek()):
            self.pos = saved_pos
            return None

        chars = []
        while not self.at_end() and not _is_metachar(self.peek()):
            ch = self.peek()
            # Stop at quotes - don't include in peek
            if _is_quote(ch):
                break
            chars.append(self.advance())

        if chars:
            word = "".join(chars)
        else:
            word = None
        self.pos = saved_pos
        return word

    def consume_word(self, expected: str) -> bool:
        """Try to consume a specific reserved word. Returns True if successful."""
        saved_pos = self.pos
        self.skip_whitespace()

        word = self.peek_word()
        if word != expected:
            self.pos = saved_pos
            return False

        # Actually consume the word
        self.skip_whitespace()
        for _ in expected:
            self.advance()
        return True

    def parse_word(self, at_command_start: bool = False) -> Word | None:
        """Parse a word token, detecting parameter expansions and command substitutions.

        at_command_start: When True, preserve spaces inside brackets for array
        assignments like a[1 + 2]=. When False, spaces break the word.
        """
        self.skip_whitespace()

        if self.at_end():
            return None

        start = self.pos
        chars = []
        parts = []
        bracket_depth = 0  # Track [...] for array subscripts
        seen_equals = False  # Track if we've seen = (for array assignment detection)

        while not self.at_end():
            ch = self.peek()

            # Track bracket depth for array subscripts like a[1+2]=3
            # Inside brackets, metacharacters like | and ( are literal
            # Only track [ after we've seen some chars (so [ -f file ] still works)
            # Only at command start (array assignments), not in argument position
            # Only BEFORE = sign (key=1],a[1 should not track the [1 part)
            # Only after identifier char (not [[ which is conditional keyword)
            if ch == "[" and chars and at_command_start and not seen_equals:
                prev_char = chars[len(chars) - 1]
                if prev_char.isalnum() or (prev_char == "_" or prev_char == "]"):
                    bracket_depth += 1
                    chars.append(self.advance())
                    continue
            if ch == "]" and bracket_depth > 0:
                bracket_depth -= 1
                chars.append(self.advance())
                continue
            if ch == "=" and bracket_depth == 0:
                seen_equals = True

            # Single-quoted string - no expansion
            if ch == "'":
                self.advance()  # consume opening quote
                chars.append("'")
                while not self.at_end() and self.peek() != "'":
                    chars.append(self.advance())
                if self.at_end():
                    raise ParseError("Unterminated single quote", pos=start)
                chars.append(self.advance())  # consume closing quote

            # Double-quoted string - expansions happen inside
            elif ch == '"':
                self.advance()  # consume opening quote
                chars.append('"')
                while not self.at_end() and self.peek() != '"':
                    c = self.peek()
                    # Handle escape sequences in double quotes
                    if c == "\\" and self.pos + 1 < self.length:
                        next_c = self.source[self.pos + 1]
                        if next_c == "\n":
                            # Line continuation - skip both backslash and newline
                            self.advance()
                            self.advance()
                        else:
                            chars.append(self.advance())  # backslash
                            chars.append(self.advance())  # escaped char
                    # Handle arithmetic expansion $((...))
                    elif (
                        c == "$"
                        and self.pos + 2 < self.length
                        and self.source[self.pos + 1] == "("
                        and self.source[self.pos + 2] == "("
                    ):
                        arith_result = self._parse_arithmetic_expansion()
                        arith_node = arith_result[0]
                        arith_text = arith_result[1]
                        if arith_node:
                            parts.append(arith_node)
                            chars.append(arith_text)
                        else:
                            # Not arithmetic - try command substitution
                            cmdsub_result = self._parse_command_substitution()
                            cmdsub_node = cmdsub_result[0]
                            cmdsub_text = cmdsub_result[1]
                            if cmdsub_node:
                                parts.append(cmdsub_node)
                                chars.append(cmdsub_text)
                            else:
                                chars.append(self.advance())
                    # Handle deprecated arithmetic expansion $[expr]
                    elif (
                        c == "$"
                        and self.pos + 1 < self.length
                        and self.source[self.pos + 1] == "["
                    ):
                        arith_result = self._parse_deprecated_arithmetic()
                        arith_node = arith_result[0]
                        arith_text = arith_result[1]
                        if arith_node:
                            parts.append(arith_node)
                            chars.append(arith_text)
                        else:
                            chars.append(self.advance())
                    # Handle command substitution $(...)
                    elif (
                        c == "$"
                        and self.pos + 1 < self.length
                        and self.source[self.pos + 1] == "("
                    ):
                        cmdsub_result = self._parse_command_substitution()
                        cmdsub_node = cmdsub_result[0]
                        cmdsub_text = cmdsub_result[1]
                        if cmdsub_node:
                            parts.append(cmdsub_node)
                            chars.append(cmdsub_text)
                        else:
                            chars.append(self.advance())
                    # Handle parameter expansion inside double quotes
                    elif c == "$":
                        param_result = self._parse_param_expansion()
                        param_node = param_result[0]
                        param_text = param_result[1]
                        if param_node:
                            parts.append(param_node)
                            chars.append(param_text)
                        else:
                            chars.append(self.advance())  # just $
                    # Handle backtick command substitution
                    elif c == "`":
                        cmdsub_result = self._parse_backtick_substitution()
                        cmdsub_node = cmdsub_result[0]
                        cmdsub_text = cmdsub_result[1]
                        if cmdsub_node:
                            parts.append(cmdsub_node)
                            chars.append(cmdsub_text)
                        else:
                            chars.append(self.advance())
                    else:
                        chars.append(self.advance())
                if self.at_end():
                    raise ParseError("Unterminated double quote", pos=start)
                chars.append(self.advance())  # consume closing quote

            # Escape outside quotes
            elif ch == "\\" and self.pos + 1 < self.length:
                next_ch = self.source[self.pos + 1]
                if next_ch == "\n":
                    # Line continuation - skip both backslash and newline
                    self.advance()
                    self.advance()
                else:
                    chars.append(self.advance())  # backslash
                    chars.append(self.advance())  # escaped char

            # ANSI-C quoting $'...'
            elif (
                ch == "$"
                and self.pos + 1 < self.length
                and self.source[self.pos + 1] == "'"
            ):
                ansi_result = self._parse_ansi_c_quote()
                ansi_node = ansi_result[0]
                ansi_text = ansi_result[1]
                if ansi_node:
                    parts.append(ansi_node)
                    chars.append(ansi_text)
                else:
                    chars.append(self.advance())

            # Locale translation $"..."
            elif (
                ch == "$"
                and self.pos + 1 < self.length
                and self.source[self.pos + 1] == '"'
            ):
                locale_result = self._parse_locale_string()
                locale_node = locale_result[0]
                locale_text = locale_result[1]
                inner_parts = locale_result[2]
                if locale_node:
                    parts.append(locale_node)
                    parts.extend(inner_parts)
                    chars.append(locale_text)
                else:
                    chars.append(self.advance())

            # Arithmetic expansion $((...)) - try before command substitution
            # If it fails (returns None), fall through to command substitution
            elif (
                ch == "$"
                and self.pos + 2 < self.length
                and self.source[self.pos + 1] == "("
                and self.source[self.pos + 2] == "("
            ):
                arith_result = self._parse_arithmetic_expansion()
                arith_node = arith_result[0]
                arith_text = arith_result[1]
                if arith_node:
                    parts.append(arith_node)
                    chars.append(arith_text)
                else:
                    # Not arithmetic (e.g., '$( ( ... ) )' is command sub + subshell)
                    cmdsub_result = self._parse_command_substitution()
                    cmdsub_node = cmdsub_result[0]
                    cmdsub_text = cmdsub_result[1]
                    if cmdsub_node:
                        parts.append(cmdsub_node)
                        chars.append(cmdsub_text)
                    else:
                        chars.append(self.advance())

            # Deprecated arithmetic expansion $[expr]
            elif (
                ch == "$"
                and self.pos + 1 < self.length
                and self.source[self.pos + 1] == "["
            ):
                arith_result = self._parse_deprecated_arithmetic()
                arith_node = arith_result[0]
                arith_text = arith_result[1]
                if arith_node:
                    parts.append(arith_node)
                    chars.append(arith_text)
                else:
                    chars.append(self.advance())

            # Command substitution $(...)
            elif (
                ch == "$"
                and self.pos + 1 < self.length
                and self.source[self.pos + 1] == "("
            ):
                cmdsub_result = self._parse_command_substitution()
                cmdsub_node = cmdsub_result[0]
                cmdsub_text = cmdsub_result[1]
                if cmdsub_node:
                    parts.append(cmdsub_node)
                    chars.append(cmdsub_text)
                else:
                    chars.append(self.advance())

            # Parameter expansion $var or ${...}
            elif ch == "$":
                param_result = self._parse_param_expansion()
                param_node = param_result[0]
                param_text = param_result[1]
                if param_node:
                    parts.append(param_node)
                    chars.append(param_text)
                else:
                    chars.append(self.advance())  # just $

            # Backtick command substitution
            elif ch == "`":
                cmdsub_result = self._parse_backtick_substitution()
                cmdsub_node = cmdsub_result[0]
                cmdsub_text = cmdsub_result[1]
                if cmdsub_node:
                    parts.append(cmdsub_node)
                    chars.append(cmdsub_text)
                else:
                    chars.append(self.advance())

            # Process substitution <(...) or >(...)
            elif (
                _is_redirect_char(ch)
                and self.pos + 1 < self.length
                and self.source[self.pos + 1] == "("
            ):
                procsub_result = self._parse_process_substitution()
                procsub_node = procsub_result[0]
                procsub_text = procsub_result[1]
                if procsub_node:
                    parts.append(procsub_node)
                    chars.append(procsub_text)
                else:
                    # Not a process substitution, treat as metacharacter
                    break

            # Array literal: name=(elements) or name+=(elements)
            elif (
                ch == "("
                and chars
                and (
                    chars[len(chars) - 1] == "="
                    or (
                        len(chars) >= 2
                        and chars[len(chars) - 2] == "+"
                        and chars[len(chars) - 1] == "="
                    )
                )
            ):
                array_result = self._parse_array_literal()
                array_node = array_result[0]
                array_text = array_result[1]
                if array_node:
                    parts.append(array_node)
                    chars.append(array_text)
                else:
                    # Unexpected: ( without matching )
                    break

            # Extglob pattern @(), ?(), *(), +(), !()
            elif (
                _is_extglob_prefix(ch)
                and self.pos + 1 < self.length
                and self.source[self.pos + 1] == "("
            ):
                chars.append(self.advance())  # @, ?, *, +, or !
                chars.append(self.advance())  # (
                extglob_depth = 1
                while not self.at_end() and extglob_depth > 0:
                    c = self.peek()
                    if c == ")":
                        chars.append(self.advance())
                        extglob_depth -= 1
                    elif c == "(":
                        chars.append(self.advance())
                        extglob_depth += 1
                    elif c == "\\":
                        chars.append(self.advance())
                        if not self.at_end():
                            chars.append(self.advance())
                    elif c == "'":
                        chars.append(self.advance())
                        while not self.at_end() and self.peek() != "'":
                            chars.append(self.advance())
                        if not self.at_end():
                            chars.append(self.advance())
                    elif c == '"':
                        chars.append(self.advance())
                        while not self.at_end() and self.peek() != '"':
                            if self.peek() == "\\" and self.pos + 1 < self.length:
                                chars.append(self.advance())
                            chars.append(self.advance())
                        if not self.at_end():
                            chars.append(self.advance())
                    elif (
                        c == "$"
                        and self.pos + 1 < self.length
                        and self.source[self.pos + 1] == "("
                    ):
                        # $() or $(()) inside extglob
                        chars.append(self.advance())  # $
                        chars.append(self.advance())  # (
                        if not self.at_end() and self.peek() == "(":
                            # $(()) arithmetic
                            chars.append(self.advance())  # second (
                            paren_depth = 2
                            while not self.at_end() and paren_depth > 0:
                                pc = self.peek()
                                if pc == "(":
                                    paren_depth += 1
                                elif pc == ")":
                                    paren_depth -= 1
                                chars.append(self.advance())
                        else:
                            # $() command sub - count as nested paren
                            extglob_depth += 1
                    elif (
                        _is_extglob_prefix(c)
                        and self.pos + 1 < self.length
                        and self.source[self.pos + 1] == "("
                    ):
                        # Nested extglob
                        chars.append(self.advance())  # @, ?, *, +, or !
                        chars.append(self.advance())  # (
                        extglob_depth += 1
                    else:
                        chars.append(self.advance())

            # Metacharacter ends the word (unless inside brackets like a[x|y]=1)
            elif _is_metachar(ch) and bracket_depth == 0:
                break

            # Regular character (including metacharacters inside brackets)
            else:
                chars.append(self.advance())

        if not chars:
            return None

        if parts:
            return Word("".join(chars), parts)
        else:
            return Word("".join(chars), None)

    def _parse_command_substitution(self) -> tuple[Node | None, str]:
        """Parse a $(...) command substitution.

        Returns (node, text) where node is CommandSubstitution and text is raw text.
        """
        if self.at_end() or self.peek() != "$":
            return None, ""

        start = self.pos
        self.advance()  # consume $

        if self.at_end() or self.peek() != "(":
            self.pos = start
            return None, ""

        self.advance()  # consume (

        # Find matching closing paren, being aware of:
        # - Nested $() and plain ()
        # - Quoted strings
        # - case statements (where ) after pattern isn't a closer)
        content_start = self.pos
        depth = 1
        case_depth = 0  # Track nested case statements
        arith_depth = 0  # Track nested arithmetic expressions

        while not self.at_end() and depth > 0:
            c = self.peek()

            # Single-quoted string - no special chars inside
            if c == "'":
                self.advance()
                while not self.at_end() and self.peek() != "'":
                    self.advance()
                if not self.at_end():
                    self.advance()
                continue

            # Double-quoted string - handle escapes and nested $()
            if c == '"':
                self.advance()
                while not self.at_end() and self.peek() != '"':
                    if self.peek() == "\\" and self.pos + 1 < self.length:
                        self.advance()
                        self.advance()
                    elif (
                        self.peek() == "$"
                        and self.pos + 1 < self.length
                        and self.source[self.pos + 1] == "("
                    ):
                        # Nested $() in double quotes - recurse to find matching )
                        # Command substitution creates new quoting context
                        self.advance()  # $
                        self.advance()  # (
                        nested_depth = 1
                        while not self.at_end() and nested_depth > 0:
                            nc = self.peek()
                            if nc == "'":
                                self.advance()
                                while not self.at_end() and self.peek() != "'":
                                    self.advance()
                                if not self.at_end():
                                    self.advance()
                            elif nc == '"':
                                self.advance()
                                while not self.at_end() and self.peek() != '"':
                                    if (
                                        self.peek() == "\\"
                                        and self.pos + 1 < self.length
                                    ):
                                        self.advance()
                                    self.advance()
                                if not self.at_end():
                                    self.advance()
                            elif nc == "\\" and self.pos + 1 < self.length:
                                self.advance()
                                self.advance()
                            elif (
                                nc == "$"
                                and self.pos + 1 < self.length
                                and self.source[self.pos + 1] == "("
                            ):
                                self.advance()
                                self.advance()
                                nested_depth += 1
                            elif nc == "(":
                                nested_depth += 1
                                self.advance()
                            elif nc == ")":
                                nested_depth -= 1
                                if nested_depth > 0:
                                    self.advance()
                            else:
                                self.advance()
                        if nested_depth == 0:
                            self.advance()  # consume the closing )
                    else:
                        self.advance()
                if not self.at_end():
                    self.advance()
                continue

            # Backslash escape
            if c == "\\" and self.pos + 1 < self.length:
                self.advance()
                self.advance()
                continue

            # Comment - skip until newline
            if c == "#" and self._is_word_boundary_before():
                while not self.at_end() and self.peek() != "\n":
                    self.advance()
                continue

            # Handle arithmetic expressions $((
            if (
                c == "$"
                and self.pos + 2 < self.length
                and self.source[self.pos + 1] == "("
                and self.source[self.pos + 2] == "("
            ):
                arith_depth += 1
                self.advance()  # $
                self.advance()  # (
                self.advance()  # (
                continue

            # Handle arithmetic close ))
            if (
                arith_depth > 0
                and c == ")"
                and self.pos + 1 < self.length
                and self.source[self.pos + 1] == ")"
            ):
                arith_depth -= 1
                self.advance()  # )
                self.advance()  # )
                continue

            # Heredoc - skip until delimiter line is found (not inside arithmetic)
            if (
                arith_depth == 0
                and c == "<"
                and self.pos + 1 < self.length
                and self.source[self.pos + 1] == "<"
            ):
                self.advance()  # first <
                self.advance()  # second <
                # Check for <<- (strip tabs)
                if not self.at_end() and self.peek() == "-":
                    self.advance()
                # Skip whitespace before delimiter
                while not self.at_end() and _is_whitespace_no_newline(self.peek()):
                    self.advance()
                # Parse delimiter (handle quoting)
                delimiter_chars = []
                if not self.at_end():
                    ch = self.peek()
                    if _is_quote(ch):
                        quote = self.advance()
                        while not self.at_end() and self.peek() != quote:
                            delimiter_chars.append(self.advance())
                        if not self.at_end():
                            self.advance()  # closing quote
                    elif ch == "\\":
                        self.advance()
                        # Backslash quotes - first char can be special, then read word
                        if not self.at_end():
                            delimiter_chars.append(self.advance())
                        while not self.at_end() and not _is_metachar(self.peek()):
                            delimiter_chars.append(self.advance())
                    else:
                        # Unquoted delimiter with possible embedded quotes
                        while not self.at_end() and not _is_metachar(self.peek()):
                            ch = self.peek()
                            if _is_quote(ch):
                                quote = self.advance()
                                while not self.at_end() and self.peek() != quote:
                                    delimiter_chars.append(self.advance())
                                if not self.at_end():
                                    self.advance()
                            elif ch == "\\":
                                self.advance()
                                if not self.at_end():
                                    delimiter_chars.append(self.advance())
                            else:
                                delimiter_chars.append(self.advance())
                delimiter = "".join(delimiter_chars)
                if delimiter:
                    # Skip to end of current line
                    while not self.at_end() and self.peek() != "\n":
                        self.advance()
                    # Skip newline
                    if not self.at_end() and self.peek() == "\n":
                        self.advance()
                    # Skip lines until we find the delimiter
                    while not self.at_end():
                        line_start = self.pos
                        line_end = self.pos
                        while line_end < self.length and self.source[line_end] != "\n":
                            line_end += 1
                        line = _substring(self.source, line_start, line_end)
                        # Move position to end of line
                        self.pos = line_end
                        # Check if this line matches delimiter
                        check_line = line.lstrip("\t")
                        if check_line == delimiter:
                            # Skip newline after delimiter
                            if not self.at_end() and self.peek() == "\n":
                                self.advance()
                            break
                        # Also check for delimiter followed by ) which closes cmdsub
                        if (
                            check_line.startswith(delimiter)
                            and len(check_line) > len(delimiter)
                            and check_line[len(delimiter)] == ")"
                        ):
                            # Position parser at the ) so it closes the cmdsub
                            tabs_stripped = len(line) - len(check_line)
                            self.pos = line_start + tabs_stripped + len(delimiter)
                            break
                        # Skip newline and continue
                        if not self.at_end() and self.peek() == "\n":
                            self.advance()
                continue

            # Track case/esac for pattern terminator handling
            # Check for 'case' keyword (word boundary: preceded by space/newline/start)
            if c == "c" and self._is_word_boundary_before():
                if self._lookahead_keyword("case"):
                    case_depth += 1
                    self._skip_keyword("case")
                    continue

            # Check for 'esac' keyword
            if c == "e" and self._is_word_boundary_before() and case_depth > 0:
                if self._lookahead_keyword("esac"):
                    case_depth -= 1
                    self._skip_keyword("esac")
                    continue

            # Handle parentheses
            if c == "(":
                depth += 1
            elif c == ")":
                # In case statement, ) after pattern is a terminator, not a paren
                # Only decrement depth if we're not in a case pattern position
                if case_depth > 0 and depth == 1:
                    # This ) might be a case pattern terminator, not closing the $(
                    # Look ahead to see if there's still content that needs esac
                    saved = self.pos
                    self.advance()  # skip this )
                    # Scan ahead to see if we find esac that closes our case
                    # before finding a ) that could close our $(
                    temp_depth = 0
                    temp_case_depth = case_depth  # Track nested cases in lookahead
                    found_esac = False
                    while not self.at_end():
                        tc = self.peek()
                        if tc == "'" or tc == '"':
                            # Skip quoted strings
                            q = tc
                            self.advance()
                            while not self.at_end() and self.peek() != q:
                                if q == '"' and self.peek() == "\\":
                                    self.advance()
                                self.advance()
                            if not self.at_end():
                                self.advance()
                        elif (
                            tc == "c"
                            and self._is_word_boundary_before()
                            and self._lookahead_keyword("case")
                        ):
                            # Nested case in lookahead
                            temp_case_depth += 1
                            self._skip_keyword("case")
                        elif (
                            tc == "e"
                            and self._is_word_boundary_before()
                            and self._lookahead_keyword("esac")
                        ):
                            temp_case_depth -= 1
                            if temp_case_depth == 0:
                                # All cases are closed
                                found_esac = True
                                break
                            self._skip_keyword("esac")
                        elif tc == "(":
                            temp_depth += 1
                            self.advance()
                        elif tc == ")":
                            # In case, ) is a pattern terminator, not a closer
                            if temp_case_depth > 0:
                                self.advance()
                            elif temp_depth > 0:
                                temp_depth -= 1
                                self.advance()
                            else:
                                # Found a ) that could be our closer
                                break
                        else:
                            self.advance()
                    self.pos = saved
                    if found_esac:
                        # This ) is a case pattern terminator, not our closer
                        self.advance()
                        continue
                depth -= 1

            if depth > 0:
                self.advance()

        if depth != 0:
            self.pos = start
            return None, ""

        content = _substring(self.source, content_start, self.pos)
        self.advance()  # consume final )

        text = _substring(self.source, start, self.pos)

        # Parse the content as a command list
        sub_parser = Parser(content)
        cmd = sub_parser.parse_list()
        if cmd is None:
            cmd = Empty()

        # Ensure all content was consumed - if not, there's a syntax error
        sub_parser.skip_whitespace_and_newlines()
        if not sub_parser.at_end():
            raise ParseError("Unexpected content in command substitution", pos=start)

        return CommandSubstitution(cmd), text

    def _is_word_boundary_before(self) -> bool:
        """Check if current position is at a word boundary (preceded by space/newline/start)."""
        if self.pos == 0:
            return True
        prev = self.source[self.pos - 1]
        return _is_word_start_context(prev)

    def _is_assignment_word(self, word: "Word") -> bool:
        """Check if a word is an assignment (contains = outside of quotes)."""
        in_single = False
        in_double = False
        i = 0
        while i < len(word.value):
            ch = word.value[i]
            if ch == "'" and not in_double:
                in_single = not in_single
            elif ch == '"' and not in_single:
                in_double = not in_double
            elif ch == "\\" and not in_single and i + 1 < len(word.value):
                i += 1  # Skip next char
                continue
            elif ch == "=" and not in_single and not in_double:
                return True
            i += 1
        return False

    def _lookahead_keyword(self, keyword: str) -> bool:
        """Check if keyword appears at current position followed by word boundary."""
        if self.pos + len(keyword) > self.length:
            return False
        if not _starts_with_at(self.source, self.pos, keyword):
            return False
        # Check word boundary after keyword
        after_pos = self.pos + len(keyword)
        if after_pos >= self.length:
            return True
        after = self.source[after_pos]
        return _is_word_end_context(after)

    def _skip_keyword(self, keyword: str) -> None:
        """Skip over a keyword."""
        for _ in keyword:
            self.advance()

    def _parse_backtick_substitution(self) -> tuple[Node | None, str]:
        """Parse a `...` command substitution.

        Returns (node, text) where node is CommandSubstitution and text is raw text.
        """
        if self.at_end() or self.peek() != "`":
            return None, ""

        start = self.pos
        self.advance()  # consume opening `

        # Find closing backtick, processing escape sequences as we go.
        # In backticks, backslash is special only before $, `, \, or newline.
        # \$ -> $, \` -> `, \\ -> \, \<newline> -> removed (line continuation)
        # other \X -> \X (backslash is literal)
        # content_chars: what gets parsed as the inner command
        # text_chars: what appears in the word representation (with line continuations removed)
        content_chars = []
        text_chars = ["`"]  # opening backtick
        while not self.at_end() and self.peek() != "`":
            c = self.peek()
            if c == "\\" and self.pos + 1 < self.length:
                next_c = self.source[self.pos + 1]
                if next_c == "\n":
                    # Line continuation: skip both backslash and newline
                    self.advance()  # skip \
                    self.advance()  # skip newline
                    # Don't add to content_chars or text_chars
                elif _is_escape_char_in_dquote(next_c):
                    # Escape sequence: skip backslash in content, keep both in text
                    self.advance()  # skip \
                    escaped = self.advance()
                    content_chars.append(escaped)
                    text_chars.append("\\")
                    text_chars.append(escaped)
                else:
                    # Backslash is literal before other characters
                    ch = self.advance()
                    content_chars.append(ch)
                    text_chars.append(ch)
            else:
                ch = self.advance()
                content_chars.append(ch)
                text_chars.append(ch)

        if self.at_end():
            self.pos = start
            return None, ""

        self.advance()  # consume closing `
        text_chars.append("`")  # closing backtick
        text = "".join(text_chars)
        content = "".join(content_chars)

        # Parse the content as a command list
        sub_parser = Parser(content)
        cmd = sub_parser.parse_list()
        if cmd is None:
            cmd = Empty()

        return CommandSubstitution(cmd), text

    def _parse_process_substitution(self) -> tuple[Node | None, str]:
        """Parse a <(...) or >(...) process substitution.

        Returns (node, text) where node is ProcessSubstitution and text is raw text.
        """
        if self.at_end() or not _is_redirect_char(self.peek()):
            return None, ""

        start = self.pos
        direction = self.advance()  # consume < or >

        if self.at_end() or self.peek() != "(":
            self.pos = start
            return None, ""

        self.advance()  # consume (

        # Find matching ) - track nested parens and handle quotes
        content_start = self.pos
        depth = 1

        while not self.at_end() and depth > 0:
            c = self.peek()

            # Single-quoted string
            if c == "'":
                self.advance()
                while not self.at_end() and self.peek() != "'":
                    self.advance()
                if not self.at_end():
                    self.advance()
                continue

            # Double-quoted string
            if c == '"':
                self.advance()
                while not self.at_end() and self.peek() != '"':
                    if self.peek() == "\\" and self.pos + 1 < self.length:
                        self.advance()
                    self.advance()
                if not self.at_end():
                    self.advance()
                continue

            # Backslash escape
            if c == "\\" and self.pos + 1 < self.length:
                self.advance()
                self.advance()
                continue

            # Nested parentheses (including nested process substitutions)
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    break

            self.advance()

        if depth != 0:
            self.pos = start
            return None, ""

        content = _substring(self.source, content_start, self.pos)
        self.advance()  # consume final )

        text = _substring(self.source, start, self.pos)

        # Parse the content as a command list
        sub_parser = Parser(content)
        cmd = sub_parser.parse_list()
        if cmd is None:
            cmd = Empty()

        return ProcessSubstitution(direction, cmd), text

    def _parse_array_literal(self) -> tuple[Node | None, str]:
        """Parse an array literal (word1 word2 ...).

        Returns (node, text) where node is Array and text is raw text.
        Called when positioned at the opening '(' after '=' or '+='.
        """
        if self.at_end() or self.peek() != "(":
            return None, ""

        start = self.pos
        self.advance()  # consume (

        elements = []

        while True:
            # Skip whitespace, newlines, and comments between elements
            self.skip_whitespace_and_newlines()

            if self.at_end():
                raise ParseError("Unterminated array literal", pos=start)

            if self.peek() == ")":
                break

            # Parse an element word
            word = self.parse_word()
            if word is None:
                # Might be a closing paren or error
                if self.peek() == ")":
                    break
                raise ParseError("Expected word in array literal", pos=self.pos)

            elements.append(word)

        if self.at_end() or self.peek() != ")":
            raise ParseError("Expected ) to close array literal", pos=self.pos)
        self.advance()  # consume )

        text = _substring(self.source, start, self.pos)
        return Array(elements), text

    def _parse_arithmetic_expansion(self) -> tuple[Node | None, str]:
        """Parse a $((...)) arithmetic expansion with parsed internals.

        Returns (node, text) where node is ArithmeticExpansion and text is raw text.
        Returns (None, "") if this is not arithmetic expansion (e.g., $( ( ... ) )
        which is command substitution containing a subshell).
        """
        if self.at_end() or self.peek() != "$":
            return None, ""

        start = self.pos

        # Check for $((
        if (
            self.pos + 2 >= self.length
            or self.source[self.pos + 1] != "("
            or self.source[self.pos + 2] != "("
        ):
            return None, ""

        self.advance()  # consume $
        self.advance()  # consume first (
        self.advance()  # consume second (

        # Find matching )) - need to track nested parens
        # Must be )) with no space between - ') )' is command sub + subshell
        content_start = self.pos
        depth = 1  # We're inside one level of (( already

        while not self.at_end() and depth > 0:
            c = self.peek()

            if c == "(":
                depth += 1
                self.advance()
            elif c == ")":
                # Check for ))
                if (
                    depth == 1
                    and self.pos + 1 < self.length
                    and self.source[self.pos + 1] == ")"
                ):
                    # Found the closing ))
                    break
                depth -= 1
                if depth == 0:
                    # Closed with ) but next isn't ) - this is $( ( ... ) )
                    self.pos = start
                    return None, ""
                self.advance()
            else:
                self.advance()

        if self.at_end() or depth != 1:
            self.pos = start
            return None, ""

        content = _substring(self.source, content_start, self.pos)
        self.advance()  # consume first )
        self.advance()  # consume second )

        text = _substring(self.source, start, self.pos)

        # Parse the arithmetic expression
        expr = self._parse_arith_expr(content)
        return ArithmeticExpansion(expr), text

    # ========== Arithmetic expression parser ==========
    # Operator precedence (lowest to highest):
    # 1. comma (,)
    # 2. assignment (= += -= *= /= %= <<= >>= &= ^= |=)
    # 3. ternary (? :)
    # 4. logical or (||)
    # 5. logical and (&&)
    # 6. bitwise or (|)
    # 7. bitwise xor (^)
    # 8. bitwise and (&)
    # 9. equality (== !=)
    # 10. comparison (< > <= >=)
    # 11. shift (<< >>)
    # 12. addition (+ -)
    # 13. multiplication (* / %)
    # 14. exponentiation (**)
    # 15. unary (! ~ + - ++ --)
    # 16. postfix (++ -- [])

    def _parse_arith_expr(self, content: str) -> Node | None:
        """Parse an arithmetic expression string into AST nodes."""
        # Save any existing arith context (for nested parsing)
        saved_arith_src = getattr(self, "_arith_src", None)
        saved_arith_pos = getattr(self, "_arith_pos", None)
        saved_arith_len = getattr(self, "_arith_len", None)

        self._arith_src = content
        self._arith_pos = 0
        self._arith_len = len(content)
        self._arith_skip_ws()
        if self._arith_at_end():
            result = None
        else:
            result = self._arith_parse_comma()

        # Restore previous arith context
        if saved_arith_src is not None:
            self._arith_src = saved_arith_src
            self._arith_pos = saved_arith_pos
            self._arith_len = saved_arith_len

        return result

    def _arith_at_end(self) -> bool:
        return self._arith_pos >= self._arith_len

    def _arith_peek(self, offset: int = 0) -> str:
        pos = self._arith_pos + offset
        if pos >= self._arith_len:
            return ""
        return self._arith_src[pos]

    def _arith_advance(self) -> str:
        if self._arith_at_end():
            return ""
        c = self._arith_src[self._arith_pos]
        self._arith_pos += 1
        return c

    def _arith_skip_ws(self) -> None:
        while not self._arith_at_end():
            c = self._arith_src[self._arith_pos]
            if _is_whitespace(c):
                self._arith_pos += 1
            elif (
                c == "\\"
                and self._arith_pos + 1 < self._arith_len
                and self._arith_src[self._arith_pos + 1] == "\n"
            ):
                # Backslash-newline continuation
                self._arith_pos += 2
            else:
                break

    def _arith_match(self, s: str) -> bool:
        """Check if the next characters match s (without consuming)."""
        return _starts_with_at(self._arith_src, self._arith_pos, s)

    def _arith_consume(self, s: str) -> bool:
        """If next chars match s, consume them and return True."""
        if self._arith_match(s):
            self._arith_pos += len(s)
            return True
        return False

    def _arith_parse_comma(self) -> Node:
        """Parse comma expressions (lowest precedence)."""
        left = self._arith_parse_assign()
        while True:
            self._arith_skip_ws()
            if self._arith_consume(","):
                self._arith_skip_ws()
                right = self._arith_parse_assign()
                left = ArithComma(left, right)
            else:
                break
        return left

    def _arith_parse_assign(self) -> Node:
        """Parse assignment expressions (right associative)."""
        left = self._arith_parse_ternary()
        self._arith_skip_ws()
        # Check for assignment operators
        assign_ops = ["<<=", ">>=", "+=", "-=", "*=", "/=", "%=", "&=", "^=", "|=", "="]
        for op in assign_ops:
            if self._arith_match(op):
                # Make sure it's not == or !=
                if op == "=" and self._arith_peek(1) == "=":
                    break
                self._arith_consume(op)
                self._arith_skip_ws()
                right = self._arith_parse_assign()  # right associative
                return ArithAssign(op, left, right)
        return left

    def _arith_parse_ternary(self) -> Node:
        """Parse ternary conditional (right associative)."""
        cond = self._arith_parse_logical_or()
        self._arith_skip_ws()
        if self._arith_consume("?"):
            self._arith_skip_ws()
            # True branch can be empty (e.g., 4 ? : $A - invalid at runtime, valid syntax)
            if self._arith_match(":"):
                if_true = None
            else:
                if_true = self._arith_parse_assign()
            self._arith_skip_ws()
            # Check for : (may be missing in malformed expressions like 1 ? 20)
            if self._arith_consume(":"):
                self._arith_skip_ws()
                # False branch can be empty (e.g., 4 ? 20 : - invalid at runtime)
                if self._arith_at_end() or self._arith_peek() == ")":
                    if_false = None
                else:
                    if_false = self._arith_parse_ternary()
            else:
                if_false = None
            return ArithTernary(cond, if_true, if_false)
        return cond

    def _arith_parse_left_assoc(self, ops: list, parsefn) -> Node:
        """Parse left-associative binary operators using match/consume."""
        left = parsefn()
        while True:
            self._arith_skip_ws()
            matched = False
            for op in ops:
                if self._arith_match(op):
                    self._arith_consume(op)
                    self._arith_skip_ws()
                    left = ArithBinaryOp(op, left, parsefn())
                    matched = True
                    break
            if not matched:
                break
        return left

    def _arith_parse_logical_or(self) -> Node:
        """Parse logical or (||)."""
        return self._arith_parse_left_assoc(["||"], self._arith_parse_logical_and)

    def _arith_parse_logical_and(self) -> Node:
        """Parse logical and (&&)."""
        return self._arith_parse_left_assoc(["&&"], self._arith_parse_bitwise_or)

    def _arith_parse_bitwise_or(self) -> Node:
        """Parse bitwise or (|)."""
        left = self._arith_parse_bitwise_xor()
        while True:
            self._arith_skip_ws()
            # Make sure it's not || or |=
            if self._arith_peek() == "|" and (
                self._arith_peek(1) != "|" and self._arith_peek(1) != "="
            ):
                self._arith_advance()
                self._arith_skip_ws()
                right = self._arith_parse_bitwise_xor()
                left = ArithBinaryOp("|", left, right)
            else:
                break
        return left

    def _arith_parse_bitwise_xor(self) -> Node:
        """Parse bitwise xor (^)."""
        left = self._arith_parse_bitwise_and()
        while True:
            self._arith_skip_ws()
            # Make sure it's not ^=
            if self._arith_peek() == "^" and self._arith_peek(1) != "=":
                self._arith_advance()
                self._arith_skip_ws()
                right = self._arith_parse_bitwise_and()
                left = ArithBinaryOp("^", left, right)
            else:
                break
        return left

    def _arith_parse_bitwise_and(self) -> Node:
        """Parse bitwise and (&)."""
        left = self._arith_parse_equality()
        while True:
            self._arith_skip_ws()
            # Make sure it's not && or &=
            if self._arith_peek() == "&" and (
                self._arith_peek(1) != "&" and self._arith_peek(1) != "="
            ):
                self._arith_advance()
                self._arith_skip_ws()
                right = self._arith_parse_equality()
                left = ArithBinaryOp("&", left, right)
            else:
                break
        return left

    def _arith_parse_equality(self) -> Node:
        """Parse equality (== !=)."""
        return self._arith_parse_left_assoc(["==", "!="], self._arith_parse_comparison)

    def _arith_parse_comparison(self) -> Node:
        """Parse comparison (< > <= >=)."""
        left = self._arith_parse_shift()
        while True:
            self._arith_skip_ws()
            if self._arith_match("<="):
                self._arith_consume("<=")
                self._arith_skip_ws()
                right = self._arith_parse_shift()
                left = ArithBinaryOp("<=", left, right)
            elif self._arith_match(">="):
                self._arith_consume(">=")
                self._arith_skip_ws()
                right = self._arith_parse_shift()
                left = ArithBinaryOp(">=", left, right)
            elif self._arith_peek() == "<" and (
                self._arith_peek(1) != "<" and self._arith_peek(1) != "="
            ):
                self._arith_advance()
                self._arith_skip_ws()
                right = self._arith_parse_shift()
                left = ArithBinaryOp("<", left, right)
            elif self._arith_peek() == ">" and (
                self._arith_peek(1) != ">" and self._arith_peek(1) != "="
            ):
                self._arith_advance()
                self._arith_skip_ws()
                right = self._arith_parse_shift()
                left = ArithBinaryOp(">", left, right)
            else:
                break
        return left

    def _arith_parse_shift(self) -> Node:
        """Parse shift (<< >>)."""
        left = self._arith_parse_additive()
        while True:
            self._arith_skip_ws()
            if self._arith_match("<<="):
                break  # assignment, not shift
            if self._arith_match(">>="):
                break  # assignment, not shift
            if self._arith_match("<<"):
                self._arith_consume("<<")
                self._arith_skip_ws()
                right = self._arith_parse_additive()
                left = ArithBinaryOp("<<", left, right)
            elif self._arith_match(">>"):
                self._arith_consume(">>")
                self._arith_skip_ws()
                right = self._arith_parse_additive()
                left = ArithBinaryOp(">>", left, right)
            else:
                break
        return left

    def _arith_parse_additive(self) -> Node:
        """Parse addition and subtraction (+ -)."""
        left = self._arith_parse_multiplicative()
        while True:
            self._arith_skip_ws()
            c = self._arith_peek()
            c2 = self._arith_peek(1)
            if c == "+" and (c2 != "+" and c2 != "="):
                self._arith_advance()
                self._arith_skip_ws()
                right = self._arith_parse_multiplicative()
                left = ArithBinaryOp("+", left, right)
            elif c == "-" and (c2 != "-" and c2 != "="):
                self._arith_advance()
                self._arith_skip_ws()
                right = self._arith_parse_multiplicative()
                left = ArithBinaryOp("-", left, right)
            else:
                break
        return left

    def _arith_parse_multiplicative(self) -> Node:
        """Parse multiplication, division, modulo (* / %)."""
        left = self._arith_parse_exponentiation()
        while True:
            self._arith_skip_ws()
            c = self._arith_peek()
            c2 = self._arith_peek(1)
            if c == "*" and (c2 != "*" and c2 != "="):
                self._arith_advance()
                self._arith_skip_ws()
                right = self._arith_parse_exponentiation()
                left = ArithBinaryOp("*", left, right)
            elif c == "/" and c2 != "=":
                self._arith_advance()
                self._arith_skip_ws()
                right = self._arith_parse_exponentiation()
                left = ArithBinaryOp("/", left, right)
            elif c == "%" and c2 != "=":
                self._arith_advance()
                self._arith_skip_ws()
                right = self._arith_parse_exponentiation()
                left = ArithBinaryOp("%", left, right)
            else:
                break
        return left

    def _arith_parse_exponentiation(self) -> Node:
        """Parse exponentiation (**) - right associative."""
        left = self._arith_parse_unary()
        self._arith_skip_ws()
        if self._arith_match("**"):
            self._arith_consume("**")
            self._arith_skip_ws()
            right = self._arith_parse_exponentiation()  # right associative
            return ArithBinaryOp("**", left, right)
        return left

    def _arith_parse_unary(self) -> Node:
        """Parse unary operators (! ~ + - ++ --)."""
        self._arith_skip_ws()
        # Pre-increment/decrement
        if self._arith_match("++"):
            self._arith_consume("++")
            self._arith_skip_ws()
            operand = self._arith_parse_unary()
            return ArithPreIncr(operand)
        if self._arith_match("--"):
            self._arith_consume("--")
            self._arith_skip_ws()
            operand = self._arith_parse_unary()
            return ArithPreDecr(operand)
        # Unary operators
        c = self._arith_peek()
        if c == "!":
            self._arith_advance()
            self._arith_skip_ws()
            operand = self._arith_parse_unary()
            return ArithUnaryOp("!", operand)
        if c == "~":
            self._arith_advance()
            self._arith_skip_ws()
            operand = self._arith_parse_unary()
            return ArithUnaryOp("~", operand)
        if c == "+" and self._arith_peek(1) != "+":
            self._arith_advance()
            self._arith_skip_ws()
            operand = self._arith_parse_unary()
            return ArithUnaryOp("+", operand)
        if c == "-" and self._arith_peek(1) != "-":
            self._arith_advance()
            self._arith_skip_ws()
            operand = self._arith_parse_unary()
            return ArithUnaryOp("-", operand)
        return self._arith_parse_postfix()

    def _arith_parse_postfix(self) -> Node:
        """Parse postfix operators (++ -- [])."""
        left = self._arith_parse_primary()
        while True:
            self._arith_skip_ws()
            if self._arith_match("++"):
                self._arith_consume("++")
                left = ArithPostIncr(left)
            elif self._arith_match("--"):
                self._arith_consume("--")
                left = ArithPostDecr(left)
            elif self._arith_peek() == "[":
                # Array subscript - but only for variables
                if left.kind == "var":
                    self._arith_advance()  # consume [
                    self._arith_skip_ws()
                    index = self._arith_parse_comma()
                    self._arith_skip_ws()
                    if not self._arith_consume("]"):
                        raise ParseError(
                            "Expected ']' in array subscript", pos=self._arith_pos
                        )
                    left = ArithSubscript(left.name, index)
                else:
                    break
            else:
                break
        return left

    def _arith_parse_primary(self) -> Node:
        """Parse primary expressions (numbers, variables, parens, expansions)."""
        self._arith_skip_ws()
        c = self._arith_peek()

        # Parenthesized expression
        if c == "(":
            self._arith_advance()
            self._arith_skip_ws()
            expr = self._arith_parse_comma()
            self._arith_skip_ws()
            if not self._arith_consume(")"):
                raise ParseError(
                    "Expected ')' in arithmetic expression", pos=self._arith_pos
                )
            return expr

        # Parameter length #$var or #${...}
        if c == "#" and self._arith_peek(1) == "$":
            self._arith_advance()  # consume #
            return self._arith_parse_expansion()

        # Parameter expansion ${...} or $var or $(...)
        if c == "$":
            return self._arith_parse_expansion()

        # Single-quoted string - content becomes the number
        if c == "'":
            return self._arith_parse_single_quote()

        # Double-quoted string - may contain expansions
        if c == '"':
            return self._arith_parse_double_quote()

        # Backtick command substitution
        if c == "`":
            return self._arith_parse_backtick()

        # Escape sequence \X (not line continuation, which is handled in _arith_skip_ws)
        # Escape covers only the single character after backslash
        if c == "\\":
            self._arith_advance()  # consume backslash
            if self._arith_at_end():
                raise ParseError(
                    "Unexpected end after backslash in arithmetic", pos=self._arith_pos
                )
            escaped_char = self._arith_advance()  # consume escaped character
            return ArithEscape(escaped_char)

        # Number or variable
        return self._arith_parse_number_or_var()

    def _arith_parse_expansion(self) -> Node:
        """Parse $var, ${...}, or $(...)."""
        if not self._arith_consume("$"):
            raise ParseError("Expected '$'", pos=self._arith_pos)

        c = self._arith_peek()

        # Command substitution $(...)
        if c == "(":
            return self._arith_parse_cmdsub()

        # Braced parameter ${...}
        if c == "{":
            return self._arith_parse_braced_param()

        # Simple $var
        name_chars = []
        while not self._arith_at_end():
            ch = self._arith_peek()
            if ch.isalnum() or ch == "_":
                name_chars.append(self._arith_advance())
            elif (_is_special_param_or_digit(ch) or ch == "#") and not name_chars:
                # Special parameters
                name_chars.append(self._arith_advance())
                break
            else:
                break
        if not name_chars:
            raise ParseError("Expected variable name after $", pos=self._arith_pos)
        return ParamExpansion("".join(name_chars))

    def _arith_parse_cmdsub(self) -> Node:
        """Parse $(...) command substitution inside arithmetic."""
        # We're positioned after $, at (
        self._arith_advance()  # consume (

        # Check for $(( which is nested arithmetic
        if self._arith_peek() == "(":
            self._arith_advance()  # consume second (
            depth = 1
            content_start = self._arith_pos
            while not self._arith_at_end() and depth > 0:
                ch = self._arith_peek()
                if ch == "(":
                    depth += 1
                    self._arith_advance()
                elif ch == ")":
                    if depth == 1 and self._arith_peek(1) == ")":
                        break
                    depth -= 1
                    self._arith_advance()
                else:
                    self._arith_advance()
            content = _substring(self._arith_src, content_start, self._arith_pos)
            self._arith_advance()  # consume first )
            self._arith_advance()  # consume second )
            inner_expr = self._parse_arith_expr(content)
            return ArithmeticExpansion(inner_expr)

        # Regular command substitution
        depth = 1
        content_start = self._arith_pos
        while not self._arith_at_end() and depth > 0:
            ch = self._arith_peek()
            if ch == "(":
                depth += 1
                self._arith_advance()
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    break
                self._arith_advance()
            else:
                self._arith_advance()
        content = _substring(self._arith_src, content_start, self._arith_pos)
        self._arith_advance()  # consume )

        # Parse the command inside
        saved_pos = self.pos
        saved_src = self.source
        saved_len = self.length
        self.source = content
        self.pos = 0
        self.length = len(content)
        cmd = self.parse_list()
        self.source = saved_src
        self.pos = saved_pos
        self.length = saved_len

        return CommandSubstitution(cmd)

    def _arith_parse_braced_param(self) -> Node:
        """Parse ${...} parameter expansion inside arithmetic."""
        self._arith_advance()  # consume {

        # Handle indirect ${!var}
        if self._arith_peek() == "!":
            self._arith_advance()
            name_chars = []
            while not self._arith_at_end() and self._arith_peek() != "}":
                name_chars.append(self._arith_advance())
            self._arith_consume("}")
            return ParamIndirect("".join(name_chars))

        # Handle length ${#var}
        if self._arith_peek() == "#":
            self._arith_advance()
            name_chars = []
            while not self._arith_at_end() and self._arith_peek() != "}":
                name_chars.append(self._arith_advance())
            self._arith_consume("}")
            return ParamLength("".join(name_chars))

        # Regular ${var} or ${var...}
        name_chars = []
        while not self._arith_at_end():
            ch = self._arith_peek()
            if ch == "}":
                self._arith_advance()
                return ParamExpansion("".join(name_chars))
            if _is_param_expansion_op(ch):
                # Operator follows
                break
            name_chars.append(self._arith_advance())

        name = "".join(name_chars)

        # Check for operator
        op_chars = []
        depth = 1
        while not self._arith_at_end() and depth > 0:
            ch = self._arith_peek()
            if ch == "{":
                depth += 1
                op_chars.append(self._arith_advance())
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    break
                op_chars.append(self._arith_advance())
            else:
                op_chars.append(self._arith_advance())
        self._arith_consume("}")
        op_str = "".join(op_chars)

        # Parse the operator
        if op_str.startswith(":-"):
            return ParamExpansion(name, ":-", _substring(op_str, 2, len(op_str)))
        if op_str.startswith(":="):
            return ParamExpansion(name, ":=", _substring(op_str, 2, len(op_str)))
        if op_str.startswith(":+"):
            return ParamExpansion(name, ":+", _substring(op_str, 2, len(op_str)))
        if op_str.startswith(":?"):
            return ParamExpansion(name, ":?", _substring(op_str, 2, len(op_str)))
        if op_str.startswith(":"):
            return ParamExpansion(name, ":", _substring(op_str, 1, len(op_str)))
        if op_str.startswith("##"):
            return ParamExpansion(name, "##", _substring(op_str, 2, len(op_str)))
        if op_str.startswith("#"):
            return ParamExpansion(name, "#", _substring(op_str, 1, len(op_str)))
        if op_str.startswith("%%"):
            return ParamExpansion(name, "%%", _substring(op_str, 2, len(op_str)))
        if op_str.startswith("%"):
            return ParamExpansion(name, "%", _substring(op_str, 1, len(op_str)))
        if op_str.startswith("//"):
            return ParamExpansion(name, "//", _substring(op_str, 2, len(op_str)))
        if op_str.startswith("/"):
            return ParamExpansion(name, "/", _substring(op_str, 1, len(op_str)))
        return ParamExpansion(name, "", op_str)

    def _arith_parse_single_quote(self) -> Node:
        """Parse '...' inside arithmetic - returns content as a number/string."""
        self._arith_advance()  # consume opening '
        content_start = self._arith_pos
        while not self._arith_at_end() and self._arith_peek() != "'":
            self._arith_advance()
        content = _substring(self._arith_src, content_start, self._arith_pos)
        if not self._arith_consume("'"):
            raise ParseError(
                "Unterminated single quote in arithmetic", pos=self._arith_pos
            )
        return ArithNumber(content)

    def _arith_parse_double_quote(self) -> Node:
        """Parse "..." inside arithmetic - may contain expansions."""
        self._arith_advance()  # consume opening "
        content_start = self._arith_pos
        while not self._arith_at_end() and self._arith_peek() != '"':
            c = self._arith_peek()
            if c == "\\" and not self._arith_at_end():
                self._arith_advance()  # skip backslash
                self._arith_advance()  # skip escaped char
            else:
                self._arith_advance()
        content = _substring(self._arith_src, content_start, self._arith_pos)
        if not self._arith_consume('"'):
            raise ParseError(
                "Unterminated double quote in arithmetic", pos=self._arith_pos
            )
        return ArithNumber(content)

    def _arith_parse_backtick(self) -> Node:
        """Parse `...` command substitution inside arithmetic."""
        self._arith_advance()  # consume opening `
        content_start = self._arith_pos
        while not self._arith_at_end() and self._arith_peek() != "`":
            c = self._arith_peek()
            if c == "\\" and not self._arith_at_end():
                self._arith_advance()  # skip backslash
                self._arith_advance()  # skip escaped char
            else:
                self._arith_advance()
        content = _substring(self._arith_src, content_start, self._arith_pos)
        if not self._arith_consume("`"):
            raise ParseError("Unterminated backtick in arithmetic", pos=self._arith_pos)
        # Parse the command inside
        saved_pos = self.pos
        saved_src = self.source
        saved_len = self.length
        self.source = content
        self.pos = 0
        self.length = len(content)
        cmd = self.parse_list()
        self.source = saved_src
        self.pos = saved_pos
        self.length = saved_len
        return CommandSubstitution(cmd)

    def _arith_parse_number_or_var(self) -> Node:
        """Parse a number or variable name."""
        self._arith_skip_ws()
        chars = []
        c = self._arith_peek()

        # Check for number (starts with digit or base#)
        if c.isdigit():
            # Could be decimal, hex (0x), octal (0), or base#n
            while not self._arith_at_end():
                ch = self._arith_peek()
                if ch.isalnum() or (ch == "#" or ch == "_"):
                    chars.append(self._arith_advance())
                else:
                    break
            prefix = "".join(chars)
            # Check if followed by $ expansion (e.g., 0x$var)
            if not self._arith_at_end() and self._arith_peek() == "$":
                expansion = self._arith_parse_expansion()
                return ArithConcat([ArithNumber(prefix), expansion])
            return ArithNumber(prefix)

        # Variable name (starts with letter or _)
        if c.isalpha() or c == "_":
            while not self._arith_at_end():
                ch = self._arith_peek()
                if ch.isalnum() or ch == "_":
                    chars.append(self._arith_advance())
                else:
                    break
            return ArithVar("".join(chars))

        raise ParseError(
            "Unexpected character '" + c + "' in arithmetic expression",
            pos=self._arith_pos,
        )

    def _parse_deprecated_arithmetic(self) -> tuple[Node | None, str]:
        """Parse a deprecated $[expr] arithmetic expansion.

        Returns (node, text) where node is ArithDeprecated and text is raw text.
        """
        if self.at_end() or self.peek() != "$":
            return None, ""

        start = self.pos

        # Check for $[
        if self.pos + 1 >= self.length or self.source[self.pos + 1] != "[":
            return None, ""

        self.advance()  # consume $
        self.advance()  # consume [

        # Find matching ] - need to track nested brackets
        content_start = self.pos
        depth = 1

        while not self.at_end() and depth > 0:
            c = self.peek()

            if c == "[":
                depth += 1
                self.advance()
            elif c == "]":
                depth -= 1
                if depth == 0:
                    break
                self.advance()
            else:
                self.advance()

        if self.at_end() or depth != 0:
            self.pos = start
            return None, ""

        content = _substring(self.source, content_start, self.pos)
        self.advance()  # consume ]

        text = _substring(self.source, start, self.pos)
        return ArithDeprecated(content), text

    def _parse_ansi_c_quote(self) -> tuple[Node | None, str]:
        """Parse ANSI-C quoting $'...'.

        Returns (node, text) where node is the AST node and text is the raw text.
        Returns (None, "") if not a valid ANSI-C quote.
        """
        if self.at_end() or self.peek() != "$":
            return None, ""
        if self.pos + 1 >= self.length or self.source[self.pos + 1] != "'":
            return None, ""

        start = self.pos
        self.advance()  # consume $
        self.advance()  # consume opening '

        content_chars = []
        found_close = False
        while not self.at_end():
            ch = self.peek()
            if ch == "'":
                self.advance()  # consume closing '
                found_close = True
                break
            elif ch == "\\":
                # Escape sequence - include both backslash and following char in content
                content_chars.append(self.advance())  # backslash
                if not self.at_end():
                    content_chars.append(self.advance())  # escaped char
            else:
                content_chars.append(self.advance())
        if not found_close:
            # Unterminated - reset and return None
            self.pos = start
            return None, ""

        text = _substring(self.source, start, self.pos)
        content = "".join(content_chars)
        return AnsiCQuote(content), text

    def _parse_locale_string(self) -> tuple[Node | None, str, list[Node]]:
        """Parse locale translation $"...".

        Returns (node, text, inner_parts) where:
        - node is the LocaleString AST node
        - text is the raw text including $"..."
        - inner_parts is a list of expansion nodes found inside
        Returns (None, "", []) if not a valid locale string.
        """
        if self.at_end() or self.peek() != "$":
            return None, "", []
        if self.pos + 1 >= self.length or self.source[self.pos + 1] != '"':
            return None, "", []

        start = self.pos
        self.advance()  # consume $
        self.advance()  # consume opening "

        content_chars = []
        inner_parts = []
        found_close = False

        while not self.at_end():
            ch = self.peek()
            if ch == '"':
                self.advance()  # consume closing "
                found_close = True
                break
            elif ch == "\\" and self.pos + 1 < self.length:
                # Escape sequence (line continuation removes both)
                next_ch = self.source[self.pos + 1]
                if next_ch == "\n":
                    # Line continuation - skip both backslash and newline
                    self.advance()
                    self.advance()
                else:
                    content_chars.append(self.advance())  # backslash
                    content_chars.append(self.advance())  # escaped char
            # Handle arithmetic expansion $((...))
            elif (
                ch == "$"
                and self.pos + 2 < self.length
                and self.source[self.pos + 1] == "("
                and self.source[self.pos + 2] == "("
            ):
                arith_result = self._parse_arithmetic_expansion()
                arith_node = arith_result[0]
                arith_text = arith_result[1]
                if arith_node:
                    inner_parts.append(arith_node)
                    content_chars.append(arith_text)
                else:
                    # Not arithmetic - try command substitution
                    cmdsub_result = self._parse_command_substitution()
                    cmdsub_node = cmdsub_result[0]
                    cmdsub_text = cmdsub_result[1]
                    if cmdsub_node:
                        inner_parts.append(cmdsub_node)
                        content_chars.append(cmdsub_text)
                    else:
                        content_chars.append(self.advance())
            # Handle command substitution $(...)
            elif (
                ch == "$"
                and self.pos + 1 < self.length
                and self.source[self.pos + 1] == "("
            ):
                cmdsub_result = self._parse_command_substitution()
                cmdsub_node = cmdsub_result[0]
                cmdsub_text = cmdsub_result[1]
                if cmdsub_node:
                    inner_parts.append(cmdsub_node)
                    content_chars.append(cmdsub_text)
                else:
                    content_chars.append(self.advance())
            # Handle parameter expansion
            elif ch == "$":
                param_result = self._parse_param_expansion()
                param_node = param_result[0]
                param_text = param_result[1]
                if param_node:
                    inner_parts.append(param_node)
                    content_chars.append(param_text)
                else:
                    content_chars.append(self.advance())
            # Handle backtick command substitution
            elif ch == "`":
                cmdsub_result = self._parse_backtick_substitution()
                cmdsub_node = cmdsub_result[0]
                cmdsub_text = cmdsub_result[1]
                if cmdsub_node:
                    inner_parts.append(cmdsub_node)
                    content_chars.append(cmdsub_text)
                else:
                    content_chars.append(self.advance())
            else:
                content_chars.append(self.advance())
        if not found_close:
            # Unterminated - reset and return None
            self.pos = start
            return None, "", []

        content = "".join(content_chars)
        # Reconstruct text from parsed content (handles line continuation removal)
        text = '$"' + content + '"'
        return LocaleString(content), text, inner_parts

    def _parse_param_expansion(self) -> tuple[Node | None, str]:
        """Parse a parameter expansion starting at $.

        Returns (node, text) where node is the AST node and text is the raw text.
        Returns (None, "") if not a valid parameter expansion.
        """
        if self.at_end() or self.peek() != "$":
            return None, ""

        start = self.pos
        self.advance()  # consume $

        if self.at_end():
            self.pos = start
            return None, ""

        ch = self.peek()

        # Braced expansion ${...}
        if ch == "{":
            self.advance()  # consume {
            return self._parse_braced_param(start)

        # Simple expansion $var or $special
        # Special parameters: ?$!#@*-0-9
        if _is_special_param_or_digit(ch) or ch == "#":
            self.advance()
            text = _substring(self.source, start, self.pos)
            return ParamExpansion(ch), text

        # Variable name [a-zA-Z_][a-zA-Z0-9_]*
        if ch.isalpha() or ch == "_":
            name_start = self.pos
            while not self.at_end():
                c = self.peek()
                if c.isalnum() or c == "_":
                    self.advance()
                else:
                    break
            name = _substring(self.source, name_start, self.pos)
            text = _substring(self.source, start, self.pos)
            return ParamExpansion(name), text

        # Not a valid expansion, restore position
        self.pos = start
        return None, ""

    def _parse_braced_param(self, start: int) -> tuple[Node | None, str]:
        """Parse contents of ${...} after the opening brace.

        start is the position of the $.
        Returns (node, text).
        """
        if self.at_end():
            self.pos = start
            return None, ""

        ch = self.peek()

        # ${#param} - length
        if ch == "#":
            self.advance()
            param = self._consume_param_name()
            if param and not self.at_end() and self.peek() == "}":
                self.advance()
                text = _substring(self.source, start, self.pos)
                return ParamLength(param), text
            self.pos = start
            return None, ""

        # ${!param} or ${!param<op><arg>} - indirect
        if ch == "!":
            self.advance()
            param = self._consume_param_name()
            if param:
                # Skip optional whitespace before closing brace
                while not self.at_end() and _is_whitespace_no_newline(self.peek()):
                    self.advance()
                if not self.at_end() and self.peek() == "}":
                    self.advance()
                    text = _substring(self.source, start, self.pos)
                    return ParamIndirect(param), text
                # ${!prefix@} and ${!prefix*} are prefix matching (lists variable names)
                # These are NOT operators - the @/* is part of the indirect form
                if not self.at_end() and _is_at_or_star(self.peek()):
                    suffix = self.advance()
                    while not self.at_end() and _is_whitespace_no_newline(self.peek()):
                        self.advance()
                    if not self.at_end() and self.peek() == "}":
                        self.advance()
                        text = _substring(self.source, start, self.pos)
                        return ParamIndirect(param + suffix), text
                    # Not a valid prefix match, reset
                    self.pos = start
                    return None, ""
                # Check for operator (e.g., ${!##} = indirect of # with # op)
                op = self._consume_param_operator()
                if op is not None:
                    # Parse argument until closing brace
                    arg_chars = []
                    depth = 1
                    while not self.at_end() and depth > 0:
                        c = self.peek()
                        if (
                            c == "$"
                            and self.pos + 1 < self.length
                            and self.source[self.pos + 1] == "{"
                        ):
                            depth += 1
                            arg_chars.append(self.advance())
                            arg_chars.append(self.advance())
                        elif c == "}":
                            depth -= 1
                            if depth > 0:
                                arg_chars.append(self.advance())
                        elif c == "\\":
                            arg_chars.append(self.advance())
                            if not self.at_end():
                                arg_chars.append(self.advance())
                        else:
                            arg_chars.append(self.advance())
                    if depth == 0:
                        self.advance()  # consume final }
                        arg = "".join(arg_chars)
                        text = _substring(self.source, start, self.pos)
                        return ParamIndirect(param, op, arg), text
            self.pos = start
            return None, ""

        # ${param} or ${param<op><arg>}
        param = self._consume_param_name()
        if not param:
            # Unknown syntax like ${(M)...} (zsh) - consume until matching }
            # Bash accepts these syntactically but fails at runtime
            depth = 1
            content_start = self.pos
            while not self.at_end() and depth > 0:
                c = self.peek()
                if c == "{":
                    depth += 1
                    self.advance()
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        break
                    self.advance()
                elif c == "\\":
                    self.advance()
                    if not self.at_end():
                        self.advance()
                else:
                    self.advance()
            if depth == 0:
                content = _substring(self.source, content_start, self.pos)
                self.advance()  # consume final }
                text = _substring(self.source, start, self.pos)
                return ParamExpansion(content), text
            self.pos = start
            return None, ""

        if self.at_end():
            self.pos = start
            return None, ""

        # Check for closing brace (simple expansion)
        if self.peek() == "}":
            self.advance()
            text = _substring(self.source, start, self.pos)
            return ParamExpansion(param), text

        # Parse operator
        op = self._consume_param_operator()
        if op is None:
            # Unknown operator - bash still parses these (fails at runtime)
            # Treat the current char as the operator
            op = self.advance()

        # Parse argument (everything until closing brace)
        # Track quote state and nesting
        arg_chars = []
        depth = 1
        in_single_quote = False
        in_double_quote = False
        while not self.at_end() and depth > 0:
            c = self.peek()
            # Single quotes - no escapes, just scan to closing quote
            if c == "'" and not in_double_quote:
                in_single_quote = not in_single_quote
                arg_chars.append(self.advance())
            # Double quotes - toggle state
            elif c == '"' and not in_single_quote:
                in_double_quote = not in_double_quote
                arg_chars.append(self.advance())
            # Escape - skip next char (line continuation removes both)
            elif c == "\\" and not in_single_quote:
                if self.pos + 1 < self.length and self.source[self.pos + 1] == "\n":
                    # Line continuation - skip both backslash and newline
                    self.advance()
                    self.advance()
                else:
                    arg_chars.append(self.advance())
                    if not self.at_end():
                        arg_chars.append(self.advance())
            # Nested ${...} - increase depth (outside single quotes)
            elif (
                c == "$"
                and not in_single_quote
                and self.pos + 1 < self.length
                and self.source[self.pos + 1] == "{"
            ):
                depth += 1
                arg_chars.append(self.advance())  # $
                arg_chars.append(self.advance())  # {
            # Command substitution $(...) - scan to matching )
            elif (
                c == "$"
                and not in_single_quote
                and self.pos + 1 < self.length
                and self.source[self.pos + 1] == "("
            ):
                arg_chars.append(self.advance())  # $
                arg_chars.append(self.advance())  # (
                paren_depth = 1
                while not self.at_end() and paren_depth > 0:
                    pc = self.peek()
                    if pc == "(":
                        paren_depth += 1
                    elif pc == ")":
                        paren_depth -= 1
                    elif pc == "\\":
                        arg_chars.append(self.advance())
                        if not self.at_end():
                            arg_chars.append(self.advance())
                        continue
                    arg_chars.append(self.advance())
            # Backtick command substitution - scan to matching `
            elif c == "`" and not in_single_quote:
                arg_chars.append(self.advance())  # opening `
                while not self.at_end() and self.peek() != "`":
                    bc = self.peek()
                    if bc == "\\" and self.pos + 1 < self.length:
                        next_c = self.source[self.pos + 1]
                        if _is_escape_char_in_dquote(next_c):
                            arg_chars.append(self.advance())  # backslash
                    arg_chars.append(self.advance())
                if not self.at_end():
                    arg_chars.append(self.advance())  # closing `
            # Closing brace - handle depth for nested ${...}
            elif c == "}":
                if in_single_quote:
                    # Inside single quotes, } is literal
                    arg_chars.append(self.advance())
                elif in_double_quote:
                    # Inside double quotes, } can close nested ${...}
                    if depth > 1:
                        depth -= 1
                        arg_chars.append(self.advance())
                    else:
                        # Literal } in double quotes (not closing nested)
                        arg_chars.append(self.advance())
                else:
                    depth -= 1
                    if depth > 0:
                        arg_chars.append(self.advance())
            else:
                arg_chars.append(self.advance())

        if depth != 0:
            self.pos = start
            return None, ""

        self.advance()  # consume final }
        arg = "".join(arg_chars)
        # Reconstruct text from parsed components (handles line continuation removal)
        text = "${" + param + op + arg + "}"
        return ParamExpansion(param, op, arg), text

    def _consume_param_name(self) -> str | None:
        """Consume a parameter name (variable name, special char, or array subscript)."""
        if self.at_end():
            return None

        ch = self.peek()

        # Special parameters
        if _is_special_param(ch):
            self.advance()
            return ch

        # Digits (positional params)
        if ch.isdigit():
            name_chars = []
            while not self.at_end() and self.peek().isdigit():
                name_chars.append(self.advance())
            return "".join(name_chars)

        # Variable name
        if ch.isalpha() or ch == "_":
            name_chars = []
            while not self.at_end():
                c = self.peek()
                if c.isalnum() or c == "_":
                    name_chars.append(self.advance())
                elif c == "[":
                    # Array subscript - track bracket depth
                    name_chars.append(self.advance())
                    bracket_depth = 1
                    while not self.at_end() and bracket_depth > 0:
                        sc = self.peek()
                        if sc == "[":
                            bracket_depth += 1
                        elif sc == "]":
                            bracket_depth -= 1
                            if bracket_depth == 0:
                                break
                        name_chars.append(self.advance())
                    if not self.at_end() and self.peek() == "]":
                        name_chars.append(self.advance())
                    break
                else:
                    break
            if name_chars:
                return "".join(name_chars)
            else:
                return None

        return None

    def _consume_param_operator(self) -> str | None:
        """Consume a parameter expansion operator."""
        if self.at_end():
            return None

        ch = self.peek()

        # Operators with optional colon prefix: :- := :? :+
        if ch == ":":
            self.advance()
            if self.at_end():
                return ":"
            next_ch = self.peek()
            if _is_simple_param_op(next_ch):
                self.advance()
                return ":" + next_ch
            # Just : (substring)
            return ":"

        # Operators without colon: - = ? +
        if _is_simple_param_op(ch):
            self.advance()
            return ch

        # Pattern removal: # ## % %%
        if ch == "#":
            self.advance()
            if not self.at_end() and self.peek() == "#":
                self.advance()
                return "##"
            return "#"

        if ch == "%":
            self.advance()
            if not self.at_end() and self.peek() == "%":
                self.advance()
                return "%%"
            return "%"

        # Substitution: / // /# /%
        if ch == "/":
            self.advance()
            if not self.at_end():
                next_ch = self.peek()
                if next_ch == "/":
                    self.advance()
                    return "//"
                elif next_ch == "#":
                    self.advance()
                    return "/#"
                elif next_ch == "%":
                    self.advance()
                    return "/%"
            return "/"

        # Case modification: ^ ^^ , ,,
        if ch == "^":
            self.advance()
            if not self.at_end() and self.peek() == "^":
                self.advance()
                return "^^"
            return "^"

        if ch == ",":
            self.advance()
            if not self.at_end() and self.peek() == ",":
                self.advance()
                return ",,"
            return ","

        # Transformation: @
        if ch == "@":
            self.advance()
            return "@"

        return None

    def parse_redirect(self) -> Redirect | HereDoc | None:
        """Parse a redirection operator and target."""
        self.skip_whitespace()
        if self.at_end():
            return None

        start = self.pos
        fd = None
        varfd = None  # Variable fd like {fd}

        # Check for variable fd {varname} or {varname[subscript]} before redirect
        if self.peek() == "{":
            saved = self.pos
            self.advance()  # consume {
            varname_chars = []
            while not self.at_end() and (
                self.peek() != "}" and not _is_redirect_char(self.peek())
            ):
                ch = self.peek()
                if ch.isalnum() or (ch == "_" or ch == "[" or ch == "]"):
                    varname_chars.append(self.advance())
                else:
                    break
            if not self.at_end() and self.peek() == "}" and varname_chars:
                self.advance()  # consume }
                varfd = "".join(varname_chars)
            else:
                # Not a valid variable fd, restore
                self.pos = saved

        # Check for optional fd number before redirect (if no varfd)
        if varfd is None and self.peek() and self.peek().isdigit():
            fd_chars = []
            while not self.at_end() and self.peek().isdigit():
                fd_chars.append(self.advance())
            fd = int("".join(fd_chars))

        ch = self.peek()

        # Handle &> and &>> (redirect both stdout and stderr)
        # Note: &> does NOT take a preceding fd number. If we consumed digits,
        # they should be a separate word, not an fd. E.g., "2&>1" is command "2"
        # with redirect "&> 1", not fd 2 redirected.
        if (
            ch == "&"
            and self.pos + 1 < self.length
            and self.source[self.pos + 1] == ">"
        ):
            if fd is not None:
                # We consumed digits that should be a word, not an fd
                # Restore position and let parse_word handle them
                self.pos = start
                return None
            self.advance()  # consume &
            self.advance()  # consume >
            if not self.at_end() and self.peek() == ">":
                self.advance()  # consume second > for &>>
                op = "&>>"
            else:
                op = "&>"
            self.skip_whitespace()
            target = self.parse_word()
            if target is None:
                raise ParseError("Expected target for redirect " + op, pos=self.pos)
            return Redirect(op, target)

        if ch is None or not _is_redirect_char(ch):
            # Not a redirect, restore position
            self.pos = start
            return None

        # Check for process substitution <(...) or >(...) - not a redirect
        # Only treat as redirect if there's a space before ( or an fd number
        if (
            fd is None
            and self.pos + 1 < self.length
            and self.source[self.pos + 1] == "("
        ):
            # This is a process substitution, not a redirect
            self.pos = start
            return None

        # Parse the redirect operator
        op = self.advance()

        # Check for multi-char operators
        strip_tabs = False
        if not self.at_end():
            next_ch = self.peek()
            if op == ">" and next_ch == ">":
                self.advance()
                op = ">>"
            elif op == "<" and next_ch == "<":
                self.advance()
                if not self.at_end() and self.peek() == "<":
                    self.advance()
                    op = "<<<"
                elif not self.at_end() and self.peek() == "-":
                    self.advance()
                    op = "<<"
                    strip_tabs = True
                else:
                    op = "<<"
            # Handle <> (read-write)
            elif op == "<" and next_ch == ">":
                self.advance()
                op = "<>"
            # Handle >| (noclobber override)
            elif op == ">" and next_ch == "|":
                self.advance()
                op = ">|"
            # Only consume >& or <& as operators if NOT followed by a digit or -
            # (>&2 should be > with target &2, not >& with target 2)
            # (>&- should be > with target &-, not >& with target -)
            elif fd is None and varfd is None and op == ">" and next_ch == "&":
                # Peek ahead to see if there's a digit or - after &
                if self.pos + 1 >= self.length or not _is_digit_or_dash(
                    self.source[self.pos + 1]
                ):
                    self.advance()
                    op = ">&"
            elif fd is None and varfd is None and op == "<" and next_ch == "&":
                if self.pos + 1 >= self.length or not _is_digit_or_dash(
                    self.source[self.pos + 1]
                ):
                    self.advance()
                    op = "<&"

        # Handle here document
        if op == "<<":
            return self._parse_heredoc(fd, strip_tabs)

        # Combine fd or varfd with operator if present
        if varfd is not None:
            op = "{" + varfd + "}" + op
        elif fd is not None:
            op = str(fd) + op

        self.skip_whitespace()

        # Handle fd duplication targets like &1, &2, &-, &10-, &$var
        if not self.at_end() and self.peek() == "&":
            self.advance()  # consume &
            # Parse the fd number or - for close, including move syntax like &10-
            if not self.at_end() and (self.peek().isdigit() or self.peek() == "-"):
                fd_chars = []
                while not self.at_end() and self.peek().isdigit():
                    fd_chars.append(self.advance())
                if fd_chars:
                    fd_target = "".join(fd_chars)
                else:
                    fd_target = ""
                # Handle just - for close, or N- for move syntax
                if not self.at_end() and self.peek() == "-":
                    fd_target += self.advance()  # consume the trailing -
                target = Word("&" + fd_target)
            else:
                # Could be &$var or &word - parse word and prepend &
                inner_word = self.parse_word()
                if inner_word is not None:
                    target = Word("&" + inner_word.value)
                    target.parts = inner_word.parts
                else:
                    raise ParseError("Expected target for redirect " + op, pos=self.pos)
        else:
            target = self.parse_word()

        if target is None:
            raise ParseError("Expected target for redirect " + op, pos=self.pos)

        return Redirect(op, target)

    def _parse_heredoc(self, fd: int | None, strip_tabs: bool) -> HereDoc:
        """Parse a here document <<DELIM ... DELIM."""
        self.skip_whitespace()

        # Parse the delimiter, handling quoting (can be mixed like 'EOF'"2")
        quoted = False
        delimiter_chars = []

        while not self.at_end() and not _is_metachar(self.peek()):
            ch = self.peek()
            if ch == '"':
                quoted = True
                self.advance()
                while not self.at_end() and self.peek() != '"':
                    delimiter_chars.append(self.advance())
                if not self.at_end():
                    self.advance()
            elif ch == "'":
                quoted = True
                self.advance()
                while not self.at_end() and self.peek() != "'":
                    delimiter_chars.append(self.advance())
                if not self.at_end():
                    self.advance()
            elif ch == "\\":
                self.advance()
                if not self.at_end():
                    next_ch = self.peek()
                    if next_ch == "\n":
                        # Backslash-newline: continue delimiter on next line
                        self.advance()  # skip the newline
                    else:
                        # Regular escape - quotes the next char
                        quoted = True
                        delimiter_chars.append(self.advance())
            elif (
                ch == "$"
                and self.pos + 1 < self.length
                and self.source[self.pos + 1] == "("
            ):
                # Command substitution embedded in delimiter
                delimiter_chars.append(self.advance())  # $
                delimiter_chars.append(self.advance())  # (
                depth = 1
                while not self.at_end() and depth > 0:
                    c = self.peek()
                    if c == "(":
                        depth += 1
                    elif c == ")":
                        depth -= 1
                    delimiter_chars.append(self.advance())
            else:
                delimiter_chars.append(self.advance())

        delimiter = "".join(delimiter_chars)

        # Find the end of the current line (command continues until newline)
        # We need to mark where the heredoc content starts
        # Must be quote-aware - newlines inside quoted strings don't end the line
        line_end = self.pos
        while line_end < self.length and self.source[line_end] != "\n":
            ch = self.source[line_end]
            if ch == "'":
                # Single-quoted string - skip to closing quote (no escapes)
                line_end += 1
                while line_end < self.length and self.source[line_end] != "'":
                    line_end += 1
            elif ch == '"':
                # Double-quoted string - skip to closing quote (with escapes)
                line_end += 1
                while line_end < self.length and self.source[line_end] != '"':
                    if self.source[line_end] == "\\" and line_end + 1 < self.length:
                        line_end += 2
                    else:
                        line_end += 1
            elif ch == "\\" and line_end + 1 < self.length:
                # Backslash escape - skip both chars
                line_end += 2
                continue
            line_end += 1

        # Find heredoc content starting position
        # If there's already a pending heredoc, this one's content starts after that
        if (
            self._pending_heredoc_end is not None
            and self._pending_heredoc_end > line_end
        ):
            content_start = self._pending_heredoc_end
        elif line_end < self.length:
            content_start = line_end + 1  # skip the newline
        else:
            content_start = self.length

        # Find the delimiter line
        content_lines = []
        scan_pos = content_start

        while scan_pos < self.length:
            # Find end of current line
            line_start = scan_pos
            line_end = scan_pos
            while line_end < self.length and self.source[line_end] != "\n":
                line_end += 1

            line = _substring(self.source, line_start, line_end)

            # For unquoted heredocs, process backslash-newline before checking delimiter
            # Join continued lines to check the full logical line against delimiter
            # Only odd number of trailing backslashes means continuation (even = literal)
            if not quoted:
                while line_end < self.length:
                    # Count trailing backslashes
                    trailing_bs = 0
                    for i in range(len(line) - 1, -1, -1):
                        if line[i] == "\\":
                            trailing_bs += 1
                        else:
                            break
                    if trailing_bs % 2 == 0:
                        break  # Even backslashes (including 0) - no continuation
                    # Odd backslashes - line continuation
                    line = _substring(
                        line, 0, len(line) - 1
                    )  # Remove the escaping backslash
                    line_end += 1  # Skip newline
                    next_line_start = line_end
                    while line_end < self.length and self.source[line_end] != "\n":
                        line_end += 1
                    line = line + _substring(self.source, next_line_start, line_end)

            # Check if this line is the delimiter
            check_line = line
            if strip_tabs:
                check_line = line.lstrip("\t")

            if check_line == delimiter:
                # Found the end - update parser position past the heredoc
                # We need to consume the heredoc content from the input
                # But we can't do that here because we haven't finished parsing the command line
                # Store the heredoc info and let the command parser handle it
                break

            # Add line to content (with newline, since we consumed continuations above)
            if strip_tabs:
                line = line.lstrip("\t")
            content_lines.append(line + "\n")

            # Move past the newline
            if line_end < self.length:
                scan_pos = line_end + 1
            else:
                scan_pos = self.length

        # Join content (newlines already included per line)
        content = "".join(content_lines)

        # Store the position where heredoc content ends so we can skip it later
        # line_end points to the end of the delimiter line (after any continuations)
        heredoc_end = line_end
        if heredoc_end < self.length:
            heredoc_end += 1  # past the newline

        # Register this heredoc's end position
        if self._pending_heredoc_end is None:
            self._pending_heredoc_end = heredoc_end
        else:
            self._pending_heredoc_end = max(self._pending_heredoc_end, heredoc_end)

        return HereDoc(delimiter, content, strip_tabs, quoted, fd)

    def parse_command(self) -> Command | None:
        """Parse a simple command (sequence of words and redirections)."""
        words = []
        redirects = []

        while True:
            self.skip_whitespace()
            if self.at_end():
                break
            ch = self.peek()
            # Check for command terminators, but &> and &>> are redirects, not terminators
            if _is_list_terminator(ch):
                break
            if ch == "&" and not (
                self.pos + 1 < self.length and self.source[self.pos + 1] == ">"
            ):
                break
            # } is only a terminator at command position (closing a brace group)
            # In argument position, } is just a regular word
            if self.peek() == "}" and not words:
                # Check if } would be a standalone word (next char is whitespace/meta/EOF)
                next_pos = self.pos + 1
                if next_pos >= self.length or _is_word_end_context(
                    self.source[next_pos]
                ):
                    break

            # Try to parse a redirect first
            redirect = self.parse_redirect()
            if redirect is not None:
                redirects.append(redirect)
                continue

            # Otherwise parse a word
            # Allow array assignments like a[1 + 2]= in prefix position (before first non-assignment)
            # Check if all previous words were assignments (contain = not inside quotes)
            all_assignments = True
            for w in words:
                if not self._is_assignment_word(w):
                    all_assignments = False
                    break
            word = self.parse_word(at_command_start=not words or all_assignments)
            if word is None:
                break
            words.append(word)

        if not words and not redirects:
            return None

        return Command(words, redirects)

    def parse_subshell(self) -> Subshell | None:
        """Parse a subshell ( list )."""
        self.skip_whitespace()
        if self.at_end() or self.peek() != "(":
            return None

        self.advance()  # consume (

        body = self.parse_list()
        if body is None:
            raise ParseError("Expected command in subshell", pos=self.pos)

        self.skip_whitespace()
        if self.at_end() or self.peek() != ")":
            raise ParseError("Expected ) to close subshell", pos=self.pos)
        self.advance()  # consume )
        return Subshell(body, self._collect_redirects())

    def parse_arithmetic_command(self) -> ArithmeticCommand | None:
        """Parse an arithmetic command (( expression )) with parsed internals.

        Returns None if this is not an arithmetic command (e.g., nested subshells
        like '( ( x ) )' that close with ') )' instead of '))').
        """
        self.skip_whitespace()

        # Check for ((
        if (
            self.at_end()
            or self.peek() != "("
            or self.pos + 1 >= self.length
            or self.source[self.pos + 1] != "("
        ):
            return None

        saved_pos = self.pos
        self.advance()  # consume first (
        self.advance()  # consume second (

        # Find matching )) - track nested parens
        # Must be )) with no space between - ') )' is nested subshells
        content_start = self.pos
        depth = 1

        while not self.at_end() and depth > 0:
            c = self.peek()

            if c == "(":
                depth += 1
                self.advance()
            elif c == ")":
                # Check for )) (must be consecutive, no space)
                if (
                    depth == 1
                    and self.pos + 1 < self.length
                    and self.source[self.pos + 1] == ")"
                ):
                    # Found the closing ))
                    break
                depth -= 1
                if depth == 0:
                    # Closed with ) but next isn't ) - this is nested subshells, not arithmetic
                    self.pos = saved_pos
                    return None
                self.advance()
            else:
                self.advance()

        if self.at_end() or depth != 1:
            # Didn't find )) - might be nested subshells or malformed
            self.pos = saved_pos
            return None

        content = _substring(self.source, content_start, self.pos)
        self.advance()  # consume first )
        self.advance()  # consume second )

        # Parse the arithmetic expression
        expr = self._parse_arith_expr(content)
        return ArithmeticCommand(expr, self._collect_redirects(), raw_content=content)

    # Unary operators for [[ ]] conditionals
    COND_UNARY_OPS = {
        "-a",
        "-b",
        "-c",
        "-d",
        "-e",
        "-f",
        "-g",
        "-h",
        "-k",
        "-p",
        "-r",
        "-s",
        "-t",
        "-u",
        "-w",
        "-x",
        "-G",
        "-L",
        "-N",
        "-O",
        "-S",
        "-z",
        "-n",
        "-o",
        "-v",
        "-R",
    }
    # Binary operators for [[ ]] conditionals
    COND_BINARY_OPS = {
        "==",
        "!=",
        "=~",
        "=",
        "<",
        ">",
        "-eq",
        "-ne",
        "-lt",
        "-le",
        "-gt",
        "-ge",
        "-nt",
        "-ot",
        "-ef",
    }

    def parse_conditional_expr(self) -> ConditionalExpr | None:
        """Parse a conditional expression [[ expression ]]."""
        self.skip_whitespace()

        # Check for [[
        if (
            self.at_end()
            or self.peek() != "["
            or self.pos + 1 >= self.length
            or self.source[self.pos + 1] != "["
        ):
            return None

        self.advance()  # consume first [
        self.advance()  # consume second [

        # Parse the conditional expression body
        body = self._parse_cond_or()

        # Skip whitespace before ]]
        while not self.at_end() and _is_whitespace_no_newline(self.peek()):
            self.advance()

        # Expect ]]
        if (
            self.at_end()
            or self.peek() != "]"
            or self.pos + 1 >= self.length
            or self.source[self.pos + 1] != "]"
        ):
            raise ParseError(
                "Expected ]] to close conditional expression", pos=self.pos
            )

        self.advance()  # consume first ]
        self.advance()  # consume second ]
        return ConditionalExpr(body, self._collect_redirects())

    def _cond_skip_whitespace(self) -> None:
        """Skip whitespace inside [[ ]], including backslash-newline continuation."""
        while not self.at_end():
            if _is_whitespace_no_newline(self.peek()):
                self.advance()
            elif (
                self.peek() == "\\"
                and self.pos + 1 < self.length
                and self.source[self.pos + 1] == "\n"
            ):
                self.advance()  # consume backslash
                self.advance()  # consume newline
            elif self.peek() == "\n":
                # Bare newline is also allowed inside [[ ]]
                self.advance()
            else:
                break

    def _cond_at_end(self) -> bool:
        """Check if we're at ]] (end of conditional)."""
        return self.at_end() or (
            self.peek() == "]"
            and self.pos + 1 < self.length
            and self.source[self.pos + 1] == "]"
        )

    def _parse_cond_or(self) -> Node:
        """Parse: or_expr = and_expr (|| or_expr)?  (right-associative)"""
        self._cond_skip_whitespace()
        left = self._parse_cond_and()
        self._cond_skip_whitespace()
        if (
            not self._cond_at_end()
            and self.peek() == "|"
            and self.pos + 1 < self.length
            and self.source[self.pos + 1] == "|"
        ):
            self.advance()  # consume first |
            self.advance()  # consume second |
            right = self._parse_cond_or()  # recursive for right-associativity
            return CondOr(left, right)
        return left

    def _parse_cond_and(self) -> Node:
        """Parse: and_expr = term (&& and_expr)?  (right-associative)"""
        self._cond_skip_whitespace()
        left = self._parse_cond_term()
        self._cond_skip_whitespace()
        if (
            not self._cond_at_end()
            and self.peek() == "&"
            and self.pos + 1 < self.length
            and self.source[self.pos + 1] == "&"
        ):
            self.advance()  # consume first &
            self.advance()  # consume second &
            right = self._parse_cond_and()  # recursive for right-associativity
            return CondAnd(left, right)
        return left

    def _parse_cond_term(self) -> Node:
        """Parse: term = '!' term | '(' or_expr ')' | unary_test | binary_test | bare_word"""
        self._cond_skip_whitespace()

        if self._cond_at_end():
            raise ParseError("Unexpected end of conditional expression", pos=self.pos)

        # Negation: ! term
        if self.peek() == "!":
            # Check it's not != operator (need whitespace after !)
            if self.pos + 1 < self.length and not _is_whitespace_no_newline(
                self.source[self.pos + 1]
            ):
                pass  # not negation, fall through to word parsing
            else:
                self.advance()  # consume !
                operand = self._parse_cond_term()
                return CondNot(operand)

        # Parenthesized group: ( or_expr )
        if self.peek() == "(":
            self.advance()  # consume (
            inner = self._parse_cond_or()
            self._cond_skip_whitespace()
            if self.at_end() or self.peek() != ")":
                raise ParseError("Expected ) in conditional expression", pos=self.pos)
            self.advance()  # consume )
            return CondParen(inner)

        # Parse first word
        word1 = self._parse_cond_word()
        if word1 is None:
            raise ParseError("Expected word in conditional expression", pos=self.pos)

        self._cond_skip_whitespace()

        # Check if word1 is a unary operator
        if word1.value in COND_UNARY_OPS:
            # Unary test: -f file
            operand = self._parse_cond_word()
            if operand is None:
                raise ParseError("Expected operand after " + word1.value, pos=self.pos)
            return UnaryTest(word1.value, operand)

        # Check if next token is a binary operator
        if not self._cond_at_end() and (
            self.peek() != "&" and self.peek() != "|" and self.peek() != ")"
        ):
            # Handle < and > as binary operators (they terminate words)
            # But not <( or >( which are process substitution
            if _is_redirect_char(self.peek()) and not (
                self.pos + 1 < self.length and self.source[self.pos + 1] == "("
            ):
                op = self.advance()
                self._cond_skip_whitespace()
                word2 = self._parse_cond_word()
                if word2 is None:
                    raise ParseError("Expected operand after " + op, pos=self.pos)
                return BinaryTest(op, word1, word2)
            # Peek at next word to see if it's a binary operator
            saved_pos = self.pos
            op_word = self._parse_cond_word()
            if op_word and op_word.value in COND_BINARY_OPS:
                # Binary test: word1 op word2
                self._cond_skip_whitespace()
                # For =~ operator, the RHS is a regex where ( ) are grouping, not conditional grouping
                if op_word.value == "=~":
                    word2 = self._parse_cond_regex_word()
                else:
                    word2 = self._parse_cond_word()
                if word2 is None:
                    raise ParseError(
                        "Expected operand after " + op_word.value, pos=self.pos
                    )
                return BinaryTest(op_word.value, word1, word2)
            else:
                # Not a binary op, restore position
                self.pos = saved_pos

        # Bare word: implicit -n test
        return UnaryTest("-n", word1)

    def _parse_cond_word(self) -> Word | None:
        """Parse a word inside [[ ]], handling expansions but stopping at conditional operators."""
        self._cond_skip_whitespace()

        if self._cond_at_end():
            return None

        # Check for special tokens that aren't words
        c = self.peek()
        if _is_paren(c):
            return None
        # Note: ! alone is handled by _parse_cond_term() as negation operator
        # Here we allow ! as a word so it can be used as pattern in binary tests
        if c == "&" and self.pos + 1 < self.length and self.source[self.pos + 1] == "&":
            return None
        if c == "|" and self.pos + 1 < self.length and self.source[self.pos + 1] == "|":
            return None

        start = self.pos
        chars = []
        parts = []

        while not self.at_end():
            ch = self.peek()

            # End of conditional
            if (
                ch == "]"
                and self.pos + 1 < self.length
                and self.source[self.pos + 1] == "]"
            ):
                break

            # Word terminators in conditionals
            if _is_whitespace_no_newline(ch):
                break
            # < and > are string comparison operators in [[ ]], terminate words
            # But <(...) and >(...) are process substitution - don't break
            if _is_redirect_char(ch) and not (
                self.pos + 1 < self.length and self.source[self.pos + 1] == "("
            ):
                break
            # ( and ) end words unless part of extended glob: @(...), ?(...), *(...), +(...), !(...)
            if ch == "(":
                # Check if this is an extended glob (preceded by @, ?, *, +, or !)
                if chars and _is_extglob_prefix(chars[len(chars) - 1]):
                    # Extended glob - consume the parenthesized content
                    chars.append(self.advance())  # (
                    depth = 1
                    while not self.at_end() and depth > 0:
                        c = self.peek()
                        if c == "(":
                            depth += 1
                        elif c == ")":
                            depth -= 1
                        chars.append(self.advance())
                    continue
                else:
                    break
            if ch == ")":
                break
            if (
                ch == "&"
                and self.pos + 1 < self.length
                and self.source[self.pos + 1] == "&"
            ):
                break
            if (
                ch == "|"
                and self.pos + 1 < self.length
                and self.source[self.pos + 1] == "|"
            ):
                break

            # Glob bracket expression [...] - consume until closing ]
            # Handles [[:alpha:]], [^0-9], []a-z] (] as first char), etc.
            if ch == "[":
                chars.append(self.advance())  # consume [
                # Handle negation [^
                if not self.at_end() and self.peek() == "^":
                    chars.append(self.advance())
                # Handle ] as first char (literal ])
                if not self.at_end() and self.peek() == "]":
                    chars.append(self.advance())
                # Consume until closing ]
                while not self.at_end():
                    c = self.peek()
                    if c == "]":
                        chars.append(self.advance())
                        break
                    if (
                        c == "["
                        and self.pos + 1 < self.length
                        and self.source[self.pos + 1] == ":"
                    ):
                        # POSIX class like [:alpha:] inside bracket expression
                        chars.append(self.advance())  # [
                        chars.append(self.advance())  # :
                        while not self.at_end() and not (
                            self.peek() == ":"
                            and self.pos + 1 < self.length
                            and self.source[self.pos + 1] == "]"
                        ):
                            chars.append(self.advance())
                        if not self.at_end():
                            chars.append(self.advance())  # :
                            chars.append(self.advance())  # ]
                    elif (
                        c == "["
                        and self.pos + 1 < self.length
                        and self.source[self.pos + 1] == "="
                    ):
                        # Equivalence class like [=a=] inside bracket expression
                        chars.append(self.advance())  # [
                        chars.append(self.advance())  # =
                        while not self.at_end() and not (
                            self.peek() == "="
                            and self.pos + 1 < self.length
                            and self.source[self.pos + 1] == "]"
                        ):
                            chars.append(self.advance())
                        if not self.at_end():
                            chars.append(self.advance())  # =
                            chars.append(self.advance())  # ]
                    elif (
                        c == "["
                        and self.pos + 1 < self.length
                        and self.source[self.pos + 1] == "."
                    ):
                        # Collating symbol like [.ch.] inside bracket expression
                        chars.append(self.advance())  # [
                        chars.append(self.advance())  # .
                        while not self.at_end() and not (
                            self.peek() == "."
                            and self.pos + 1 < self.length
                            and self.source[self.pos + 1] == "]"
                        ):
                            chars.append(self.advance())
                        if not self.at_end():
                            chars.append(self.advance())  # .
                            chars.append(self.advance())  # ]
                    else:
                        chars.append(self.advance())
                continue

            # Single-quoted string
            if ch == "'":
                self.advance()
                chars.append("'")
                while not self.at_end() and self.peek() != "'":
                    chars.append(self.advance())
                if self.at_end():
                    raise ParseError("Unterminated single quote", pos=start)
                chars.append(self.advance())

            # Double-quoted string
            elif ch == '"':
                self.advance()
                chars.append('"')
                while not self.at_end() and self.peek() != '"':
                    c = self.peek()
                    if c == "\\" and self.pos + 1 < self.length:
                        next_c = self.source[self.pos + 1]
                        if next_c == "\n":
                            # Line continuation - skip both backslash and newline
                            self.advance()
                            self.advance()
                        else:
                            chars.append(self.advance())
                            chars.append(self.advance())
                    elif c == "$":
                        # Handle expansions inside double quotes
                        if (
                            self.pos + 2 < self.length
                            and self.source[self.pos + 1] == "("
                            and self.source[self.pos + 2] == "("
                        ):
                            arith_result = self._parse_arithmetic_expansion()
                            arith_node = arith_result[0]
                            arith_text = arith_result[1]
                            if arith_node:
                                parts.append(arith_node)
                                chars.append(arith_text)
                            else:
                                # Not arithmetic - try command substitution
                                cmdsub_result = self._parse_command_substitution()
                                cmdsub_node = cmdsub_result[0]
                                cmdsub_text = cmdsub_result[1]
                                if cmdsub_node:
                                    parts.append(cmdsub_node)
                                    chars.append(cmdsub_text)
                                else:
                                    chars.append(self.advance())
                        elif (
                            self.pos + 1 < self.length
                            and self.source[self.pos + 1] == "("
                        ):
                            cmdsub_result = self._parse_command_substitution()
                            cmdsub_node = cmdsub_result[0]
                            cmdsub_text = cmdsub_result[1]
                            if cmdsub_node:
                                parts.append(cmdsub_node)
                                chars.append(cmdsub_text)
                            else:
                                chars.append(self.advance())
                        else:
                            param_result = self._parse_param_expansion()
                            param_node = param_result[0]
                            param_text = param_result[1]
                            if param_node:
                                parts.append(param_node)
                                chars.append(param_text)
                            else:
                                chars.append(self.advance())
                    else:
                        chars.append(self.advance())
                if self.at_end():
                    raise ParseError("Unterminated double quote", pos=start)
                chars.append(self.advance())

            # Escape
            elif ch == "\\" and self.pos + 1 < self.length:
                chars.append(self.advance())
                chars.append(self.advance())

            # ANSI-C quoting $'...'
            elif (
                ch == "$"
                and self.pos + 1 < self.length
                and self.source[self.pos + 1] == "'"
            ):
                ansi_result = self._parse_ansi_c_quote()
                ansi_node = ansi_result[0]
                ansi_text = ansi_result[1]
                if ansi_node:
                    parts.append(ansi_node)
                    chars.append(ansi_text)
                else:
                    chars.append(self.advance())

            # Locale translation $"..."
            elif (
                ch == "$"
                and self.pos + 1 < self.length
                and self.source[self.pos + 1] == '"'
            ):
                locale_result = self._parse_locale_string()
                locale_node = locale_result[0]
                locale_text = locale_result[1]
                inner_parts = locale_result[2]
                if locale_node:
                    parts.append(locale_node)
                    parts.extend(inner_parts)
                    chars.append(locale_text)
                else:
                    chars.append(self.advance())

            # Arithmetic expansion $((...))
            elif (
                ch == "$"
                and self.pos + 2 < self.length
                and self.source[self.pos + 1] == "("
                and self.source[self.pos + 2] == "("
            ):
                arith_result = self._parse_arithmetic_expansion()
                arith_node = arith_result[0]
                arith_text = arith_result[1]
                if arith_node:
                    parts.append(arith_node)
                    chars.append(arith_text)
                else:
                    chars.append(self.advance())

            # Command substitution $(...)
            elif (
                ch == "$"
                and self.pos + 1 < self.length
                and self.source[self.pos + 1] == "("
            ):
                cmdsub_result = self._parse_command_substitution()
                cmdsub_node = cmdsub_result[0]
                cmdsub_text = cmdsub_result[1]
                if cmdsub_node:
                    parts.append(cmdsub_node)
                    chars.append(cmdsub_text)
                else:
                    chars.append(self.advance())

            # Parameter expansion $var or ${...}
            elif ch == "$":
                param_result = self._parse_param_expansion()
                param_node = param_result[0]
                param_text = param_result[1]
                if param_node:
                    parts.append(param_node)
                    chars.append(param_text)
                else:
                    chars.append(self.advance())

            # Process substitution <(...) or >(...)
            elif (
                _is_redirect_char(ch)
                and self.pos + 1 < self.length
                and self.source[self.pos + 1] == "("
            ):
                procsub_result = self._parse_process_substitution()
                procsub_node = procsub_result[0]
                procsub_text = procsub_result[1]
                if procsub_node:
                    parts.append(procsub_node)
                    chars.append(procsub_text)
                else:
                    chars.append(self.advance())

            # Backtick command substitution
            elif ch == "`":
                cmdsub_result = self._parse_backtick_substitution()
                cmdsub_node = cmdsub_result[0]
                cmdsub_text = cmdsub_result[1]
                if cmdsub_node:
                    parts.append(cmdsub_node)
                    chars.append(cmdsub_text)
                else:
                    chars.append(self.advance())

            # Regular character
            else:
                chars.append(self.advance())

        if not chars:
            return None

        parts_arg = None
        if parts:
            parts_arg = parts
        return Word("".join(chars), parts_arg)

    def _parse_cond_regex_word(self) -> Word | None:
        """Parse a regex pattern word in [[ ]], where ( ) are regex grouping, not conditional grouping."""
        self._cond_skip_whitespace()

        if self._cond_at_end():
            return None

        start = self.pos
        chars = []
        parts = []
        paren_depth = 0  # Track regex grouping parens - spaces inside don't terminate

        while not self.at_end():
            ch = self.peek()

            # End of conditional
            if (
                ch == "]"
                and self.pos + 1 < self.length
                and self.source[self.pos + 1] == "]"
            ):
                break

            # Backslash-newline continuation (check before space/escape handling)
            if (
                ch == "\\"
                and self.pos + 1 < self.length
                and self.source[self.pos + 1] == "\n"
            ):
                self.advance()  # consume backslash
                self.advance()  # consume newline
                continue

            # Escape sequences - consume both characters (including escaped spaces)
            if ch == "\\" and self.pos + 1 < self.length:
                chars.append(self.advance())
                chars.append(self.advance())
                continue

            # Track regex grouping parentheses
            if ch == "(":
                paren_depth += 1
                chars.append(self.advance())
                continue
            if ch == ")":
                if paren_depth > 0:
                    paren_depth -= 1
                    chars.append(self.advance())
                    continue
                # Unmatched ) - probably end of pattern
                break

            # Regex character class [...] - consume until closing ]
            # Handles [[:alpha:]], [^0-9], []a-z] (] as first char), etc.
            if ch == "[":
                chars.append(self.advance())  # consume [
                # Handle negation [^
                if not self.at_end() and self.peek() == "^":
                    chars.append(self.advance())
                # Handle ] as first char (literal ])
                if not self.at_end() and self.peek() == "]":
                    chars.append(self.advance())
                # Consume until closing ]
                while not self.at_end():
                    c = self.peek()
                    if c == "]":
                        chars.append(self.advance())
                        break
                    if (
                        c == "["
                        and self.pos + 1 < self.length
                        and self.source[self.pos + 1] == ":"
                    ):
                        # POSIX class like [:alpha:] inside bracket expression
                        chars.append(self.advance())  # [
                        chars.append(self.advance())  # :
                        while not self.at_end() and not (
                            self.peek() == ":"
                            and self.pos + 1 < self.length
                            and self.source[self.pos + 1] == "]"
                        ):
                            chars.append(self.advance())
                        if not self.at_end():
                            chars.append(self.advance())  # :
                            chars.append(self.advance())  # ]
                    elif c == "$":
                        # Handle parameter/arithmetic expansions inside bracket expression
                        if (
                            self.pos + 1 < self.length
                            and self.source[self.pos + 1] == "("
                        ):
                            # Could be $((...)) arithmetic or $(...) command substitution
                            if (
                                self.pos + 2 < self.length
                                and self.source[self.pos + 2] == "("
                            ):
                                # Arithmetic expansion $((...))
                                arith_result = self._parse_arithmetic_expansion()
                                arith_node = arith_result[0]
                                arith_text = arith_result[1]
                                if arith_node:
                                    parts.append(arith_node)
                                    chars.append(arith_text)
                                else:
                                    chars.append(self.advance())
                            else:
                                # Command substitution $(...)
                                cmdsub_result = self._parse_command_substitution()
                                cmdsub_node = cmdsub_result[0]
                                cmdsub_text = cmdsub_result[1]
                                if cmdsub_node:
                                    parts.append(cmdsub_node)
                                    chars.append(cmdsub_text)
                                else:
                                    chars.append(self.advance())
                        else:
                            # Parameter expansion ${...} or $var
                            param_result = self._parse_param_expansion()
                            param_node = param_result[0]
                            param_text = param_result[1]
                            if param_node:
                                parts.append(param_node)
                                chars.append(param_text)
                            else:
                                chars.append(self.advance())
                    else:
                        chars.append(self.advance())
                continue

            # Word terminators - space/tab ends the regex (unless inside parens), as do && and ||
            if _is_whitespace(ch) and paren_depth == 0:
                break
            if _is_whitespace(ch) and paren_depth > 0:
                # Space inside regex parens is part of the pattern
                chars.append(self.advance())
                continue
            if (
                ch == "&"
                and self.pos + 1 < self.length
                and self.source[self.pos + 1] == "&"
            ):
                break
            if (
                ch == "|"
                and self.pos + 1 < self.length
                and self.source[self.pos + 1] == "|"
            ):
                break

            # Single-quoted string
            if ch == "'":
                self.advance()
                chars.append("'")
                while not self.at_end() and self.peek() != "'":
                    chars.append(self.advance())
                if self.at_end():
                    raise ParseError("Unterminated single quote", pos=start)
                chars.append(self.advance())
                continue

            # Double-quoted string
            if ch == '"':
                self.advance()
                chars.append('"')
                while not self.at_end() and self.peek() != '"':
                    c = self.peek()
                    if c == "\\" and self.pos + 1 < self.length:
                        chars.append(self.advance())
                        chars.append(self.advance())
                    elif c == "$":
                        param_result = self._parse_param_expansion()
                        param_node = param_result[0]
                        param_text = param_result[1]
                        if param_node:
                            parts.append(param_node)
                            chars.append(param_text)
                        else:
                            chars.append(self.advance())
                    else:
                        chars.append(self.advance())
                if self.at_end():
                    raise ParseError("Unterminated double quote", pos=start)
                chars.append(self.advance())
                continue

            # Command substitution $(...) or parameter expansion $var or ${...}
            if ch == "$":
                # Try command substitution first
                if self.pos + 1 < self.length and self.source[self.pos + 1] == "(":
                    cmdsub_result = self._parse_command_substitution()
                    cmdsub_node = cmdsub_result[0]
                    cmdsub_text = cmdsub_result[1]
                    if cmdsub_node:
                        parts.append(cmdsub_node)
                        chars.append(cmdsub_text)
                        continue
                param_result = self._parse_param_expansion()
                param_node = param_result[0]
                param_text = param_result[1]
                if param_node:
                    parts.append(param_node)
                    chars.append(param_text)
                else:
                    chars.append(self.advance())
                continue

            # Regular character (including ( ) which are regex grouping)
            chars.append(self.advance())

        if not chars:
            return None

        parts_arg = None
        if parts:
            parts_arg = parts
        return Word("".join(chars), parts_arg)

    def parse_brace_group(self) -> BraceGroup | None:
        """Parse a brace group { list }."""
        self.skip_whitespace()
        if self.at_end() or self.peek() != "{":
            return None

        # Check that { is followed by whitespace or ( (it's a reserved word)
        # {( is valid: brace group containing a subshell
        if self.pos + 1 < self.length:
            next_ch = self.source[self.pos + 1]
            if not _is_whitespace(next_ch) and next_ch != "(":
                return None

        self.advance()  # consume {
        self.skip_whitespace_and_newlines()

        body = self.parse_list()
        if body is None:
            raise ParseError("Expected command in brace group", pos=self.pos)

        self.skip_whitespace()
        if self.at_end() or self.peek() != "}":
            raise ParseError("Expected } to close brace group", pos=self.pos)
        self.advance()  # consume }
        return BraceGroup(body, self._collect_redirects())

    def parse_if(self) -> If | None:
        """Parse an if statement: if list; then list [elif list; then list]* [else list] fi."""
        if not self.consume_word("if"):
            return None

        # Parse condition (a list that ends at 'then')
        condition = self.parse_list_until({"then"})
        if condition is None:
            raise ParseError("Expected condition after 'if'", pos=self.pos)

        # Expect 'then'
        self.skip_whitespace_and_newlines()
        if not self.consume_word("then"):
            raise ParseError("Expected 'then' after if condition", pos=self.pos)

        # Parse then body (ends at elif, else, or fi)
        then_body = self.parse_list_until({"elif", "else", "fi"})
        if then_body is None:
            raise ParseError("Expected commands after 'then'", pos=self.pos)

        # Check what comes next: elif, else, or fi
        self.skip_whitespace_and_newlines()
        next_word = self.peek_word()

        else_body = None
        if next_word == "elif":
            # elif is syntactic sugar for else if ... fi
            self.consume_word("elif")
            # Parse the rest as a nested if (but we've already consumed 'elif')
            # We need to parse: condition; then body [elif|else|fi]
            elif_condition = self.parse_list_until({"then"})
            if elif_condition is None:
                raise ParseError("Expected condition after 'elif'", pos=self.pos)

            self.skip_whitespace_and_newlines()
            if not self.consume_word("then"):
                raise ParseError("Expected 'then' after elif condition", pos=self.pos)

            elif_then_body = self.parse_list_until({"elif", "else", "fi"})
            if elif_then_body is None:
                raise ParseError("Expected commands after 'then'", pos=self.pos)

            # Recursively handle more elif/else/fi
            self.skip_whitespace_and_newlines()
            inner_next = self.peek_word()

            inner_else = None
            if inner_next == "elif":
                # More elif - recurse by creating a fake "if" and parsing
                # Actually, let's just recursively call a helper
                inner_else = self._parse_elif_chain()
            elif inner_next == "else":
                self.consume_word("else")
                inner_else = self.parse_list_until({"fi"})
                if inner_else is None:
                    raise ParseError("Expected commands after 'else'", pos=self.pos)

            else_body = If(elif_condition, elif_then_body, inner_else)

        elif next_word == "else":
            self.consume_word("else")
            else_body = self.parse_list_until({"fi"})
            if else_body is None:
                raise ParseError("Expected commands after 'else'", pos=self.pos)

        # Expect 'fi'
        self.skip_whitespace_and_newlines()
        if not self.consume_word("fi"):
            raise ParseError("Expected 'fi' to close if statement", pos=self.pos)
        return If(condition, then_body, else_body, self._collect_redirects())

    def _parse_elif_chain(self) -> If:
        """Parse elif chain (after seeing 'elif' keyword)."""
        self.consume_word("elif")

        condition = self.parse_list_until({"then"})
        if condition is None:
            raise ParseError("Expected condition after 'elif'", pos=self.pos)

        self.skip_whitespace_and_newlines()
        if not self.consume_word("then"):
            raise ParseError("Expected 'then' after elif condition", pos=self.pos)

        then_body = self.parse_list_until({"elif", "else", "fi"})
        if then_body is None:
            raise ParseError("Expected commands after 'then'", pos=self.pos)

        self.skip_whitespace_and_newlines()
        next_word = self.peek_word()

        else_body = None
        if next_word == "elif":
            else_body = self._parse_elif_chain()
        elif next_word == "else":
            self.consume_word("else")
            else_body = self.parse_list_until({"fi"})
            if else_body is None:
                raise ParseError("Expected commands after 'else'", pos=self.pos)

        return If(condition, then_body, else_body)

    def parse_while(self) -> While | None:
        """Parse a while loop: while list; do list; done."""
        if not self.consume_word("while"):
            return None

        # Parse condition (ends at 'do')
        condition = self.parse_list_until({"do"})
        if condition is None:
            raise ParseError("Expected condition after 'while'", pos=self.pos)

        # Expect 'do'
        self.skip_whitespace_and_newlines()
        if not self.consume_word("do"):
            raise ParseError("Expected 'do' after while condition", pos=self.pos)

        # Parse body (ends at 'done')
        body = self.parse_list_until({"done"})
        if body is None:
            raise ParseError("Expected commands after 'do'", pos=self.pos)

        # Expect 'done'
        self.skip_whitespace_and_newlines()
        if not self.consume_word("done"):
            raise ParseError("Expected 'done' to close while loop", pos=self.pos)
        return While(condition, body, self._collect_redirects())

    def parse_until(self) -> Until | None:
        """Parse an until loop: until list; do list; done."""
        if not self.consume_word("until"):
            return None

        # Parse condition (ends at 'do')
        condition = self.parse_list_until({"do"})
        if condition is None:
            raise ParseError("Expected condition after 'until'", pos=self.pos)

        # Expect 'do'
        self.skip_whitespace_and_newlines()
        if not self.consume_word("do"):
            raise ParseError("Expected 'do' after until condition", pos=self.pos)

        # Parse body (ends at 'done')
        body = self.parse_list_until({"done"})
        if body is None:
            raise ParseError("Expected commands after 'do'", pos=self.pos)

        # Expect 'done'
        self.skip_whitespace_and_newlines()
        if not self.consume_word("done"):
            raise ParseError("Expected 'done' to close until loop", pos=self.pos)
        return Until(condition, body, self._collect_redirects())

    def parse_for(self) -> For | ForArith | None:
        """Parse a for loop: for name [in words]; do list; done or C-style for ((;;))."""
        if not self.consume_word("for"):
            return None
        self.skip_whitespace()

        # Check for C-style for loop: for ((init; cond; incr))
        if (
            self.peek() == "("
            and self.pos + 1 < self.length
            and self.source[self.pos + 1] == "("
        ):
            return self._parse_for_arith()

        # Parse variable name (bash allows reserved words and command substitutions as variable names)
        if self.peek() == "$":
            # Command substitution as variable name: for $(echo i) in ...
            var_word = self.parse_word()
            if var_word is None:
                raise ParseError("Expected variable name after 'for'", pos=self.pos)
            var_name = var_word.value
        else:
            var_name = self.peek_word()
            if var_name is None:
                raise ParseError("Expected variable name after 'for'", pos=self.pos)
            self.consume_word(var_name)

        self.skip_whitespace()

        # Handle optional semicolon or newline before 'in' or 'do'
        if self.peek() == ";":
            self.advance()
        self.skip_whitespace_and_newlines()

        # Check for optional 'in' clause
        words = None
        if self.peek_word() == "in":
            self.consume_word("in")
            self.skip_whitespace_and_newlines()  # Allow newlines after 'in'

            # Parse words until semicolon, newline, or 'do'
            words = []
            while True:
                self.skip_whitespace()
                # Check for end of word list
                if self.at_end():
                    break
                if _is_semicolon_or_newline(self.peek()):
                    if self.peek() == ";":
                        self.advance()  # consume semicolon
                    break
                if self.peek_word() == "do":
                    break

                word = self.parse_word()
                if word is None:
                    break
                words.append(word)

        # Skip to 'do' or '{'
        self.skip_whitespace_and_newlines()

        # Check for brace group body as alternative to do/done
        if self.peek() == "{":
            # Bash allows: for x in a b; { cmd; }
            brace_group = self.parse_brace_group()
            if brace_group is None:
                raise ParseError("Expected brace group in for loop", pos=self.pos)
            return For(var_name, words, brace_group.body, self._collect_redirects())

        # Expect 'do'
        if not self.consume_word("do"):
            raise ParseError("Expected 'do' in for loop", pos=self.pos)

        # Parse body (ends at 'done')
        body = self.parse_list_until({"done"})
        if body is None:
            raise ParseError("Expected commands after 'do'", pos=self.pos)

        # Expect 'done'
        self.skip_whitespace_and_newlines()
        if not self.consume_word("done"):
            raise ParseError("Expected 'done' to close for loop", pos=self.pos)
        return For(var_name, words, body, self._collect_redirects())

    def _parse_for_arith(self) -> ForArith:
        """Parse C-style for loop: for ((init; cond; incr)); do list; done."""
        # We've already consumed 'for' and positioned at '(('
        self.advance()  # consume first (
        self.advance()  # consume second (

        # Parse the three expressions separated by semicolons
        # Each can be empty
        parts = []
        current = []
        paren_depth = 0

        while not self.at_end():
            ch = self.peek()
            if ch == "(":
                paren_depth += 1
                current.append(self.advance())
            elif ch == ")":
                if paren_depth > 0:
                    paren_depth -= 1
                    current.append(self.advance())
                else:
                    # Check for closing ))
                    if self.pos + 1 < self.length and self.source[self.pos + 1] == ")":
                        # End of ((...)) - preserve trailing whitespace
                        parts.append("".join(current).lstrip())
                        self.advance()  # consume first )
                        self.advance()  # consume second )
                        break
                    else:
                        current.append(self.advance())
            elif ch == ";" and paren_depth == 0:
                # Preserve trailing whitespace in expressions
                parts.append("".join(current).lstrip())
                current = []
                self.advance()  # consume ;
            else:
                current.append(self.advance())

        if len(parts) != 3:
            raise ParseError("Expected three expressions in for ((;;))", pos=self.pos)

        init = parts[0]
        cond = parts[1]
        incr = parts[2]

        self.skip_whitespace()

        # Handle optional semicolon
        if not self.at_end() and self.peek() == ";":
            self.advance()

        self.skip_whitespace_and_newlines()
        body = self._parse_loop_body("for loop")
        return ForArith(init, cond, incr, body, self._collect_redirects())

    def parse_select(self) -> Select | None:
        """Parse a select statement: select name [in words]; do list; done."""
        if not self.consume_word("select"):
            return None
        self.skip_whitespace()

        # Parse variable name
        var_name = self.peek_word()
        if var_name is None:
            raise ParseError("Expected variable name after 'select'", pos=self.pos)
        self.consume_word(var_name)

        self.skip_whitespace()

        # Handle optional semicolon before 'in', 'do', or '{'
        if self.peek() == ";":
            self.advance()
        self.skip_whitespace_and_newlines()

        # Check for optional 'in' clause
        words = None
        if self.peek_word() == "in":
            self.consume_word("in")
            self.skip_whitespace_and_newlines()  # Allow newlines after 'in'

            # Parse words until semicolon, newline, 'do', or '{'
            words = []
            while True:
                self.skip_whitespace()
                # Check for end of word list
                if self.at_end():
                    break
                if _is_semicolon_newline_brace(self.peek()):
                    if self.peek() == ";":
                        self.advance()  # consume semicolon
                    break
                if self.peek_word() == "do":
                    break

                word = self.parse_word()
                if word is None:
                    break
                words.append(word)

            # Empty word list is allowed for select (unlike for)

        # Skip whitespace before body
        self.skip_whitespace_and_newlines()
        body = self._parse_loop_body("select")
        return Select(var_name, words, body, self._collect_redirects())

    def _is_case_terminator(self) -> bool:
        """Check if we're at a case pattern terminator (;;, ;&, or ;;&)."""
        if self.at_end() or self.peek() != ";":
            return False
        if self.pos + 1 >= self.length:
            return False
        next_ch = self.source[self.pos + 1]
        # ;; or ;& or ;;& (which is actually ;;&)
        return _is_semicolon_or_amp(next_ch)

    def _consume_case_terminator(self) -> str:
        """Consume and return case pattern terminator (;;, ;&, or ;;&)."""
        if self.at_end() or self.peek() != ";":
            return ";;"  # default
        self.advance()  # consume first ;
        if self.at_end():
            return ";;"
        ch = self.peek()
        if ch == ";":
            self.advance()  # consume second ;
            # Check for ;;&
            if not self.at_end() and self.peek() == "&":
                self.advance()  # consume &
                return ";;&"
            return ";;"
        elif ch == "&":
            self.advance()  # consume &
            return ";&"
        return ";;"

    def parse_case(self) -> Case | None:
        """Parse a case statement: case word in pattern) commands;; ... esac."""
        if not self.consume_word("case"):
            return None
        self.skip_whitespace()

        # Parse the word to match
        word = self.parse_word()
        if word is None:
            raise ParseError("Expected word after 'case'", pos=self.pos)

        self.skip_whitespace_and_newlines()

        # Expect 'in'
        if not self.consume_word("in"):
            raise ParseError("Expected 'in' after case word", pos=self.pos)

        self.skip_whitespace_and_newlines()

        # Parse pattern clauses until 'esac'
        patterns = []
        while True:
            self.skip_whitespace_and_newlines()

            # Check if we're at 'esac' (but not 'esac)' which is esac as a pattern)
            if self.peek_word() == "esac":
                # Look ahead to see if esac is a pattern (esac followed by ) then body/;;)
                # or the closing keyword (esac followed by ) that closes containing construct)
                saved = self.pos
                self.skip_whitespace()
                # Consume "esac"
                while (
                    not self.at_end()
                    and not _is_metachar(self.peek())
                    and not _is_quote(self.peek())
                ):
                    self.advance()
                self.skip_whitespace()
                # Check for ) and what follows
                is_pattern = False
                if not self.at_end() and self.peek() == ")":
                    self.advance()  # consume )
                    self.skip_whitespace()
                    # esac is a pattern if there's body content or ;; after )
                    # Not a pattern if ) is followed by end, newline, or another )
                    if not self.at_end():
                        next_ch = self.peek()
                        # If followed by ;; or actual command content, it's a pattern
                        if next_ch == ";":
                            is_pattern = True
                        elif not _is_newline_or_right_paren(next_ch):
                            is_pattern = True
                self.pos = saved
                if not is_pattern:
                    break

            # Skip optional leading ( before pattern (POSIX allows this)
            self.skip_whitespace_and_newlines()
            if not self.at_end() and self.peek() == "(":
                self.advance()
                self.skip_whitespace_and_newlines()

            # Parse pattern (everything until ')' at depth 0)
            # Pattern can contain | for alternation, quotes, globs, extglobs, etc.
            # Extglob patterns @(), ?(), *(), +(), !() contain nested parens
            pattern_chars = []
            extglob_depth = 0
            while not self.at_end():
                ch = self.peek()
                if ch == ")":
                    if extglob_depth > 0:
                        # Inside extglob, consume the ) and decrement depth
                        pattern_chars.append(self.advance())
                        extglob_depth -= 1
                    else:
                        # End of pattern
                        self.advance()
                        break
                elif ch == "\\":
                    # Line continuation or backslash escape
                    if self.pos + 1 < self.length and self.source[self.pos + 1] == "\n":
                        # Line continuation - skip both backslash and newline
                        self.advance()
                        self.advance()
                    else:
                        # Normal escape - consume both chars
                        pattern_chars.append(self.advance())
                        if not self.at_end():
                            pattern_chars.append(self.advance())
                elif (
                    ch == "$"
                    and self.pos + 1 < self.length
                    and self.source[self.pos + 1] == "("
                ):
                    # $( or $(( - command sub or arithmetic
                    pattern_chars.append(self.advance())  # $
                    pattern_chars.append(self.advance())  # (
                    if not self.at_end() and self.peek() == "(":
                        # $(( arithmetic - need to find matching ))
                        pattern_chars.append(self.advance())  # second (
                        paren_depth = 2
                        while not self.at_end() and paren_depth > 0:
                            c = self.peek()
                            if c == "(":
                                paren_depth += 1
                            elif c == ")":
                                paren_depth -= 1
                            pattern_chars.append(self.advance())
                    else:
                        # $() command sub - track single paren
                        extglob_depth += 1
                elif ch == "(" and extglob_depth > 0:
                    # Grouping paren inside extglob
                    pattern_chars.append(self.advance())
                    extglob_depth += 1
                elif (
                    _is_extglob_prefix(ch)
                    and self.pos + 1 < self.length
                    and self.source[self.pos + 1] == "("
                ):
                    # Extglob opener: @(, ?(, *(, +(, !(
                    pattern_chars.append(self.advance())  # @, ?, *, +, or !
                    pattern_chars.append(self.advance())  # (
                    extglob_depth += 1
                elif ch == "[":
                    # Character class - but only if there's a matching ]
                    # ] must come before ) at same depth (either extglob or pattern)
                    is_char_class = False
                    scan_pos = self.pos + 1
                    scan_depth = 0
                    has_first_bracket_literal = False
                    # Skip [! or [^ at start
                    if scan_pos < self.length and _is_caret_or_bang(
                        self.source[scan_pos]
                    ):
                        scan_pos += 1
                    # Skip ] as first char (literal in char class) only if there's another ]
                    if scan_pos < self.length and self.source[scan_pos] == "]":
                        # Check if there's another ] later
                        if self.source.find("]", scan_pos + 1) != -1:
                            scan_pos += 1
                            has_first_bracket_literal = True
                    while scan_pos < self.length:
                        sc = self.source[scan_pos]
                        if sc == "]" and scan_depth == 0:
                            is_char_class = True
                            break
                        elif sc == "[":
                            scan_depth += 1
                        elif sc == ")" and scan_depth == 0:
                            # Hit pattern/extglob closer before finding ]
                            break
                        elif sc == "|" and scan_depth == 0 and extglob_depth > 0:
                            # Hit alternation in extglob - ] must be in this branch
                            break
                        scan_pos += 1
                    if is_char_class:
                        pattern_chars.append(self.advance())
                        # Handle [! or [^ at start
                        if not self.at_end() and _is_caret_or_bang(self.peek()):
                            pattern_chars.append(self.advance())
                        # Handle ] as first char (literal) only if we detected it in scan
                        if (
                            has_first_bracket_literal
                            and not self.at_end()
                            and self.peek() == "]"
                        ):
                            pattern_chars.append(self.advance())
                        # Consume until closing ]
                        while not self.at_end() and self.peek() != "]":
                            pattern_chars.append(self.advance())
                        if not self.at_end():
                            pattern_chars.append(self.advance())  # ]
                    else:
                        # Not a valid char class, treat [ as literal
                        pattern_chars.append(self.advance())
                elif ch == "'":
                    # Single-quoted string in pattern
                    pattern_chars.append(self.advance())
                    while not self.at_end() and self.peek() != "'":
                        pattern_chars.append(self.advance())
                    if not self.at_end():
                        pattern_chars.append(self.advance())
                elif ch == '"':
                    # Double-quoted string in pattern
                    pattern_chars.append(self.advance())
                    while not self.at_end() and self.peek() != '"':
                        if self.peek() == "\\" and self.pos + 1 < self.length:
                            pattern_chars.append(self.advance())
                        pattern_chars.append(self.advance())
                    if not self.at_end():
                        pattern_chars.append(self.advance())
                elif _is_whitespace(ch):
                    # Skip whitespace at top level, but preserve inside $() or extglob
                    if extglob_depth > 0:
                        pattern_chars.append(self.advance())
                    else:
                        self.advance()
                else:
                    pattern_chars.append(self.advance())

            pattern = "".join(pattern_chars)
            if not pattern:
                raise ParseError("Expected pattern in case statement", pos=self.pos)

            # Parse commands until ;;, ;&, ;;&, or esac
            # Commands are optional (can have empty body)
            self.skip_whitespace()

            body = None
            # Check for empty body: terminator right after pattern
            is_empty_body = self._is_case_terminator()

            if not is_empty_body:
                # Skip newlines and check if there's content before terminator or esac
                self.skip_whitespace_and_newlines()
                if not self.at_end() and self.peek_word() != "esac":
                    # Check again for terminator after whitespace/newlines
                    is_at_terminator = self._is_case_terminator()
                    if not is_at_terminator:
                        body = self.parse_list_until({"esac"})
                        self.skip_whitespace()

            # Handle terminator: ;;, ;&, or ;;&
            terminator = self._consume_case_terminator()

            self.skip_whitespace_and_newlines()

            patterns.append(CasePattern(pattern, body, terminator))

        # Expect 'esac'
        self.skip_whitespace_and_newlines()
        if not self.consume_word("esac"):
            raise ParseError("Expected 'esac' to close case statement", pos=self.pos)
        return Case(word, patterns, self._collect_redirects())

    def parse_coproc(self) -> Coproc | None:
        """Parse a coproc statement.

        bash-oracle behavior:
        - For compound commands (brace group, if, while, etc.), extract NAME if present
        - For simple commands, don't extract NAME (treat everything as the command)
        """
        if not self.consume_word("coproc"):
            return None
        self.skip_whitespace()

        name = None

        # Check for compound command directly (no NAME)
        ch = None
        if not self.at_end():
            ch = self.peek()
        if ch == "{":
            body = self.parse_brace_group()
            if body is not None:
                return Coproc(body, name)
        if ch == "(":
            if self.pos + 1 < self.length and self.source[self.pos + 1] == "(":
                body = self.parse_arithmetic_command()
                if body is not None:
                    return Coproc(body, name)
            body = self.parse_subshell()
            if body is not None:
                return Coproc(body, name)

        # Check for reserved word compounds directly
        next_word = self.peek_word()
        if next_word in COMPOUND_KEYWORDS:
            body = self.parse_compound_command()
            if body is not None:
                return Coproc(body, name)

        # Check if first word is NAME followed by compound command
        word_start = self.pos
        potential_name = self.peek_word()
        if potential_name:
            # Skip past the potential name
            while (
                not self.at_end()
                and not _is_metachar(self.peek())
                and not _is_quote(self.peek())
            ):
                self.advance()
            self.skip_whitespace()

            # Check what follows
            ch = None
            if not self.at_end():
                ch = self.peek()
            next_word = self.peek_word()

            if ch == "{":
                # NAME { ... } - extract name
                name = potential_name
                body = self.parse_brace_group()
                if body is not None:
                    return Coproc(body, name)
            elif ch == "(":
                # NAME ( ... ) - extract name
                name = potential_name
                if self.pos + 1 < self.length and self.source[self.pos + 1] == "(":
                    body = self.parse_arithmetic_command()
                else:
                    body = self.parse_subshell()
                if body is not None:
                    return Coproc(body, name)
            elif next_word in COMPOUND_KEYWORDS:
                # NAME followed by reserved compound - extract name
                name = potential_name
                body = self.parse_compound_command()
                if body is not None:
                    return Coproc(body, name)

            # Not followed by compound - restore position and parse as simple command
            self.pos = word_start

        # Parse as simple command (includes any "NAME" as part of the command)
        body = self.parse_command()
        if body is not None:
            return Coproc(body, name)

        raise ParseError("Expected command after coproc", pos=self.pos)

    def parse_function(self) -> Function | None:
        """Parse a function definition.

        Forms:
            name() compound_command           # POSIX form
            function name compound_command    # bash form without parens
            function name() compound_command  # bash form with parens
        """
        self.skip_whitespace()
        if self.at_end():
            return None

        saved_pos = self.pos

        # Check for 'function' keyword form
        if self.peek_word() == "function":
            self.consume_word("function")
            self.skip_whitespace()

            # Get function name
            name = self.peek_word()
            if name is None:
                self.pos = saved_pos
                return None
            self.consume_word(name)
            self.skip_whitespace()

            # Optional () after name - but only if it's actually ()
            # and not the start of a subshell body
            if not self.at_end() and self.peek() == "(":
                # Check if this is () or start of subshell
                if self.pos + 1 < self.length and self.source[self.pos + 1] == ")":
                    self.advance()  # consume (
                    self.advance()  # consume )
                # else: the ( is start of subshell body, don't consume

            self.skip_whitespace_and_newlines()

            # Parse body (any compound command)
            body = self._parse_compound_command()
            if body is None:
                raise ParseError("Expected function body", pos=self.pos)

            return Function(name, body)

        # Check for POSIX form: name()
        # We need to peek ahead to see if there's a () after the word
        name = self.peek_word()
        if name is None or name in RESERVED_WORDS:
            return None

        # Assignment words (containing =) are not function definitions
        if _str_contains(name, "="):
            return None

        # Save position after the name
        self.skip_whitespace()
        name_start = self.pos

        # Consume the name
        while (
            not self.at_end()
            and not _is_metachar(self.peek())
            and not _is_quote(self.peek())
            and not _is_paren(self.peek())
        ):
            self.advance()

        name = _substring(self.source, name_start, self.pos)
        if not name:
            self.pos = saved_pos
            return None

        # Check for () - whitespace IS allowed between name and (
        self.skip_whitespace()
        if self.at_end() or self.peek() != "(":
            self.pos = saved_pos
            return None

        self.advance()  # consume (
        self.skip_whitespace()
        if self.at_end() or self.peek() != ")":
            self.pos = saved_pos
            return None
        self.advance()  # consume )

        self.skip_whitespace_and_newlines()

        # Parse body (any compound command)
        body = self._parse_compound_command()
        if body is None:
            raise ParseError("Expected function body", pos=self.pos)

        return Function(name, body)

    def _parse_compound_command(self) -> Node | None:
        """Parse any compound command (for function bodies, etc.)."""
        # Try each compound command type
        result = self.parse_brace_group()
        if result:
            return result

        result = self.parse_subshell()
        if result:
            return result

        result = self.parse_conditional_expr()
        if result:
            return result

        result = self.parse_if()
        if result:
            return result

        result = self.parse_while()
        if result:
            return result

        result = self.parse_until()
        if result:
            return result

        result = self.parse_for()
        if result:
            return result

        result = self.parse_case()
        if result:
            return result

        result = self.parse_select()
        if result:
            return result

        return None

    def parse_list_until(self, stop_words: set[str]) -> Node | None:
        """Parse a list that stops before certain reserved words."""
        # Check if we're already at a stop word
        self.skip_whitespace_and_newlines()
        if self.peek_word() in stop_words:
            return None

        pipeline = self.parse_pipeline()
        if pipeline is None:
            return None

        parts = [pipeline]

        while True:
            # Check for newline as implicit command separator
            self.skip_whitespace()
            has_newline = False
            while not self.at_end() and self.peek() == "\n":
                has_newline = True
                self.advance()
                # Skip past any pending heredoc content after newline
                if (
                    self._pending_heredoc_end is not None
                    and self._pending_heredoc_end > self.pos
                ):
                    self.pos = self._pending_heredoc_end
                    self._pending_heredoc_end = None
                self.skip_whitespace()

            op = self.parse_list_operator()

            # Newline acts as implicit semicolon if followed by more commands
            if op is None and has_newline:
                # Check if there's another command (not a stop word)
                if (
                    not self.at_end()
                    and self.peek_word() not in stop_words
                    and not _is_right_bracket(self.peek())
                ):
                    op = "\n"  # Newline separator (distinct from explicit ;)

            if op is None:
                break

            # For & at end of list, don't require another command
            if op == "&":
                parts.append(Operator(op))
                self.skip_whitespace_and_newlines()
                if (
                    self.at_end()
                    or self.peek_word() in stop_words
                    or _is_newline_or_right_bracket(self.peek())
                ):
                    break

            # For ; - check if it's a terminator before a stop word (don't include it)
            if op == ";":
                self.skip_whitespace_and_newlines()
                # Also check for ;;, ;&, or ;;& (case terminators)
                at_case_terminator = (
                    self.peek() == ";"
                    and self.pos + 1 < self.length
                    and _is_semicolon_or_amp(self.source[self.pos + 1])
                )
                if (
                    self.at_end()
                    or self.peek_word() in stop_words
                    or _is_newline_or_right_bracket(self.peek())
                    or at_case_terminator
                ):
                    # Don't include trailing semicolon - it's just a terminator
                    break
                parts.append(Operator(op))
            elif op != "&":
                parts.append(Operator(op))

            # Check for stop words before parsing next pipeline
            self.skip_whitespace_and_newlines()
            # Also check for ;;, ;&, or ;;& (case terminators)
            if self.peek_word() in stop_words:
                break
            if (
                self.peek() == ";"
                and self.pos + 1 < self.length
                and _is_semicolon_or_amp(self.source[self.pos + 1])
            ):
                break

            pipeline = self.parse_pipeline()
            if pipeline is None:
                raise ParseError("Expected command after " + op, pos=self.pos)
            parts.append(pipeline)

        if len(parts) == 1:
            return parts[0]
        return List(parts)

    def parse_compound_command(self) -> Node | None:
        """Parse a compound command (subshell, brace group, if, loops, or simple command)."""
        self.skip_whitespace()
        if self.at_end():
            return None

        ch = self.peek()

        # Arithmetic command ((...)) - check before subshell
        if (
            ch == "("
            and self.pos + 1 < self.length
            and self.source[self.pos + 1] == "("
        ):
            result = self.parse_arithmetic_command()
            if result is not None:
                return result
            # Not arithmetic (e.g., '(( x ) )' is nested subshells) - fall through

        # Subshell
        if ch == "(":
            return self.parse_subshell()

        # Brace group
        if ch == "{":
            result = self.parse_brace_group()
            if result is not None:
                return result
            # Fall through to simple command if not a brace group

        # Conditional expression [[ ]] - check before reserved words
        if (
            ch == "["
            and self.pos + 1 < self.length
            and self.source[self.pos + 1] == "["
        ):
            return self.parse_conditional_expr()

        # Check for reserved words
        word = self.peek_word()

        # Reserved words that cannot start a statement (only valid in specific contexts)
        if word in ("fi", "then", "elif", "else", "done", "esac", "do", "in"):
            raise ParseError(f"Unexpected reserved word '{word}'", pos=self.pos)

        # If statement
        if word == "if":
            return self.parse_if()

        # While loop
        if word == "while":
            return self.parse_while()

        # Until loop
        if word == "until":
            return self.parse_until()

        # For loop
        if word == "for":
            return self.parse_for()

        # Select statement
        if word == "select":
            return self.parse_select()

        # Case statement
        if word == "case":
            return self.parse_case()

        # Function definition (function keyword form)
        if word == "function":
            return self.parse_function()

        # Coproc
        if word == "coproc":
            return self.parse_coproc()

        # Try POSIX function definition (name() form) before simple command
        func = self.parse_function()
        if func is not None:
            return func

        # Simple command
        return self.parse_command()

    def parse_pipeline(self) -> Node | None:
        """Parse a pipeline (commands separated by |), with optional time/negation prefix."""
        self.skip_whitespace()

        # Track order of prefixes: "time", "negation", or "time_negation" or "negation_time"
        prefix_order = None
        time_posix = False

        # Check for 'time' prefix first
        if self.peek_word() == "time":
            self.consume_word("time")
            prefix_order = "time"
            self.skip_whitespace()
            # Check for -p flag
            if not self.at_end() and self.peek() == "-":
                saved = self.pos
                self.advance()
                if not self.at_end() and self.peek() == "p":
                    self.advance()
                    if self.at_end() or _is_whitespace(self.peek()):
                        time_posix = True
                    else:
                        self.pos = saved
                else:
                    self.pos = saved
            self.skip_whitespace()
            # Check for -- (end of options) - implies -p per bash-oracle
            if not self.at_end() and _starts_with_at(self.source, self.pos, "--"):
                if self.pos + 2 >= self.length or _is_whitespace(
                    self.source[self.pos + 2]
                ):
                    self.advance()
                    self.advance()
                    time_posix = True
                    self.skip_whitespace()
            # Skip nested time keywords (time time X collapses to time X)
            while self.peek_word() == "time":
                self.consume_word("time")
                self.skip_whitespace()
                # Check for -p after nested time
                if not self.at_end() and self.peek() == "-":
                    saved = self.pos
                    self.advance()
                    if not self.at_end() and self.peek() == "p":
                        self.advance()
                        if self.at_end() or _is_whitespace(self.peek()):
                            time_posix = True
                        else:
                            self.pos = saved
                    else:
                        self.pos = saved
                self.skip_whitespace()
            # Check for ! after time
            if not self.at_end() and self.peek() == "!":
                if self.pos + 1 >= self.length or _is_whitespace(
                    self.source[self.pos + 1]
                ):
                    self.advance()
                    prefix_order = "time_negation"
                    self.skip_whitespace()

        # Check for '!' negation prefix (if no time yet)
        elif not self.at_end() and self.peek() == "!":
            if self.pos + 1 >= self.length or _is_whitespace(self.source[self.pos + 1]):
                self.advance()
                self.skip_whitespace()
                # Recursively parse pipeline to handle ! ! cmd, ! time cmd, etc.
                # Bare ! (no following command) is valid POSIX - equivalent to false
                inner = self.parse_pipeline()
                # Double negation cancels out (! ! cmd -> cmd, ! ! -> empty command)
                if inner is not None and inner.kind == "negation":
                    if inner.pipeline is not None:
                        return inner.pipeline
                    else:
                        return Command([])
                return Negation(inner)

        # Parse the actual pipeline
        result = self._parse_simple_pipeline()

        # Wrap based on prefix order
        # Note: bare time and time ! are valid (null command timing)
        if prefix_order == "time":
            result = Time(result, time_posix)
        elif prefix_order == "negation":
            result = Negation(result)
        elif prefix_order == "time_negation":
            # time ! cmd -> Negation(Time(cmd)) per bash-oracle
            result = Time(result, time_posix)
            result = Negation(result)
        elif prefix_order == "negation_time":
            # ! time cmd -> Negation(Time(cmd))
            result = Time(result, time_posix)
            result = Negation(result)
        elif result is None:
            # No prefix and no pipeline
            return None

        return result

    def _parse_simple_pipeline(self) -> Node | None:
        """Parse a simple pipeline (commands separated by | or |&) without time/negation."""
        cmd = self.parse_compound_command()
        if cmd is None:
            return None

        commands = [cmd]

        while True:
            self.skip_whitespace()
            if self.at_end() or self.peek() != "|":
                break
            # Check it's not ||
            if self.pos + 1 < self.length and self.source[self.pos + 1] == "|":
                break

            self.advance()  # consume |

            # Check for |& (pipe stderr)
            is_pipe_both = False
            if not self.at_end() and self.peek() == "&":
                self.advance()  # consume &
                is_pipe_both = True

            self.skip_whitespace_and_newlines()  # Allow command on next line after pipe

            # Add pipe-both marker if this is a |& pipe
            if is_pipe_both:
                commands.append(PipeBoth())

            cmd = self.parse_compound_command()
            if cmd is None:
                raise ParseError("Expected command after |", pos=self.pos)
            commands.append(cmd)

        if len(commands) == 1:
            return commands[0]
        return Pipeline(commands)

    def parse_list_operator(self) -> str | None:
        """Parse a list operator (&&, ||, ;, &)."""
        self.skip_whitespace()
        if self.at_end():
            return None

        ch = self.peek()

        if ch == "&":
            # Check if this is &> or &>> (redirect), not background operator
            if self.pos + 1 < self.length and self.source[self.pos + 1] == ">":
                return None  # Let redirect parser handle &> and &>>
            self.advance()
            if not self.at_end() and self.peek() == "&":
                self.advance()
                return "&&"
            return "&"

        if ch == "|":
            if self.pos + 1 < self.length and self.source[self.pos + 1] == "|":
                self.advance()
                self.advance()
                return "||"
            return None  # single | is pipe, not list operator

        if ch == ";":
            # Don't treat ;;, ;&, or ;;& as a single semicolon (they're case terminators)
            if self.pos + 1 < self.length and _is_semicolon_or_amp(
                self.source[self.pos + 1]
            ):
                return None
            self.advance()
            return ";"

        return None

    def parse_list(self, newline_as_separator: bool = True) -> Node | None:
        """Parse a command list (pipelines separated by &&, ||, ;, &).

        Args:
            newline_as_separator: If True, treat newlines as implicit semicolons.
                If False, stop at newlines (for top-level parsing).
        """
        if newline_as_separator:
            self.skip_whitespace_and_newlines()
        else:
            self.skip_whitespace()
        pipeline = self.parse_pipeline()
        if pipeline is None:
            return None

        parts = [pipeline]

        while True:
            # Check for newline as implicit command separator
            self.skip_whitespace()
            has_newline = False
            while not self.at_end() and self.peek() == "\n":
                has_newline = True
                # If not treating newlines as separators, stop here
                if not newline_as_separator:
                    break
                self.advance()
                # Skip past any pending heredoc content after newline
                if (
                    self._pending_heredoc_end is not None
                    and self._pending_heredoc_end > self.pos
                ):
                    self.pos = self._pending_heredoc_end
                    self._pending_heredoc_end = None
                self.skip_whitespace()

            # If we hit a newline and not treating them as separators, stop
            if has_newline and not newline_as_separator:
                break

            op = self.parse_list_operator()

            # Newline acts as implicit semicolon if followed by more commands
            if op is None and has_newline:
                if not self.at_end() and not _is_right_bracket(self.peek()):
                    op = "\n"  # Newline separator (distinct from explicit ;)

            if op is None:
                break

            # Don't add duplicate semicolon (e.g., explicit ; followed by newline)
            if not (
                op == ";"
                and parts
                and parts[len(parts) - 1].kind == "operator"
                and parts[len(parts) - 1].op == ";"
            ):
                parts.append(Operator(op))

            # For & at end of list, don't require another command
            if op == "&":
                self.skip_whitespace()
                if self.at_end() or _is_right_bracket(self.peek()):
                    break
                # Newline after & - in compound commands, skip it (& acts as separator)
                # At top level, newline terminates (separate commands)
                if self.peek() == "\n":
                    if newline_as_separator:
                        self.skip_whitespace_and_newlines()
                        if self.at_end() or _is_right_bracket(self.peek()):
                            break
                    else:
                        break  # Top-level: newline ends this list

            # For ; at end of list, don't require another command
            if op == ";":
                self.skip_whitespace()
                if self.at_end() or _is_right_bracket(self.peek()):
                    break
                # Newline after ; means continue to see if more commands follow
                if self.peek() == "\n":
                    continue

            # For && and ||, allow newlines before the next command
            if op == "&&" or op == "||":
                self.skip_whitespace_and_newlines()

            pipeline = self.parse_pipeline()
            if pipeline is None:
                raise ParseError("Expected command after " + op, pos=self.pos)
            parts.append(pipeline)

        if len(parts) == 1:
            return parts[0]
        return List(parts)

    def parse_comment(self) -> Node | None:
        """Parse a comment (# to end of line)."""
        if self.at_end() or self.peek() != "#":
            return None
        start = self.pos
        while not self.at_end() and self.peek() != "\n":
            self.advance()
        text = _substring(self.source, start, self.pos)
        return Comment(text)

    def parse(self) -> list[Node]:
        """Parse the entire input."""
        source = self.source.strip()
        if not source:
            return [Empty()]

        results = []

        # Skip leading comments (bash-oracle doesn't output them)
        while True:
            self.skip_whitespace()
            # Skip newlines but not comments
            while not self.at_end() and self.peek() == "\n":
                self.advance()
            if self.at_end():
                break
            comment = self.parse_comment()
            if not comment:
                break
            # Don't add to results - bash-oracle doesn't output comments

        # Parse statements separated by newlines as separate top-level nodes
        while not self.at_end():
            result = self.parse_list(newline_as_separator=False)
            if result is not None:
                results.append(result)

            self.skip_whitespace()

            # Skip newlines (and any pending heredoc content) between statements
            found_newline = False
            while not self.at_end() and self.peek() == "\n":
                found_newline = True
                self.advance()
                # Skip past any pending heredoc content after newline
                if (
                    self._pending_heredoc_end is not None
                    and self._pending_heredoc_end > self.pos
                ):
                    self.pos = self._pending_heredoc_end
                    self._pending_heredoc_end = None
                self.skip_whitespace()

            # If no newline and not at end, we have unparsed content
            if not found_newline and not self.at_end():
                raise ParseError("Parser not fully implemented yet", pos=self.pos)

        if not results:
            return [Empty()]

        return results


def parse(source: str) -> list[Node]:
    """
    Parse bash source code and return a list of AST nodes.

    Args:
        source: The bash source code to parse.

    Returns:
        A list of AST nodes representing the parsed code.

    Raises:
        ParseError: If the source code cannot be parsed.
    """
    parser = Parser(source)
    return parser.parse()
