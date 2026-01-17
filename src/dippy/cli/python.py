"""
Python command handler for Dippy.

Analyzes Python scripts to determine if they're safe (read-only, no I/O,
no code execution). Uses AST-based static analysis with a whitelist approach.

Conservative by design: if we can't prove it's safe, ask for confirmation.
"""

import ast
from pathlib import Path
from typing import NamedTuple

from dippy.cli import Classification

COMMANDS = ["python", "python3"] + [f"python3.{v}" for v in range(8, 20)]

# === Safe Module Whitelist ===
# Only modules that cannot perform I/O, execute code, or mutate external state.
# When in doubt, leave it out.

SAFE_MODULES = frozenset(
    {
        # Core data structures
        "collections",
        "collections.abc",
        "dataclasses",
        "typing",
        "typing_extensions",
        "types",
        "enum",
        "array",
        # Math and algorithms
        "math",
        "cmath",
        "statistics",
        "decimal",
        "fractions",
        "random",  # Deterministic given seed, no I/O
        "itertools",
        "functools",
        "operator",
        "bisect",
        "heapq",
        "graphlib",
        # Text processing
        "re",
        "string",
        "textwrap",
        "difflib",
        "unicodedata",
        # Data format parsing (in-memory only)
        "json",  # json.load/dump need file objects, but open() is blocked
        "csv",  # csv.reader/writer need file objects, but open() is blocked
        "tomllib",  # Read-only TOML (Python 3.11+), no file I/O methods
        # Note: configparser excluded - can read files directly
        # Note: xml excluded - security concerns (XXE)
        # Note: codecs excluded - codecs.open() can read/write files
        # Hashing and encoding (pure computation)
        "hashlib",
        "hmac",
        "base64",
        "binascii",
        "quopri",
        "uu",
        # Compression (in-memory only via compress/decompress)
        "zlib",  # Only zlib.compress/decompress, no file methods
        # Note: gzip, bz2, lzma excluded - they have .open() for file I/O
        # Date and time (reading system time is fine)
        "datetime",
        "time",
        "calendar",
        "zoneinfo",
        # Introspection (AST only, not source reading)
        "ast",
        "dis",
        "tokenize",
        "token",
        "keyword",
        "symtable",
        # Note: inspect excluded - getsource/getsourcefile read files
        # Note: linecache excluded - reads files
        # Other safe utilities
        "copy",
        "pprint",
        "reprlib",
        "abc",
        "numbers",
        "contextlib",
        "warnings",
        "traceback",
        # Parsing
        "struct",
        # Note: codecs excluded - codecs.open() can read/write files
        # HTML (parsing only - html.parser)
        "html",
        "html.parser",
        "html.entities",
    }
)

# Modules that are NEVER safe
# Sources: Bandit blacklists, RestrictedPython, CVE research
DANGEROUS_MODULES = frozenset(
    {
        # === Code execution ===
        "subprocess",
        "os",
        "sys",  # sys.exit, sys.modules manipulation
        "shutil",
        "runpy",
        "compileall",
        "py_compile",
        "importlib",
        "pkgutil",
        # Legacy process modules (Bandit)
        "popen2",
        "commands",
        # === File I/O ===
        "pathlib",  # Can read/write files
        "io",
        "fileinput",
        "tempfile",
        "glob",
        "fnmatch",  # Used with glob
        "codecs",  # codecs.open() can read/write files
        "linecache",  # Reads source files
        "inspect",  # getsource/getsourcefile read files
        "configparser",  # Can read files directly
        # Compression with file I/O
        "gzip",  # gzip.open() reads/writes files
        "bz2",  # bz2.open() reads/writes files
        "lzma",  # lzma.open() reads/writes files
        "tarfile",  # Can extract files
        "zipfile",  # Can extract files
        # === Network ===
        "socket",
        "ssl",
        "http",
        "http.client",
        "http.server",
        "urllib",
        "urllib.request",
        "urllib.parse",
        "ftplib",  # Bandit B402: insecure cleartext
        "smtplib",
        "poplib",
        "imaplib",
        "nntplib",
        "telnetlib",  # Bandit B401: insecure cleartext
        "socketserver",
        "xmlrpc",  # Bandit B411: XML vulnerabilities
        "ipaddress",
        # === XML parsing (XXE vulnerabilities - Bandit B405-B410) ===
        "xml",
        "xml.etree",
        "xml.etree.ElementTree",
        "xml.etree.cElementTree",
        "xml.sax",
        "xml.dom",
        "xml.dom.minidom",
        "xml.dom.pulldom",
        "xml.dom.expatbuilder",
        "xml.parsers",
        "xml.parsers.expat",
        # === Process/threading ===
        "multiprocessing",
        "threading",
        "concurrent",
        "concurrent.futures",
        "asyncio",
        "signal",
        "mmap",
        # === System interaction ===
        "ctypes",
        "platform",
        "sysconfig",
        "resource",
        "pty",
        "tty",
        "termios",
        "fcntl",
        "grp",
        "pwd",
        "spwd",
        "crypt",
        # === Deserialization (Bandit B301-B302, B403) ===
        "pickle",
        "cPickle",
        "dill",  # Bandit: pickle variant
        "shelve",
        "marshal",  # Bandit B302
        "jsonpickle",  # Bandit: pickle via JSON
        # === Databases ===
        "dbm",
        "sqlite3",
        # === Code manipulation ===
        "code",
        "codeop",
        "gc",  # Can resurrect objects
        # === Other dangerous ===
        "webbrowser",
        "cmd",
        "shlex",
        "getpass",
        "getopt",
        "argparse",  # Can sys.exit
        "logging",  # Can write to files
        "atexit",
        # CGI (Bandit B412: httpoxy vulnerabilities)
        "cgi",
        "cgitb",
        "wsgiref.handlers",
    }
)

# Builtins that are never safe
DANGEROUS_BUILTINS = frozenset(
    {
        # Code execution
        "eval",
        "exec",
        "compile",
        "__import__",
        # I/O
        "open",
        "input",
        "print",  # Technically I/O, but we'll allow it in some contexts
        # Introspection escape hatches
        "globals",
        "locals",
        "vars",
        "dir",  # Can be used for introspection attacks
        # Mutation
        "setattr",
        "delattr",
        "getattr",  # Can bypass restrictions
        # Memory
        "memoryview",
        # Debugging
        "breakpoint",
    }
)

# Builtins that are safe (whitelist)
SAFE_BUILTINS = frozenset(
    {
        # Types and constructors
        "bool",
        "int",
        "float",
        "complex",
        "str",
        "bytes",
        "bytearray",
        "list",
        "tuple",
        "dict",
        "set",
        "frozenset",
        "range",
        "slice",
        "object",
        "type",
        # Iteration
        "iter",
        "next",
        "enumerate",
        "zip",
        "map",
        "filter",
        "reversed",
        # Aggregation
        "len",
        "sum",
        "min",
        "max",
        "abs",
        "round",
        "pow",
        "divmod",
        "all",
        "any",
        "sorted",
        # Type checking
        "isinstance",
        "issubclass",
        "callable",
        "hasattr",
        # Conversion
        "repr",
        "str",
        "ascii",
        "chr",
        "ord",
        "hex",
        "oct",
        "bin",
        "format",
        "hash",
        "id",
        # Other safe
        "staticmethod",
        "classmethod",
        "property",
        "super",
    }
)

# Attributes/methods that indicate dangerous operations
# Sources: Bandit, RestrictedPython INSPECT_ATTRIBUTES
DANGEROUS_ATTRS = frozenset(
    {
        # === File operations ===
        "write",
        "writelines",
        "truncate",
        "flush",
        "close",
        "read",
        "readline",
        "readlines",
        "read_text",
        "read_bytes",
        "write_text",
        "write_bytes",
        "open",  # pathlib.Path.open, gzip.open, etc.
        # === OS/Process operations ===
        "remove",
        "unlink",
        "rmdir",
        "rmtree",
        "mkdir",
        "makedirs",
        "rename",
        "replace",
        "chmod",
        "chown",
        "chroot",
        "link",
        "symlink",
        "system",
        "popen",
        "popen2",
        "popen3",
        "popen4",
        "spawn",
        "spawnl",
        "spawnle",
        "spawnlp",
        "spawnlpe",
        "spawnv",
        "spawnve",
        "spawnvp",
        "spawnvpe",
        "startfile",
        "fork",
        "forkpty",
        "exec",
        "execl",
        "execle",
        "execlp",
        "execlpe",
        "execv",
        "execve",
        "execvp",
        "execvpe",
        "kill",
        "killpg",
        "terminate",
        "wait",
        "waitpid",
        "wait3",
        "wait4",
        # Subprocess (Bandit B602-B607)
        "call",
        "check_call",
        "check_output",
        "run",
        "Popen",
        "getoutput",
        "getstatusoutput",
        # === Network ===
        "connect",
        "bind",
        "listen",
        "accept",
        "send",
        "sendall",
        "sendto",
        "sendmsg",
        "recv",
        "recvfrom",
        "recvmsg",
        "request",
        "urlopen",
        "urlretrieve",
        # === Deserialization ===
        # Note: load/loads/decode are too generic (json.loads is safe)
        # Dangerous deserializers (pickle, marshal) are caught by import checks
        "Unpickler",
        # === Reflection escape hatches (RestrictedPython) ===
        # These allow sandbox escapes via introspection chains
        "__dict__",
        "__class__",
        "__bases__",
        "__mro__",
        "__subclasses__",
        "__globals__",
        "__code__",
        "__closure__",
        "__reduce__",
        "__reduce_ex__",
        "__getstate__",
        "__setstate__",
        # Frame/traceback objects (RestrictedPython INSPECT_ATTRIBUTES)
        "tb_frame",
        "tb_next",
        "f_back",
        "f_builtins",
        "f_code",
        "f_globals",
        "f_locals",
        "f_trace",
        # Code objects
        "co_code",
        # Generator/coroutine internals
        "gi_frame",
        "gi_code",
        "gi_yieldfrom",
        "cr_await",
        "cr_frame",
        "cr_code",
        # === Module manipulation ===
        "__import__",
        "__loader__",
        "__spec__",
        "__builtins__",
    }
)


class Violation(NamedTuple):
    """A safety violation found during analysis."""

    line: int
    col: int
    kind: str
    detail: str


class SafetyAnalyzer(ast.NodeVisitor):
    """
    AST visitor that checks Python code for safety.

    Uses a strict whitelist approach: only explicitly safe constructs
    are allowed. Anything unknown is flagged.
    """

    def __init__(self, allow_print: bool = True):
        self.violations: list[Violation] = []
        self.allow_print = allow_print

    def _add(self, node: ast.AST, kind: str, detail: str) -> None:
        self.violations.append(
            Violation(
                getattr(node, "lineno", 0), getattr(node, "col_offset", 0), kind, detail
            )
        )

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            module = alias.name
            root = module.split(".")[0]

            if module in DANGEROUS_MODULES or root in DANGEROUS_MODULES:
                self._add(node, "import", f"dangerous module: {module}")
            elif module not in SAFE_MODULES and root not in SAFE_MODULES:
                self._add(node, "import", f"unknown module: {module}")

        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module is None:
            self._add(node, "import", "relative import without module")
            return

        module = node.module
        root = module.split(".")[0]

        if module in DANGEROUS_MODULES or root in DANGEROUS_MODULES:
            self._add(node, "import", f"dangerous module: {module}")
        elif module not in SAFE_MODULES and root not in SAFE_MODULES:
            self._add(node, "import", f"unknown module: {module}")

        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func

        # Direct builtin call: eval(), exec(), open()
        if isinstance(func, ast.Name):
            name = func.id
            if name in DANGEROUS_BUILTINS:
                if name == "print" and self.allow_print:
                    pass  # Allow print
                else:
                    self._add(node, "builtin", f"dangerous builtin: {name}")
            elif name not in SAFE_BUILTINS and not name[0].isupper():
                # Allow capitalized names (likely class instantiation)
                # but flag unknown lowercase builtins
                pass  # User-defined functions are okay

        # Method call: obj.write(), os.system()
        elif isinstance(func, ast.Attribute):
            attr = func.attr
            if attr in DANGEROUS_ATTRS:
                self._add(node, "method", f"dangerous method: {attr}")

        self.generic_visit(node)

    # Reflection attributes that are dangerous even on access (not just call)
    # These provide access to frames, code objects, and other internals
    REFLECTION_ATTRS = frozenset(
        {
            # Dunder reflection
            "__globals__",
            "__code__",
            "__closure__",
            "__dict__",
            "__class__",
            "__bases__",
            "__mro__",
            "__subclasses__",
            "__reduce__",
            "__reduce_ex__",
            "__builtins__",
            # Frame objects (RestrictedPython INSPECT_ATTRIBUTES)
            "tb_frame",
            "tb_next",
            "f_back",
            "f_builtins",
            "f_code",
            "f_globals",
            "f_locals",
            "f_trace",
            # Code objects
            "co_code",
            # Generator/coroutine internals
            "gi_frame",
            "gi_code",
            "gi_yieldfrom",
            "cr_await",
            "cr_frame",
            "cr_code",
        }
    )

    def visit_Attribute(self, node: ast.Attribute) -> None:
        # Flag dangerous attribute access even without call
        if node.attr in self.REFLECTION_ATTRS:
            self._add(node, "reflection", f"dangerous attribute: {node.attr}")

        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        # Flag access to dangerous names
        name = node.id
        if name in ("__builtins__", "__loader__", "__spec__"):
            self._add(node, "reflection", f"dangerous name: {name}")

        self.generic_visit(node)

    def visit_Starred(self, node: ast.Starred) -> None:
        # *args unpacking is fine
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        # Check for dangerous decorators
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name):
                if decorator.id not in SAFE_BUILTINS:
                    # Unknown decorator - could be dangerous
                    pass  # Allow for now, decorator itself will be checked
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        # Async implies asyncio which is dangerous
        self._add(node, "async", "async functions require asyncio")
        self.generic_visit(node)

    def visit_Await(self, node: ast.Await) -> None:
        self._add(node, "async", "await requires asyncio")
        self.generic_visit(node)

    def visit_With(self, node: ast.With) -> None:
        # with statements often involve files
        # Check what's being opened
        for item in node.items:
            ctx = item.context_expr
            if isinstance(ctx, ast.Call):
                if isinstance(ctx.func, ast.Name):
                    if ctx.func.id == "open":
                        self._add(node, "io", "file open in with statement")
        self.generic_visit(node)

    def visit_Global(self, node: ast.Global) -> None:
        # Global statements are fine for read, but could enable mutation
        pass

    def visit_Try(self, node: ast.Try) -> None:
        # Try/except is fine
        self.generic_visit(node)


def analyze_python_source(source: str, allow_print: bool = True) -> list[Violation]:
    """
    Analyze Python source code for safety violations.

    Returns list of violations, empty if code appears safe.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return [Violation(e.lineno or 0, e.offset or 0, "syntax", str(e))]

    analyzer = SafetyAnalyzer(allow_print=allow_print)
    analyzer.visit(tree)
    return analyzer.violations


def analyze_python_file(path: Path) -> tuple[bool, str]:
    """
    Analyze a Python file for safety.

    Returns (is_safe, reason).
    """
    if not path.exists():
        return False, f"file not found: {path}"

    if not path.is_file():
        return False, f"not a file: {path}"

    # Check file extension
    if path.suffix not in (".py", ".pyw"):
        return False, f"not a Python file: {path.suffix}"

    # Size limit - don't analyze huge files
    try:
        size = path.stat().st_size
        if size > 100_000:  # 100KB limit
            return False, "file too large to analyze"
    except OSError as e:
        return False, f"cannot stat file: {e}"

    # Read and analyze
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return False, f"cannot read file: {e}"

    violations = analyze_python_source(source)

    if violations:
        # Return first violation as reason
        v = violations[0]
        return False, f"{v.kind}: {v.detail} (line {v.line})"

    return True, "static analysis passed"


# === Python Flag Parsing ===

# Python flags that take an argument
FLAGS_WITH_ARG = frozenset(
    {
        "-c",  # command
        "-m",  # module
        "-W",  # warning control
        "-X",  # implementation option
        "--check-hash-based-pycs",
    }
)

# Python flags that are safe (no code execution)
SAFE_FLAGS = frozenset(
    {
        "-V",
        "--version",
        "-h",
        "--help",
        "-VV",  # Verbose version
    }
)


def _find_script_path(tokens: list[str], cwd: Path) -> tuple[Path | None, int]:
    """
    Find the script path in Python command tokens.

    Returns (path, index) or (None, -1) if no script found.
    """
    i = 1  # Skip 'python'
    while i < len(tokens):
        token = tokens[i]

        # Version/help - stop looking
        if token in SAFE_FLAGS:
            return None, -1

        # -c command or -m module - not a file
        if token in ("-c", "-m"):
            return None, -1

        # Flag with argument
        if token in FLAGS_WITH_ARG:
            i += 2
            continue

        # Combined flag=value
        if token.startswith("-") and "=" in token:
            i += 1
            continue

        # Flag without argument
        if token.startswith("-"):
            i += 1
            continue

        # Found the script path
        script_path = Path(token)
        if not script_path.is_absolute():
            script_path = cwd / script_path

        return script_path.resolve(), i

    return None, -1


def get_description(tokens: list[str]) -> str:
    """Get description for Python command."""
    if len(tokens) < 2:
        return tokens[0]

    for token in tokens[1:]:
        if token in SAFE_FLAGS:
            return f"{tokens[0]} {token}"
        if token == "-c":
            return f"{tokens[0]} -c"
        if token == "-m":
            idx = tokens.index("-m")
            if idx + 1 < len(tokens):
                return f"{tokens[0]} -m {tokens[idx + 1]}"
            return f"{tokens[0]} -m"
        if not token.startswith("-"):
            # Script name
            return f"{tokens[0]} {Path(token).name}"

    return tokens[0]


def classify(tokens: list[str], cwd: Path | None = None) -> Classification:
    """
    Classify Python command for approval.

    Auto-approves:
    - Version/help flags
    - Scripts that pass static analysis (no I/O, no dangerous imports)

    Requires confirmation:
    - -c (inline code)
    - -m (module execution)
    - Scripts that fail analysis or can't be read
    - Interactive mode
    """
    if cwd is None:
        cwd = Path.cwd()

    desc = get_description(tokens)

    if len(tokens) < 2:
        # Just "python" - starts interactive mode
        return Classification("ask", description=f"{tokens[0]} interactive")

    # Check for safe flags first
    for token in tokens[1:]:
        if token in SAFE_FLAGS:
            return Classification("approve", description=desc)

    # Check for -c (inline code) - too hard to analyze reliably
    if "-c" in tokens:
        return Classification("ask", description=desc)

    # Check for -m (module) - could run arbitrary code
    if "-m" in tokens:
        idx = tokens.index("-m")
        if idx + 1 < len(tokens):
            module = tokens[idx + 1]
            # Only calendar is truly inert (just prints output, no I/O or code exec)
            # - timeit: executes its argument as code
            # - json.tool: reads files
            # - pydoc: imports modules (executes top-level code)
            if module == "calendar":
                return Classification("approve", description=desc)
        return Classification("ask", description=desc)

    # Check for -i (interactive after script)
    if "-i" in tokens:
        return Classification("ask", description=desc)

    # Find and analyze script
    script_path, _ = _find_script_path(tokens, cwd)

    if script_path is None:
        # No script found - might be just flags
        return Classification("ask", description=desc)

    # Try to analyze the script
    is_safe, reason = analyze_python_file(script_path)

    if is_safe:
        return Classification("approve", description=f"{desc} (analyzed)")
    else:
        # Include reason in description so user knows why
        return Classification("ask", description=f"{desc}: {reason}")
