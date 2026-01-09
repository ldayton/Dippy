set shell := ["bash", "-cu"]

_test-py version:
    uv run --python {{version}} pytest

# Run tests on Python 3.11
test-py311: (_test-py "3.11")
# Run tests on Python 3.12
test-py312: (_test-py "3.12")
# Run tests on Python 3.13
test-py313: (_test-py "3.13")
# Run tests on Python 3.14
test-py314: (_test-py "3.14")

# Run tests (default: 3.14)
alias test := test-py314

# Run tests on all supported Python versions
test-all: test-py311 test-py312 test-py313 test-py314

# Format and lint
fmt:
    uv run ruff check --fix && uv run ruff format
