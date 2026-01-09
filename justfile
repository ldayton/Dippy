set shell := ["bash", "-cu"]
project := "dippy"

_test-py version *ARGS:
    UV_PROJECT_ENVIRONMENT=.venv-{{version}} uv run --python {{version}} pytest {{ARGS}} 2>&1 | sed -u "s/^/[py{{version}}] /" | tee /tmp/{{project}}-test-py{{version}}.log

# Run tests on Python 3.11
test-py311 *ARGS: (_test-py "3.11" ARGS)
# Run tests on Python 3.12
test-py312 *ARGS: (_test-py "3.12" ARGS)
# Run tests on Python 3.13
test-py313 *ARGS: (_test-py "3.13" ARGS)
# Run tests on Python 3.14
test-py314 *ARGS: (_test-py "3.14" ARGS)

# Run tests (default: 3.14)
test *ARGS: (_test-py "3.14" ARGS)

# Run tests on all supported Python versions (parallel)
test-all:
    just test-py311 & just test-py312 & just test-py313 & just test-py314 & wait

# Run all checks (tests, lint, format) in parallel
check:
    just test-all & just lint & just fmt & wait

# Lint (--fix to apply changes)
lint *ARGS:
    uv run ruff check {{ if ARGS == "--fix" { "--fix" } else { "" } }} 2>&1 | sed -u "s/^/[lint] /" | tee /tmp/{{project}}-lint.log

# Format (--fix to apply changes)
fmt *ARGS:
    uv run ruff format {{ if ARGS == "--fix" { "" } else { "--check" } }} 2>&1 | sed -u "s/^/[fmt] /" | tee /tmp/{{project}}-fmt.log
