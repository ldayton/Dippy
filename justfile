set shell := ["bash", "-o", "pipefail", "-cu"]
project := "dippy"

_test-py version *ARGS:
    UV_PROJECT_ENVIRONMENT=.venv-{{version}} uv run --python {{version}} pytest {{ARGS}} 2>&1 | sed -u "s/^/[py{{version}}] /" | tee /tmp/{{project}}-test-py{{version}}.log

# Run tests on Python 3.8
test-py38 *ARGS: (_test-py "3.8" ARGS)
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
test-all: test-py38 test-py39 test-py310 test-py311 test-py312 test-py313 test-py314

# Verify lock file is up to date
lock-check:
    uv lock --check 2>&1 | sed -u "s/^/[lock] /" | tee /tmp/{{project}}-lock.log

# Check for banned Python constructions
check-style:
    python3 tools/check_style.py src 2>&1 | sed -u "s/^/[style] /" | tee /tmp/{{project}}-style.log

# Run all checks (tests, lint, format, lock, style) in parallel
[parallel]
check: test-all lint fmt lock-check check-style

# Lint (--fix to apply changes)
lint *ARGS:
    uv run ruff check {{ if ARGS == "--fix" { "--fix" } else { "" } }} 2>&1 | sed -u "s/^/[lint] /" | tee /tmp/{{project}}-lint.log

# Format (--fix to apply changes)
fmt *ARGS:
    uv run ruff format {{ if ARGS == "--fix" { "" } else { "--check" } }} 2>&1 | sed -u "s/^/[fmt] /" | tee /tmp/{{project}}-fmt.log

# Update vendored parable.py from GitHub
update-parable:
    #!/usr/bin/env bash
    set -euo pipefail
    commit=$(git ls-remote https://github.com/ldayton/Parable.git refs/heads/main | cut -f1)
    curl -sS "https://raw.githubusercontent.com/ldayton/Parable/$commit/src/parable.py" -o src/dippy/vendor/parable.py
    checksum=$(shasum -a 256 src/dippy/vendor/parable.py | cut -d' ' -f1)
    sed "s/^parable-commit = .*/parable-commit = \"$commit\"/" pyproject.toml > pyproject.toml.tmp && mv pyproject.toml.tmp pyproject.toml
    sed "s/^parable-sha256 = .*/parable-sha256 = \"$checksum\"/" pyproject.toml > pyproject.toml.tmp && mv pyproject.toml.tmp pyproject.toml
    echo "Updated parable.py to $commit ($checksum)"

# Verify vendored parable.py matches pyproject.toml checksum
check-parable:
    #!/usr/bin/env bash
    set -euo pipefail
    expected=$(grep '^parable-sha256' pyproject.toml | cut -d'"' -f2)
    actual=$(shasum -a 256 src/dippy/vendor/parable.py | cut -d' ' -f1)
    commit=$(grep '^parable-commit' pyproject.toml | cut -d'"' -f2)
    if [[ "$expected" != "$actual" ]]; then
        echo "parable.py checksum mismatch"
        echo "  expected: $expected"
        echo "  actual:   $actual"
        exit 1
    fi
    latest=$(git ls-remote https://github.com/ldayton/Parable.git refs/heads/main | cut -f1)
    if [[ "$commit" == "$latest" ]]; then
        echo "parable.py @ $commit (latest)"
    else
        echo "parable.py @ $commit (latest: $latest)"
    fi

# Install VS Code syntax highlighting extension
vscode:
    #!/usr/bin/env bash
    cd editors/vscode
    rm -f dippy-syntax-*.vsix
    npx @vscode/vsce package
    code --install-extension dippy-syntax-*.vsix
