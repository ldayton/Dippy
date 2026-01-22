"""
Comprehensive tests for openssl CLI handler.

OpenSSL has viewing commands (safe) and crypto operations (need confirmation).
"""

from __future__ import annotations

import pytest

from conftest import is_approved, needs_confirmation


TESTS = [
    # === SAFE: Version/help/list ===
    ("openssl version", True),
    ("openssl version -a", True),
    ("openssl help", True),
    ("openssl list", True),
    ("openssl list -commands", True),
    ("openssl list -digest-commands", True),
    ("openssl list -cipher-commands", True),
    #
    # === SAFE: Viewing certificates with -noout ===
    ("openssl x509 -noout -text -in cert.pem", True),
    ("openssl x509 -in cert.pem -noout -text", True),
    ("openssl x509 -noout -subject -in cert.pem", True),
    ("openssl x509 -noout -issuer -in cert.pem", True),
    ("openssl x509 -noout -dates -in cert.pem", True),
    ("openssl x509 -noout -startdate -in cert.pem", True),
    ("openssl x509 -noout -enddate -in cert.pem", True),
    ("openssl x509 -noout -serial -in cert.pem", True),
    ("openssl x509 -noout -fingerprint -in cert.pem", True),
    ("openssl x509 -noout -fingerprint -sha256 -in cert.pem", True),
    ("openssl x509 -noout -pubkey -in cert.pem", True),
    ("openssl x509 -noout -modulus -in cert.pem", True),
    ("openssl x509 -noout -purpose -in cert.pem", True),
    #
    # === SAFE: Connection testing ===
    ("openssl s_client -connect example.com:443", True),
    ("openssl s_client -connect example.com:443 -servername example.com", True),
    ("openssl s_client -connect example.com:443 -showcerts", True),
    ("openssl s_client -connect example.com:443 -verify 5", True),
    ("openssl s_client -starttls smtp -connect mail.example.com:587", True),
    #
    # === UNSAFE: Certificate operations (without -noout) ===
    ("openssl x509 -in cert.pem -text", False),  # outputs cert data
    ("openssl x509 -in cert.pem -out cert.der -outform DER", False),
    ("openssl x509 -req -in csr.pem -signkey key.pem -out cert.pem", False),
    #
    # === UNSAFE: Key generation ===
    ("openssl genrsa -out key.pem 2048", False),
    ("openssl genrsa 4096", False),
    ("openssl genpkey -algorithm RSA -out key.pem", False),
    ("openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256", False),
    ("openssl ecparam -genkey -name prime256v1 -out key.pem", False),
    #
    # === UNSAFE: CSR operations ===
    ("openssl req -new -key key.pem -out csr.pem", False),
    ("openssl req -new -newkey rsa:2048 -keyout key.pem -out csr.pem", False),
    ("openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem", False),
    #
    # === UNSAFE: Encryption/decryption ===
    ("openssl enc -aes-256-cbc -in file.txt -out file.enc", False),
    ("openssl enc -d -aes-256-cbc -in file.enc -out file.txt", False),
    ("openssl aes-256-cbc -in file.txt -out file.enc", False),
    #
    # === UNSAFE: Signing/verification ===
    ("openssl dgst -sha256 -sign key.pem -out sig.bin file.txt", False),
    ("openssl dgst -sha256 -verify pubkey.pem -signature sig.bin file.txt", False),
    #
    # === UNSAFE: Key/cert conversion ===
    ("openssl pkcs12 -export -out cert.p12 -inkey key.pem -in cert.pem", False),
    ("openssl pkcs12 -in cert.p12 -out cert.pem", False),
    ("openssl rsa -in key.pem -out key-nopass.pem", False),
    ("openssl ec -in key.pem -out key-nopass.pem", False),
    ("openssl pkcs8 -topk8 -in key.pem -out key.p8", False),
    #
    # === UNSAFE: Random/hash generation ===
    ("openssl rand -hex 32", False),
    ("openssl rand -base64 32", False),
    ("openssl rand -out random.bin 256", False),
    ("openssl dgst -sha256 file.txt", False),
    ("openssl sha256 file.txt", False),
    ("openssl md5 file.txt", False),
    #
    # === UNSAFE: CA operations ===
    ("openssl ca -in csr.pem -out cert.pem", False),
    ("openssl crl -in crl.pem -text", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool) -> None:
    """Test that command safety is detected correctly."""
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approved for: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirmation for: {command}"
