"""
Comprehensive tests for prometheus CLI handler.

Prometheus is a monitoring server and time-series database. Only help and version
flags are safe (informational only). Running the server itself is unsafe as it
starts a service, binds ports, creates lockfiles, and writes data to storage.
"""

from __future__ import annotations

import pytest

from conftest import is_approved, needs_confirmation


TESTS = [
    # === SAFE: Help and version flags ===
    ("prometheus --help", True),
    ("prometheus -h", True),
    ("prometheus --help-long", True),
    ("prometheus --help-man", True),
    ("prometheus --version", True),
    #
    # === UNSAFE: Running the server (any other usage) ===
    ("prometheus", False),  # No arguments starts server with defaults
    ("prometheus --config.file=prometheus.yml", False),
    ("prometheus --config.file=/etc/prometheus/prometheus.yml", False),
    ("prometheus --web.listen-address=0.0.0.0:9090", False),
    ("prometheus --web.listen-address=:9090", False),
    ("prometheus --storage.tsdb.path=data/", False),
    ("prometheus --storage.tsdb.path=/var/lib/prometheus", False),
    ("prometheus --storage.tsdb.retention.time=15d", False),
    ("prometheus --storage.tsdb.retention.size=512MB", False),
    ("prometheus --log.level=info", False),
    ("prometheus --log.level=debug", False),
    ("prometheus --log.format=json", False),
    ("prometheus --agent", False),  # Agent mode
    ("prometheus --no-agent", False),  # Explicit server mode
    #
    # === UNSAFE: Web configuration ===
    ("prometheus --web.config.file=/etc/prometheus/web.yml", False),
    ("prometheus --web.external-url=http://prometheus.example.com", False),
    ("prometheus --web.route-prefix=/prometheus", False),
    ("prometheus --web.enable-lifecycle", False),
    ("prometheus --web.enable-admin-api", False),
    ("prometheus --web.enable-remote-write-receiver", False),
    ("prometheus --web.enable-otlp-receiver", False),
    ("prometheus --web.console.templates=consoles", False),
    ("prometheus --web.console.libraries=console_libraries", False),
    #
    # === UNSAFE: Storage configuration ===
    ("prometheus --storage.agent.path=data-agent/", False),
    ("prometheus --storage.agent.wal-compression", False),
    ("prometheus --storage.tsdb.no-lockfile", False),
    ("prometheus --storage.remote.flush-deadline=1m", False),
    #
    # === UNSAFE: Query and alerting configuration ===
    ("prometheus --query.timeout=2m", False),
    ("prometheus --query.max-concurrency=20", False),
    ("prometheus --query.max-samples=50000000", False),
    ("prometheus --rules.alert.for-outage-tolerance=1h", False),
    ("prometheus --alertmanager.notification-queue-capacity=10000", False),
    #
    # === UNSAFE: Feature flags and other options ===
    ("prometheus --enable-feature=exemplar-storage", False),
    ("prometheus --enable-feature=memory-snapshot-on-shutdown", False),
    ("prometheus --auto-gomaxprocs", False),
    ("prometheus --auto-gomemlimit", False),
    #
    # === UNSAFE: Combined options ===
    (
        "prometheus --config.file=prometheus.yml --storage.tsdb.path=/data --web.listen-address=:9090",
        False,
    ),
    (
        "prometheus --agent --storage.agent.path=/data --web.listen-address=:9090",
        False,
    ),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool) -> None:
    """Test that command safety is detected correctly."""
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approved for: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirmation for: {command}"
