set shell := ["bash", "-o", "pipefail", "-cu"]
project := "dippy"

_test-py version *ARGS:
    UV_PROJECT_ENVIRONMENT=.venv-{{version}} uv run --python {{version}} pytest {{ARGS}} 2>&1 | sed -u "s/^/[py{{version}}] /" | tee /tmp/{{project}}-test-py{{version}}.log

# Run tests on Python 3.9
test-py39 *ARGS: (_test-py "3.9" ARGS)
# Run tests on Python 3.10
test-py310 *ARGS: (_test-py "3.10" ARGS)
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
[parallel]
test-all: test-py39 test-py310 test-py311 test-py312 test-py313 test-py314

# Verify lock file is up to date
lock-check:
    uv lock --check 2>&1 | sed -u "s/^/[lock] /" | tee /tmp/{{project}}-lock.log

# Run all checks (tests, lint, format, lock) in parallel
[parallel]
check: test-all lint fmt lock-check

# Lint (--fix to apply changes)
lint *ARGS:
    uv run ruff check {{ if ARGS == "--fix" { "--fix" } else { "" } }} 2>&1 | sed -u "s/^/[lint] /" | tee /tmp/{{project}}-lint.log

# Format (--fix to apply changes)
fmt *ARGS:
    uv run ruff format {{ if ARGS == "--fix" { "" } else { "--check" } }} 2>&1 | sed -u "s/^/[fmt] /" | tee /tmp/{{project}}-fmt.log

# Install VS Code syntax highlighting extension
vscode:
    #!/usr/bin/env bash
    cd editors/vscode
    rm -f dippy-syntax-*.vsix
    npx @vscode/vsce package
    code --install-extension dippy-syntax-*.vsix
