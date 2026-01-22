"""
Comprehensive tests for Cargo (Rust) CLI handler.

Tests cover cargo commands for Rust package management.
"""

from __future__ import annotations

import pytest

from conftest import is_approved, needs_confirmation


TESTS = [
    #
    # === HELP / VERSION ===
    #
    ("cargo help", True),
    ("cargo --help", True),
    ("cargo -h", True),
    ("cargo help build", True),
    ("cargo build --help", True),
    ("cargo version", True),
    ("cargo --version", True),
    ("cargo -V", True),
    #
    # === INFO / SEARCH / METADATA (safe read-only) ===
    #
    ("cargo search serde", True),
    ("cargo search --limit 20 tokio", True),
    ("cargo info serde", True),
    ("cargo info tokio --verbose", True),
    ("cargo tree", True),
    ("cargo tree --invert serde", True),
    ("cargo tree --depth 2", True),
    ("cargo tree --duplicates", True),
    ("cargo tree --features all", True),
    ("cargo metadata", True),
    ("cargo metadata --format-version 1", True),
    ("cargo metadata --no-deps", True),
    ("cargo read-manifest", True),
    ("cargo locate-project", True),
    ("cargo locate-project --message-format plain", True),
    ("cargo pkgid", True),
    ("cargo pkgid serde", True),
    ("cargo verify-project", True),
    #
    # === CHECK / CLIPPY / FMT / DOC (safe - no artifacts, linting only) ===
    #
    ("cargo check", True),
    ("cargo c", True),
    ("cargo check --all-targets", True),
    ("cargo check --release", True),
    ("cargo check --workspace", True),
    ("cargo check -p mypackage", True),
    ("cargo check --features feature1", True),
    ("cargo check --all-features", True),
    ("cargo clippy", True),
    ("cargo clippy --all-targets", True),
    ("cargo clippy -- -D warnings", True),
    ("cargo clippy --fix", True),  # clippy --fix is safe, only modifies source
    ("cargo fmt", True),
    ("cargo fmt --check", True),
    ("cargo fmt --all", True),
    ("cargo fmt -- --check", True),
    ("cargo doc", True),
    ("cargo doc --open", True),
    ("cargo doc --no-deps", True),
    ("cargo doc --document-private-items", True),
    #
    # === FETCH / UPDATE / VENDOR / GENERATE-LOCKFILE (safe - dependency management) ===
    #
    ("cargo fetch", True),
    ("cargo fetch --locked", True),
    ("cargo update", True),
    ("cargo update -p serde", True),
    ("cargo update --dry-run", True),
    ("cargo update --precise 1.0.0 serde", True),
    ("cargo generate-lockfile", True),
    ("cargo vendor", True),
    ("cargo vendor vendor/", True),
    ("cargo vendor --versioned-dirs", True),
    #
    # === LOGIN / LOGOUT / OWNER (registry auth - safe read-only operations) ===
    #
    ("cargo login", True),
    ("cargo login --registry crates-io", True),
    ("cargo logout", True),
    ("cargo owner", True),
    ("cargo owner --list", True),
    #
    # === BUILD (unsafe - creates artifacts) ===
    #
    ("cargo build", False),
    ("cargo b", False),
    ("cargo build --release", False),
    ("cargo build --target x86_64-unknown-linux-gnu", False),
    ("cargo build --all-targets", False),
    ("cargo build --workspace", False),
    ("cargo build -p mypackage", False),
    ("cargo build --features feature1", False),
    ("cargo build --all-features", False),
    ("cargo build --jobs 4", False),
    ("cargo build -j 4", False),
    ("cargo build --verbose", False),
    ("cargo build -v", False),
    #
    # === RUN (unsafe - executes code) ===
    #
    ("cargo run", False),
    ("cargo r", False),
    ("cargo run --release", False),
    ("cargo run --bin mybin", False),
    ("cargo run --example myexample", False),
    ("cargo run -- arg1 arg2", False),
    ("cargo run -p mypackage", False),
    ("cargo run --features feature1", False),
    #
    # === TEST (unsafe - executes tests) ===
    #
    ("cargo test", False),
    ("cargo t", False),
    ("cargo test --release", False),
    ("cargo test --all-targets", False),
    ("cargo test --workspace", False),
    ("cargo test -p mypackage", False),
    ("cargo test testname", False),
    ("cargo test -- --nocapture", False),
    ("cargo test -- --test-threads=1", False),
    ("cargo test --doc", False),
    #
    # === BENCH (unsafe - executes benchmarks) ===
    #
    ("cargo bench", False),
    ("cargo bench --all-targets", False),
    ("cargo bench benchname", False),
    ("cargo bench -- --save-baseline new", False),
    #
    # === INSTALL / UNINSTALL (unsafe - modifies system) ===
    #
    ("cargo install ripgrep", False),
    ("cargo install --path .", False),
    ("cargo install --git https://github.com/user/repo", False),
    ("cargo install --version 1.0.0 serde", False),
    ("cargo install --force serde", False),
    ("cargo install --locked ripgrep", False),
    ("cargo install --list", False),  # list is actually safe but handled uniformly
    ("cargo uninstall ripgrep", False),
    #
    # === PUBLISH / YANK (unsafe - modifies registry) ===
    #
    ("cargo publish", False),
    ("cargo publish --dry-run", False),
    ("cargo publish --allow-dirty", False),
    ("cargo publish --registry crates-io", False),
    ("cargo yank --version 1.0.0", False),
    ("cargo yank --undo --version 1.0.0", False),
    #
    # === CLEAN (unsafe - deletes files) ===
    #
    ("cargo clean", False),
    ("cargo clean --release", False),
    ("cargo clean -p mypackage", False),
    ("cargo clean --doc", False),
    #
    # === NEW / INIT (unsafe - creates files) ===
    #
    ("cargo new myproject", False),
    ("cargo new --lib mylib", False),
    ("cargo new --bin mybin", False),
    ("cargo new --vcs git myproject", False),
    ("cargo init", False),
    ("cargo init --lib", False),
    ("cargo init --bin", False),
    ("cargo init myproject", False),
    #
    # === ADD / REMOVE (unsafe - modifies Cargo.toml) ===
    #
    ("cargo add serde", False),
    ("cargo add serde --features derive", False),
    ("cargo add serde --dev", False),
    ("cargo add serde --build", False),
    ("cargo add serde --optional", False),
    ("cargo add --git https://github.com/serde-rs/serde", False),
    ("cargo add --path ../mylib", False),
    ("cargo remove serde", False),
    ("cargo rm serde", False),
    ("cargo remove serde --dev", False),
    #
    # === FIX (unsafe - modifies source code) ===
    #
    ("cargo fix", False),
    ("cargo fix --edition", False),
    ("cargo fix --edition-idioms", False),
    ("cargo fix --allow-dirty", False),
    ("cargo fix --allow-staged", False),
    #
    # === EDGE CASES ===
    #
    ("cargo", False),  # No subcommand
    ("cargo unknown-command", False),
    ("cargo +nightly build", False),  # Toolchain override
    ("cargo +stable test", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool) -> None:
    """Test that command safety is detected correctly."""
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approved for: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirmation for: {command}"
