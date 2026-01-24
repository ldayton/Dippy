"""Test cases for security."""

import pytest
from conftest import is_approved, needs_confirmation

TESTS = [
    # Read operations - safe
    ("security help", True),
    ("security help find-certificate", True),
    ("security show-keychain-info login.keychain", True),
    ("security dump-keychain login.keychain", True),
    ("security find-generic-password -s service", True),
    ("security find-generic-password -a account -s service", True),
    ("security find-internet-password -s server", True),
    ("security find-key -t public", True),
    ("security find-certificate -a", True),
    ("security find-certificate -c CommonName", True),
    ("security find-identity -v", True),
    ("security find-identity -p codesigning", True),
    ("security get-identity-preference -s https://example.com", True),
    ("security dump-trust-settings", True),
    ("security dump-trust-settings -d", True),
    ("security verify-cert -c cert.pem", True),
    ("security error -h", True),
    ("security error 25293", True),
    ("security leaks", True),
    ("security list-smartcards", True),
    ("security translocate-policy-check /path/to/app", True),
    ("security translocate-status-check /path/to/app", True),
    ("security translocate-original-path /path/to/app", True),
    ("security requirement-evaluate anchor apple", True),
    # Write/modify operations - unsafe
    ("security list-keychains", False),  # Can modify with -s
    ("security list-keychains -s keychain.keychain", False),
    ("security default-keychain", False),  # Can modify with -s
    ("security default-keychain -s keychain.keychain", False),
    ("security login-keychain", False),  # Can modify with -s
    ("security create-keychain newkeychain.keychain", False),
    ("security delete-keychain keychain.keychain", False),
    ("security lock-keychain", False),
    ("security unlock-keychain", False),
    ("security set-keychain-settings keychain.keychain", False),
    ("security set-keychain-password keychain.keychain", False),
    ("security create-keypair", False),
    ("security add-generic-password -s service -a account -w pass", False),
    ("security add-internet-password -s server -a account -w pass", False),
    ("security add-certificates cert.pem", False),
    ("security delete-generic-password -s service", False),
    ("security delete-internet-password -s server", False),
    ("security delete-certificate -c CommonName", False),
    ("security delete-identity -c CommonName", False),
    ("security set-identity-preference -s https://example.com -c CN", False),
    ("security export -k keychain.keychain -o output.pem", False),
    ("security import cert.pem", False),
    ("security cms -S -i msg.txt", False),
    ("security add-trusted-cert cert.pem", False),
    ("security remove-trusted-cert cert.pem", False),
    ("security trust-settings-export output.plist", False),
    ("security trust-settings-import settings.plist", False),
    ("security authorize -u", False),
    ("security authorizationdb read system.login.console", False),
    ("security execute-with-privileges /usr/bin/id", False),
    ("security user-trust-settings-enable", False),
    ("security smartcards token -l", False),
    ("security create-filevaultmaster-keychain", False),
    # No arguments - unsafe
    ("security", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool):
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approve: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirm: {command}"
