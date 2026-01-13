"""
Tests for Python command handler.

Tests static analysis of Python scripts to determine if they're safe.
"""

import pytest

from conftest import is_approved, needs_confirmation


class TestPythonBasicFlags:
    """Tests for basic Python flags that don't run code."""

    @pytest.mark.parametrize(
        "cmd",
        [
            "python --version",
            "python -V",
            "python -VV",
            "python --help",
            "python -h",
            "python3 --version",
            "python3 -V",
            "python3.11 --version",
            "python3.12 --version",
        ],
    )
    def test_version_help_approved(self, check, cmd):
        """Version and help flags should be approved."""
        result = check(cmd)
        assert is_approved(result), f"Expected approve: {cmd}"


class TestPythonCodeExecution:
    """Tests for Python code execution modes."""

    @pytest.mark.parametrize(
        "cmd",
        [
            "python -c 'print(1)'",
            "python3 -c 'import os; os.system(\"ls\")'",
            "python -c 'x=1'",
            "python -m http.server",
            "python -m pip install foo",
            "python -m pytest",
            "python -m venv .venv",
            "python",  # Interactive mode
            "python -i script.py",  # Interactive after script
        ],
    )
    def test_code_execution_needs_confirmation(self, check, cmd):
        """Code execution modes should need confirmation."""
        result = check(cmd)
        assert needs_confirmation(result), f"Expected confirm: {cmd}"

    @pytest.mark.parametrize(
        "cmd",
        [
            "python -m json.tool",
            "python -m calendar",
            "python -m pydoc",
        ],
    )
    def test_safe_modules_approved(self, check, cmd):
        """Safe stdlib modules should be approved."""
        result = check(cmd)
        assert is_approved(result), f"Expected approve: {cmd}"


class TestPythonScriptAnalysis:
    """Tests for Python script static analysis."""

    def test_safe_script_approved(self, check, tmp_path):
        """Script with only safe operations should be approved."""
        script = tmp_path / "safe.py"
        script.write_text("""
import json
import re
from collections import defaultdict

data = {'key': 'value'}
text = json.dumps(data)
pattern = re.compile(r'\\d+')
result = [x * 2 for x in range(10)]
print(result)
""")
        result = check(f"python {script}")
        assert is_approved(result), "Safe script should be approved"

    def test_safe_script_math_approved(self, check, tmp_path):
        """Math-only script should be approved."""
        script = tmp_path / "math_script.py"
        script.write_text("""
import math
import statistics
from decimal import Decimal

values = [1, 2, 3, 4, 5]
mean = statistics.mean(values)
stddev = statistics.stdev(values)
result = math.sqrt(sum(x**2 for x in values))
pi_approx = Decimal('3.14159')
print(f"Result: {result}")
""")
        result = check(f"python {script}")
        assert is_approved(result), "Math script should be approved"

    def test_safe_script_dataclasses_approved(self, check, tmp_path):
        """Script using dataclasses should be approved."""
        script = tmp_path / "dataclass_script.py"
        script.write_text("""
from dataclasses import dataclass, field
from typing import List
import json

@dataclass
class Person:
    name: str
    age: int
    tags: List[str] = field(default_factory=list)

p = Person("Alice", 30, ["dev", "py"])
print(json.dumps({"name": p.name, "age": p.age}))
""")
        result = check(f"python {script}")
        assert is_approved(result), "Dataclass script should be approved"

    def test_dangerous_import_os_blocked(self, check, tmp_path):
        """Script importing os should be blocked."""
        script = tmp_path / "dangerous_os.py"
        script.write_text("""
import os
print(os.getcwd())
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "os import should be blocked"

    def test_dangerous_import_subprocess_blocked(self, check, tmp_path):
        """Script importing subprocess should be blocked."""
        script = tmp_path / "dangerous_subprocess.py"
        script.write_text("""
import subprocess
subprocess.run(["ls"])
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "subprocess import should be blocked"

    def test_dangerous_import_pathlib_blocked(self, check, tmp_path):
        """Script importing pathlib should be blocked (can write files)."""
        script = tmp_path / "dangerous_pathlib.py"
        script.write_text("""
from pathlib import Path
p = Path("test.txt")
p.write_text("hello")
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "pathlib import should be blocked"

    def test_dangerous_import_socket_blocked(self, check, tmp_path):
        """Script importing socket should be blocked."""
        script = tmp_path / "dangerous_socket.py"
        script.write_text("""
import socket
s = socket.socket()
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "socket import should be blocked"

    def test_dangerous_import_requests_blocked(self, check, tmp_path):
        """Script importing requests should be blocked."""
        script = tmp_path / "dangerous_requests.py"
        script.write_text("""
import requests
r = requests.get("http://example.com")
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "requests import should be blocked"

    def test_dangerous_builtin_eval_blocked(self, check, tmp_path):
        """Script using eval should be blocked."""
        script = tmp_path / "dangerous_eval.py"
        script.write_text("""
code = "1 + 1"
result = eval(code)
print(result)
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "eval should be blocked"

    def test_dangerous_builtin_exec_blocked(self, check, tmp_path):
        """Script using exec should be blocked."""
        script = tmp_path / "dangerous_exec.py"
        script.write_text("""
code = "x = 1"
exec(code)
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "exec should be blocked"

    def test_dangerous_builtin_open_blocked(self, check, tmp_path):
        """Script using open should be blocked."""
        script = tmp_path / "dangerous_open.py"
        script.write_text("""
with open("file.txt", "w") as f:
    f.write("data")
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "open should be blocked"

    def test_dangerous_import_dunder_blocked(self, check, tmp_path):
        """Script using __import__ should be blocked."""
        script = tmp_path / "dangerous_dunder_import.py"
        script.write_text("""
os = __import__("os")
print(os.getcwd())
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "__import__ should be blocked"

    def test_dangerous_reflection_blocked(self, check, tmp_path):
        """Script using dangerous reflection should be blocked."""
        script = tmp_path / "dangerous_reflection.py"
        script.write_text("""
class Foo:
    pass

# Trying to access dangerous attributes
print(Foo.__subclasses__())
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "reflection should be blocked"

    def test_dangerous_async_blocked(self, check, tmp_path):
        """Script using async should be blocked (requires asyncio)."""
        script = tmp_path / "dangerous_async.py"
        script.write_text("""
async def fetch():
    return "data"

import asyncio
asyncio.run(fetch())
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "async should be blocked"

    def test_nonexistent_file_blocked(self, check, tmp_path):
        """Non-existent script should be blocked."""
        result = check(f"python {tmp_path}/nonexistent.py")
        assert needs_confirmation(result), "nonexistent file should be blocked"

    def test_syntax_error_blocked(self, check, tmp_path):
        """Script with syntax error should be blocked."""
        script = tmp_path / "syntax_error.py"
        script.write_text("""
def foo(
    # Missing closing paren
print("hello")
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "syntax error should be blocked"


class TestPythonComplexScripts:
    """Tests for more complex Python scripts."""

    def test_json_processing_approved(self, check, tmp_path):
        """JSON processing script should be approved."""
        script = tmp_path / "json_process.py"
        script.write_text("""
import json
from collections import Counter

# Simulate processing (in real use, data would come from stdin or arg)
data = '[{"name": "a"}, {"name": "b"}, {"name": "a"}]'
items = json.loads(data)
counts = Counter(item["name"] for item in items)
print(json.dumps(dict(counts)))
""")
        result = check(f"python {script}")
        assert is_approved(result)

    def test_text_processing_approved(self, check, tmp_path):
        """Text processing script should be approved."""
        script = tmp_path / "text_process.py"
        script.write_text("""
import re
import textwrap
from difflib import SequenceMatcher

text1 = "hello world"
text2 = "hello there"

ratio = SequenceMatcher(None, text1, text2).ratio()
words = re.findall(r'\\w+', text1)
wrapped = textwrap.fill("A very long string " * 10, width=40)
print(f"Similarity: {ratio:.2f}")
print(f"Words: {words}")
""")
        result = check(f"python {script}")
        assert is_approved(result)

    def test_algorithm_script_approved(self, check, tmp_path):
        """Algorithm/computation script should be approved."""
        script = tmp_path / "algorithm.py"
        script.write_text("""
import heapq
import bisect
from itertools import permutations, combinations
from functools import reduce

# Heap operations
heap = [3, 1, 4, 1, 5]
heapq.heapify(heap)
smallest = heapq.heappop(heap)

# Binary search
sorted_list = [1, 2, 3, 4, 5]
idx = bisect.bisect_left(sorted_list, 3)

# Combinatorics
perms = list(permutations([1, 2, 3], 2))
combs = list(combinations([1, 2, 3], 2))

# Reduce
product = reduce(lambda x, y: x * y, [1, 2, 3, 4])

print(f"Smallest: {smallest}, Index: {idx}, Product: {product}")
""")
        result = check(f"python {script}")
        assert is_approved(result)

    def test_hashing_encoding_approved(self, check, tmp_path):
        """Hashing and encoding script should be approved."""
        script = tmp_path / "hash_encode.py"
        script.write_text("""
import hashlib
import hmac
import base64
import binascii

data = b"hello world"

# Hashing
sha256 = hashlib.sha256(data).hexdigest()
md5 = hashlib.md5(data).hexdigest()

# HMAC
mac = hmac.new(b"secret", data, hashlib.sha256).hexdigest()

# Encoding
b64 = base64.b64encode(data).decode()
hex_str = binascii.hexlify(data).decode()

print(f"SHA256: {sha256}")
print(f"Base64: {b64}")
""")
        result = check(f"python {script}")
        assert is_approved(result)


class TestPythonEdgeCases:
    """Edge cases and special scenarios."""

    def test_empty_script_approved(self, check, tmp_path):
        """Empty script should be approved."""
        script = tmp_path / "empty.py"
        script.write_text("")
        result = check(f"python {script}")
        assert is_approved(result)

    def test_comment_only_script_approved(self, check, tmp_path):
        """Script with only comments should be approved."""
        script = tmp_path / "comments.py"
        script.write_text("""
# This is a comment
# Another comment
\"\"\"
A docstring that does nothing
\"\"\"
""")
        result = check(f"python {script}")
        assert is_approved(result)

    def test_print_allowed_by_default(self, check, tmp_path):
        """Print should be allowed by default."""
        script = tmp_path / "print_test.py"
        script.write_text("""
print("Hello, World!")
print(1, 2, 3, sep=", ")
""")
        result = check(f"python {script}")
        assert is_approved(result)

    def test_class_definition_approved(self, check, tmp_path):
        """Class definitions should be approved."""
        script = tmp_path / "class_def.py"
        script.write_text("""
from abc import ABC, abstractmethod

class Base(ABC):
    @abstractmethod
    def method(self):
        pass

class Derived(Base):
    def method(self):
        return 42

obj = Derived()
print(obj.method())
""")
        result = check(f"python {script}")
        assert is_approved(result)

    def test_comprehensions_approved(self, check, tmp_path):
        """Comprehensions should be approved."""
        script = tmp_path / "comprehensions.py"
        script.write_text("""
# List comprehension
squares = [x**2 for x in range(10)]

# Dict comprehension
square_map = {x: x**2 for x in range(10)}

# Set comprehension
unique_squares = {x**2 for x in range(-5, 6)}

# Generator expression
sum_squares = sum(x**2 for x in range(10))

print(squares, square_map, unique_squares, sum_squares)
""")
        result = check(f"python {script}")
        assert is_approved(result)

    def test_large_file_blocked(self, check, tmp_path):
        """Very large files should be blocked (too expensive to analyze)."""
        script = tmp_path / "large.py"
        # Create a file > 100KB
        script.write_text("x = 1\n" * 20000)
        result = check(f"python {script}")
        assert needs_confirmation(result)

    def test_non_python_extension_blocked(self, check, tmp_path):
        """Non-.py files should be blocked."""
        script = tmp_path / "script.txt"
        script.write_text("print('hello')")
        result = check(f"python {script}")
        assert needs_confirmation(result)

    def test_unknown_import_blocked(self, check, tmp_path):
        """Unknown third-party imports should be blocked."""
        script = tmp_path / "unknown_import.py"
        script.write_text("""
import pandas as pd
import numpy as np
df = pd.DataFrame()
""")
        result = check(f"python {script}")
        assert needs_confirmation(result)


class TestPythonWithFlags:
    """Tests for Python with various flags."""

    def test_script_with_unbuffered_flag(self, check, tmp_path):
        """Script with -u flag should still be analyzed."""
        script = tmp_path / "safe.py"
        script.write_text("print('hello')")
        result = check(f"python -u {script}")
        assert is_approved(result)

    def test_script_with_optimize_flag(self, check, tmp_path):
        """Script with -O flag should still be analyzed."""
        script = tmp_path / "safe.py"
        script.write_text("print('hello')")
        result = check(f"python -O {script}")
        assert is_approved(result)

    def test_script_with_multiple_flags(self, check, tmp_path):
        """Script with multiple flags should still be analyzed."""
        script = tmp_path / "safe.py"
        script.write_text("import json\nprint(json.dumps({}))")
        result = check(f"python -u -B -O {script}")
        assert is_approved(result)

    def test_script_with_warning_flag(self, check, tmp_path):
        """Script with -W flag should still be analyzed."""
        script = tmp_path / "safe.py"
        script.write_text("print('hello')")
        result = check(f"python -W ignore {script}")
        assert is_approved(result)


class TestPythonUnitAnalysis:
    """Unit tests for the analysis functions directly."""

    def test_analyze_safe_source(self):
        """Test analyze_python_source with safe code."""
        from dippy.cli.python import analyze_python_source

        source = """
import json
data = json.loads('{}')
print(data)
"""
        violations = analyze_python_source(source)
        assert len(violations) == 0

    def test_analyze_dangerous_source(self):
        """Test analyze_python_source with dangerous code."""
        from dippy.cli.python import analyze_python_source

        source = """
import os
os.system('ls')
"""
        violations = analyze_python_source(source)
        assert len(violations) > 0
        assert any(v.kind == "import" for v in violations)

    def test_analyze_eval_source(self):
        """Test analyze_python_source detects eval."""
        from dippy.cli.python import analyze_python_source

        source = """
x = eval("1 + 1")
"""
        violations = analyze_python_source(source)
        assert len(violations) > 0
        assert any(v.kind == "builtin" and "eval" in v.detail for v in violations)


class TestPythonSecurityBypasses:
    """Tests for known bypass attempts that MUST be blocked."""

    def test_codecs_open_blocked(self, check, tmp_path):
        """codecs.open() can read/write files - must be blocked."""
        script = tmp_path / "codecs_bypass.py"
        script.write_text("""
import codecs
with codecs.open("file.txt", "w", "utf-8") as f:
    f.write("pwned")
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "codecs.open bypass should be blocked"

    def test_gzip_open_blocked(self, check, tmp_path):
        """gzip.open() can read/write files - must be blocked."""
        script = tmp_path / "gzip_bypass.py"
        script.write_text("""
import gzip
with gzip.open("file.gz", "wb") as f:
    f.write(b"pwned")
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "gzip.open bypass should be blocked"

    def test_bz2_open_blocked(self, check, tmp_path):
        """bz2.open() can read/write files - must be blocked."""
        script = tmp_path / "bz2_bypass.py"
        script.write_text("""
import bz2
with bz2.open("file.bz2", "wb") as f:
    f.write(b"pwned")
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "bz2.open bypass should be blocked"

    def test_lzma_open_blocked(self, check, tmp_path):
        """lzma.open() can read/write files - must be blocked."""
        script = tmp_path / "lzma_bypass.py"
        script.write_text("""
import lzma
with lzma.open("file.xz", "wb") as f:
    f.write(b"pwned")
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "lzma.open bypass should be blocked"

    def test_inspect_getsource_blocked(self, check, tmp_path):
        """inspect.getsource() reads files - must be blocked."""
        script = tmp_path / "inspect_bypass.py"
        script.write_text("""
import inspect
import json
source = inspect.getsource(json)
print(source)
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "inspect.getsource bypass should be blocked"

    def test_linecache_blocked(self, check, tmp_path):
        """linecache reads files - must be blocked."""
        script = tmp_path / "linecache_bypass.py"
        script.write_text("""
import linecache
line = linecache.getline("/etc/passwd", 1)
print(line)
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "linecache bypass should be blocked"

    def test_dunder_import_in_comprehension_blocked(self, check, tmp_path):
        """__import__ in comprehension must be blocked."""
        script = tmp_path / "comprehension_bypass.py"
        script.write_text("""
modules = [__import__('os') for _ in [1]]
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), (
            "__import__ in comprehension should be blocked"
        )

    def test_getattr_builtins_blocked(self, check, tmp_path):
        """getattr on __builtins__ must be blocked."""
        script = tmp_path / "getattr_bypass.py"
        script.write_text("""
open_func = getattr(__builtins__, 'open')
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "getattr(__builtins__) should be blocked"

    def test_class_subclasses_blocked(self, check, tmp_path):
        """__subclasses__ access must be blocked."""
        script = tmp_path / "subclasses_bypass.py"
        script.write_text("""
subclasses = ().__class__.__bases__[0].__subclasses__()
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "__subclasses__ bypass should be blocked"

    def test_globals_blocked(self, check, tmp_path):
        """globals() must be blocked."""
        script = tmp_path / "globals_bypass.py"
        script.write_text("""
g = globals()
builtins = g['__builtins__']
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "globals() should be blocked"

    def test_zlib_safe_without_file_io(self, check, tmp_path):
        """zlib compress/decompress (no file I/O) should be safe."""
        script = tmp_path / "zlib_safe.py"
        script.write_text("""
import zlib
data = b"hello world"
compressed = zlib.compress(data)
decompressed = zlib.decompress(compressed)
print(decompressed)
""")
        result = check(f"python {script}")
        assert is_approved(result), "zlib compress/decompress should be safe"


class TestDangerousModulesBandit:
    """Tests for dangerous modules from Bandit blacklists."""

    def test_marshal_blocked(self, check, tmp_path):
        """marshal module can deserialize arbitrary code - must be blocked."""
        script = tmp_path / "marshal_dangerous.py"
        script.write_text("""
import marshal
data = marshal.dumps(lambda: None)
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "marshal should be blocked"

    def test_dill_blocked(self, check, tmp_path):
        """dill is a pickle variant - must be blocked."""
        script = tmp_path / "dill_dangerous.py"
        script.write_text("""
import dill
obj = dill.dumps(lambda x: x)
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "dill should be blocked"

    def test_jsonpickle_blocked(self, check, tmp_path):
        """jsonpickle can execute code on decode - must be blocked."""
        script = tmp_path / "jsonpickle_dangerous.py"
        script.write_text("""
import jsonpickle
data = jsonpickle.encode({"key": "value"})
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "jsonpickle should be blocked"

    def test_pickle_import_from_blocked(self, check, tmp_path):
        """from pickle import X must be blocked."""
        script = tmp_path / "pickle_from.py"
        script.write_text("""
from pickle import loads, dumps
data = dumps({"key": "value"})
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "from pickle import should be blocked"

    def test_configparser_blocked(self, check, tmp_path):
        """configparser can read files directly - must be blocked."""
        script = tmp_path / "configparser_dangerous.py"
        script.write_text("""
import configparser
config = configparser.ConfigParser()
config.read('config.ini')
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "configparser should be blocked"


class TestDangerousModulesXML:
    """Tests for XML modules (XXE vulnerabilities - Bandit B405-B410)."""

    def test_xml_etree_blocked(self, check, tmp_path):
        """xml.etree.ElementTree is vulnerable to XXE - must be blocked."""
        script = tmp_path / "xml_etree.py"
        script.write_text("""
import xml.etree.ElementTree as ET
tree = ET.parse('data.xml')
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "xml.etree should be blocked"

    def test_xml_etree_from_import_blocked(self, check, tmp_path):
        """from xml.etree import ElementTree must be blocked."""
        script = tmp_path / "xml_etree_from.py"
        script.write_text("""
from xml.etree import ElementTree
root = ElementTree.fromstring('<root/>')
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "from xml.etree should be blocked"

    def test_xml_sax_blocked(self, check, tmp_path):
        """xml.sax is vulnerable to XXE - must be blocked."""
        script = tmp_path / "xml_sax.py"
        script.write_text("""
import xml.sax
parser = xml.sax.make_parser()
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "xml.sax should be blocked"

    def test_xml_dom_minidom_blocked(self, check, tmp_path):
        """xml.dom.minidom is vulnerable to XXE - must be blocked."""
        script = tmp_path / "xml_minidom.py"
        script.write_text("""
from xml.dom import minidom
doc = minidom.parseString('<root/>')
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "xml.dom.minidom should be blocked"

    def test_xml_parsers_expat_blocked(self, check, tmp_path):
        """xml.parsers.expat must be blocked."""
        script = tmp_path / "xml_expat.py"
        script.write_text("""
from xml.parsers import expat
parser = expat.ParserCreate()
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "xml.parsers.expat should be blocked"


class TestDangerousModulesArchive:
    """Tests for archive modules that can extract files."""

    def test_tarfile_blocked(self, check, tmp_path):
        """tarfile can extract files - must be blocked."""
        script = tmp_path / "tarfile_dangerous.py"
        script.write_text("""
import tarfile
with tarfile.open('archive.tar.gz') as tar:
    tar.extractall()
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "tarfile should be blocked"

    def test_zipfile_blocked(self, check, tmp_path):
        """zipfile can extract files - must be blocked."""
        script = tmp_path / "zipfile_dangerous.py"
        script.write_text("""
import zipfile
with zipfile.ZipFile('archive.zip') as zf:
    zf.extractall()
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "zipfile should be blocked"

    def test_tarfile_from_import_blocked(self, check, tmp_path):
        """from tarfile import X must be blocked."""
        script = tmp_path / "tarfile_from.py"
        script.write_text("""
from tarfile import open as tar_open
tar = tar_open('archive.tar')
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "from tarfile should be blocked"


class TestDangerousModulesCGI:
    """Tests for CGI modules (httpoxy vulnerabilities - Bandit B412)."""

    def test_cgi_blocked(self, check, tmp_path):
        """cgi module has httpoxy vulnerabilities - must be blocked."""
        script = tmp_path / "cgi_dangerous.py"
        script.write_text("""
import cgi
form = cgi.FieldStorage()
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "cgi should be blocked"

    def test_cgitb_blocked(self, check, tmp_path):
        """cgitb module must be blocked."""
        script = tmp_path / "cgitb_dangerous.py"
        script.write_text("""
import cgitb
cgitb.enable()
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "cgitb should be blocked"

    def test_wsgiref_handlers_blocked(self, check, tmp_path):
        """wsgiref.handlers has httpoxy vulnerabilities - must be blocked."""
        script = tmp_path / "wsgiref_dangerous.py"
        script.write_text("""
from wsgiref.handlers import CGIHandler
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "wsgiref.handlers should be blocked"


class TestDangerousModulesLegacy:
    """Tests for legacy dangerous modules."""

    def test_commands_blocked(self, check, tmp_path):
        """commands module (Python 2 legacy) must be blocked."""
        script = tmp_path / "commands_dangerous.py"
        script.write_text("""
import commands
output = commands.getoutput('ls')
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "commands should be blocked"

    def test_popen2_blocked(self, check, tmp_path):
        """popen2 module (legacy) must be blocked."""
        script = tmp_path / "popen2_dangerous.py"
        script.write_text("""
import popen2
r, w = popen2.popen2('ls')
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "popen2 should be blocked"


class TestDangerousAttributes:
    """Tests for dangerous method/attribute access."""

    def test_subprocess_popen_method_blocked(self, check, tmp_path):
        """subprocess.Popen must be blocked."""
        script = tmp_path / "subprocess_popen.py"
        script.write_text("""
import subprocess
p = subprocess.Popen(['ls'])
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "subprocess.Popen should be blocked"

    def test_subprocess_check_output_blocked(self, check, tmp_path):
        """subprocess.check_output must be blocked."""
        script = tmp_path / "subprocess_check_output.py"
        script.write_text("""
import subprocess
out = subprocess.check_output(['ls'])
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "subprocess.check_output should be blocked"

    def test_subprocess_run_blocked(self, check, tmp_path):
        """subprocess.run must be blocked."""
        script = tmp_path / "subprocess_run.py"
        script.write_text("""
import subprocess
subprocess.run(['ls'])
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "subprocess.run should be blocked"

    def test_os_system_method_blocked(self, check, tmp_path):
        """os.system method must be blocked."""
        script = tmp_path / "os_system.py"
        script.write_text("""
import os
os.system('ls')
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "os.system should be blocked"

    def test_os_popen_method_blocked(self, check, tmp_path):
        """os.popen method must be blocked."""
        script = tmp_path / "os_popen.py"
        script.write_text("""
import os
f = os.popen('ls')
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "os.popen should be blocked"

    def test_os_spawn_methods_blocked(self, check, tmp_path):
        """os.spawn* methods must be blocked."""
        script = tmp_path / "os_spawn.py"
        script.write_text("""
import os
os.spawnl(os.P_WAIT, '/bin/ls', 'ls')
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "os.spawnl should be blocked"

    def test_os_exec_methods_blocked(self, check, tmp_path):
        """os.exec* methods must be blocked."""
        script = tmp_path / "os_exec.py"
        script.write_text("""
import os
os.execv('/bin/ls', ['ls'])
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "os.execv should be blocked"


class TestDangerousReflection:
    """Tests for dangerous reflection/introspection attributes."""

    def test_frame_f_globals_blocked(self, check, tmp_path):
        """Frame f_globals access must be blocked."""
        script = tmp_path / "f_globals.py"
        script.write_text("""
import sys
frame = sys._getframe()
g = frame.f_globals
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "f_globals should be blocked"

    def test_frame_f_locals_blocked(self, check, tmp_path):
        """Frame f_locals access must be blocked."""
        script = tmp_path / "f_locals.py"
        script.write_text("""
import sys
frame = sys._getframe()
l = frame.f_locals
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "f_locals should be blocked"

    def test_frame_f_code_blocked(self, check, tmp_path):
        """Frame f_code access must be blocked."""
        script = tmp_path / "f_code.py"
        script.write_text("""
import sys
frame = sys._getframe()
code = frame.f_code
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "f_code should be blocked"

    def test_traceback_tb_frame_blocked(self, check, tmp_path):
        """Traceback tb_frame access must be blocked."""
        script = tmp_path / "tb_frame.py"
        script.write_text("""
import sys
try:
    1/0
except:
    tb = sys.exc_info()[2]
    frame = tb.tb_frame
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "tb_frame should be blocked"

    def test_generator_gi_frame_blocked(self, check, tmp_path):
        """Generator gi_frame access must be blocked."""
        script = tmp_path / "gi_frame.py"
        script.write_text("""
def gen():
    yield 1
g = gen()
frame = g.gi_frame
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "gi_frame should be blocked"

    def test_code_co_code_blocked(self, check, tmp_path):
        """Code object co_code access must be blocked."""
        script = tmp_path / "co_code.py"
        script.write_text("""
def foo():
    pass
bytecode = foo.__code__.co_code
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "co_code should be blocked"

    def test_func_globals_blocked(self, check, tmp_path):
        """Function __globals__ access must be blocked."""
        script = tmp_path / "func_globals.py"
        script.write_text("""
def foo():
    pass
g = foo.__globals__
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "__globals__ should be blocked"

    def test_func_code_blocked(self, check, tmp_path):
        """Function __code__ access must be blocked."""
        script = tmp_path / "func_code.py"
        script.write_text("""
def foo():
    pass
c = foo.__code__
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "__code__ should be blocked"

    def test_class_mro_blocked(self, check, tmp_path):
        """Class __mro__ access must be blocked."""
        script = tmp_path / "class_mro.py"
        script.write_text("""
class Foo:
    pass
mro = Foo.__mro__
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "__mro__ should be blocked"

    def test_class_bases_blocked(self, check, tmp_path):
        """Class __bases__ access must be blocked."""
        script = tmp_path / "class_bases.py"
        script.write_text("""
class Foo:
    pass
bases = Foo.__bases__
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "__bases__ should be blocked"


class TestDangerousFileOps:
    """Tests for file operation methods."""

    def test_file_write_method_blocked(self, check, tmp_path):
        """File .write() method must be blocked."""
        script = tmp_path / "file_write.py"
        script.write_text("""
f = open('test.txt', 'w')
f.write('data')
f.close()
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "file.write should be blocked"

    def test_file_read_method_blocked(self, check, tmp_path):
        """File .read() method must be blocked."""
        script = tmp_path / "file_read.py"
        script.write_text("""
f = open('test.txt')
data = f.read()
f.close()
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "file.read should be blocked"

    def test_path_write_text_method_blocked(self, check, tmp_path):
        """Path.write_text() method must be blocked."""
        script = tmp_path / "path_write_text.py"
        script.write_text("""
from pathlib import Path
p = Path('test.txt')
p.write_text('hello')
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "Path.write_text should be blocked"

    def test_path_read_text_method_blocked(self, check, tmp_path):
        """Path.read_text() method must be blocked."""
        script = tmp_path / "path_read_text.py"
        script.write_text("""
from pathlib import Path
p = Path('test.txt')
content = p.read_text()
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "Path.read_text should be blocked"

    def test_path_write_bytes_method_blocked(self, check, tmp_path):
        """Path.write_bytes() method must be blocked."""
        script = tmp_path / "path_write_bytes.py"
        script.write_text("""
from pathlib import Path
p = Path('test.bin')
p.write_bytes(b'hello')
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "Path.write_bytes should be blocked"

    def test_path_open_method_blocked(self, check, tmp_path):
        """Path.open() method must be blocked."""
        script = tmp_path / "path_open.py"
        script.write_text("""
from pathlib import Path
p = Path('test.txt')
with p.open('w') as f:
    pass
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "Path.open should be blocked"

    def test_shutil_rmtree_blocked(self, check, tmp_path):
        """shutil.rmtree must be blocked."""
        script = tmp_path / "shutil_rmtree.py"
        script.write_text("""
import shutil
shutil.rmtree('/tmp/test')
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "shutil.rmtree should be blocked"

    def test_os_remove_blocked(self, check, tmp_path):
        """os.remove must be blocked."""
        script = tmp_path / "os_remove.py"
        script.write_text("""
import os
os.remove('test.txt')
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "os.remove should be blocked"

    def test_os_mkdir_blocked(self, check, tmp_path):
        """os.mkdir must be blocked."""
        script = tmp_path / "os_mkdir.py"
        script.write_text("""
import os
os.mkdir('newdir')
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "os.mkdir should be blocked"


class TestNetworkOps:
    """Tests for network operation methods."""

    def test_socket_connect_blocked(self, check, tmp_path):
        """socket.connect must be blocked."""
        script = tmp_path / "socket_connect.py"
        script.write_text("""
import socket
s = socket.socket()
s.connect(('localhost', 80))
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "socket.connect should be blocked"

    def test_urllib_urlopen_blocked(self, check, tmp_path):
        """urllib.request.urlopen must be blocked."""
        script = tmp_path / "urllib_urlopen.py"
        script.write_text("""
from urllib.request import urlopen
r = urlopen('http://example.com')
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "urlopen should be blocked"

    def test_http_client_blocked(self, check, tmp_path):
        """http.client must be blocked."""
        script = tmp_path / "http_client.py"
        script.write_text("""
from http.client import HTTPConnection
conn = HTTPConnection('example.com')
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "http.client should be blocked"

    def test_ftplib_blocked(self, check, tmp_path):
        """ftplib must be blocked (Bandit B402)."""
        script = tmp_path / "ftplib_dangerous.py"
        script.write_text("""
import ftplib
ftp = ftplib.FTP('ftp.example.com')
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "ftplib should be blocked"

    def test_telnetlib_blocked(self, check, tmp_path):
        """telnetlib must be blocked (Bandit B401)."""
        script = tmp_path / "telnetlib_dangerous.py"
        script.write_text("""
import telnetlib
tn = telnetlib.Telnet('example.com')
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "telnetlib should be blocked"

    def test_xmlrpc_blocked(self, check, tmp_path):
        """xmlrpc must be blocked (Bandit B411)."""
        script = tmp_path / "xmlrpc_dangerous.py"
        script.write_text("""
from xmlrpc.client import ServerProxy
proxy = ServerProxy('http://localhost:8000')
""")
        result = check(f"python {script}")
        assert needs_confirmation(result), "xmlrpc should be blocked"


class TestUnitAnalysisExtended:
    """Extended unit tests for analyze_python_source."""

    def test_analyze_xml_import(self):
        """Test detection of xml module import."""
        from dippy.cli.python import analyze_python_source

        source = "import xml.etree.ElementTree"
        violations = analyze_python_source(source)
        assert len(violations) > 0
        assert any("xml" in v.detail for v in violations)

    def test_analyze_marshal_import(self):
        """Test detection of marshal module import."""
        from dippy.cli.python import analyze_python_source

        source = "import marshal"
        violations = analyze_python_source(source)
        assert len(violations) > 0
        assert any("marshal" in v.detail for v in violations)

    def test_analyze_tarfile_import(self):
        """Test detection of tarfile module import."""
        from dippy.cli.python import analyze_python_source

        source = "import tarfile"
        violations = analyze_python_source(source)
        assert len(violations) > 0
        assert any("tarfile" in v.detail for v in violations)

    def test_analyze_dangerous_attr_access(self):
        """Test detection of dangerous attribute access."""
        from dippy.cli.python import analyze_python_source

        source = """
def foo():
    pass
g = foo.__globals__
"""
        violations = analyze_python_source(source)
        assert len(violations) > 0
        assert any("__globals__" in v.detail for v in violations)

    def test_analyze_frame_access(self):
        """Test detection of frame attribute access."""
        from dippy.cli.python import analyze_python_source

        source = """
import sys
f = sys._getframe()
g = f.f_globals
"""
        violations = analyze_python_source(source)
        # Should have at least the sys import violation
        assert len(violations) > 0

    def test_analyze_safe_still_safe(self):
        """Ensure safe code is still detected as safe."""
        from dippy.cli.python import analyze_python_source

        source = """
import json
import math
from collections import Counter

data = json.dumps({"x": math.pi})
counts = Counter([1, 2, 2, 3])
print(data, counts)
"""
        violations = analyze_python_source(source)
        assert len(violations) == 0, f"Expected no violations, got {violations}"
