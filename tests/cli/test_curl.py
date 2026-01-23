"""Test cases for curl."""

from __future__ import annotations

import pytest

from conftest import is_approved, needs_confirmation
from dippy.core.config import Config, Rule

# ==========================================================================
# Curl
# ==========================================================================
#
# Safe: GET, HEAD, OPTIONS, TRACE are read-only methods.
# Unsafe: POST, PUT, DELETE, PATCH mutate server state.
# Unsafe: Any flag that sends data (-d, -F, --json, -T, etc.)
# Unsafe: FTP commands that modify server (-Q with write commands, --ftp-create-dirs)
# Unsafe: Mail operations (--mail-from, --mail-rcpt)
# Unsafe: Config files (-K, --config) - can contain arbitrary options
#

TESTS = [
    #
    # --- Basic safe operations ---
    #
    ("curl https://example.com", True),
    ("curl http://example.com/api/users", True),
    ("curl ftp://example.com/file.txt", True),
    #
    # --- Safe methods (-X / --request) ---
    #
    ("curl -X GET https://example.com", True),
    ("curl -X HEAD https://example.com", True),
    ("curl -X OPTIONS https://example.com", True),
    ("curl -X TRACE https://example.com", True),
    ("curl --request GET https://example.com", True),
    ("curl --request HEAD https://example.com", True),
    ("curl --request=GET https://example.com", True),
    ("curl --request=HEAD https://example.com", True),
    ("curl --request=OPTIONS https://example.com", True),
    ("curl --request=TRACE https://example.com", True),
    # Case insensitivity for methods
    ("curl -X get https://example.com", True),
    ("curl -X Get https://example.com", True),
    #
    # --- Head request shortcuts ---
    #
    ("curl -I https://example.com", True),
    ("curl --head https://example.com", True),
    #
    # --- Output flags (safe - just control where response goes) ---
    #
    ("curl -o output.txt https://example.com", False),
    ("curl --output output.txt https://example.com", False),
    ("curl -O https://example.com/file.zip", True),
    ("curl --remote-name https://example.com/file.zip", True),
    ("curl -J -O https://example.com/file.zip", True),
    ("curl --remote-header-name https://example.com", True),
    ("curl -D headers.txt https://example.com", True),
    ("curl --dump-header headers.txt https://example.com", True),
    ("curl -c cookies.txt https://example.com", True),
    ("curl --cookie-jar cookies.txt https://example.com", True),
    ("curl --trace trace.txt https://example.com", True),
    ("curl --trace-ascii trace.txt https://example.com", True),
    ("curl --stderr errors.txt https://example.com", True),
    ("curl --libcurl code.c https://example.com", True),
    ("curl --output-dir /tmp https://example.com", True),
    #
    # --- Verbosity/display flags (safe) ---
    #
    ("curl -v https://example.com", True),
    ("curl --verbose https://example.com", True),
    ("curl -s https://example.com", True),
    ("curl --silent https://example.com", True),
    ("curl -S https://example.com", True),
    ("curl --show-error https://example.com", True),
    ("curl -# https://example.com", True),
    ("curl --progress-bar https://example.com", True),
    ("curl --no-progress-meter https://example.com", True),
    ("curl -i https://example.com", True),
    ("curl --include https://example.com", True),
    ("curl -w '%{http_code}' https://example.com", True),
    ("curl --write-out '%{http_code}' https://example.com", True),
    #
    # --- Common safe flag combinations ---
    #
    ("curl -s -o /dev/null -w '%{http_code}' https://example.com", True),
    ("curl -sSL https://example.com", True),
    ("curl -fsSL https://example.com/install.sh", True),
    ("curl -v -I https://example.com", True),
    ("curl --silent --show-error https://example.com", True),
    #
    # --- Redirect handling (safe) ---
    #
    ("curl -L https://example.com", True),
    ("curl --location https://example.com", True),
    ("curl --location-trusted https://example.com", True),
    ("curl --max-redirs 5 https://example.com", True),
    #
    # --- Headers and cookies (reading/sending existing - safe) ---
    #
    ("curl -H 'Accept: application/json' https://example.com", True),
    ("curl --header 'Authorization: Bearer token' https://example.com", True),
    ("curl -b cookies.txt https://example.com", True),
    ("curl --cookie cookies.txt https://example.com", True),
    ("curl -A 'Mozilla/5.0' https://example.com", True),
    ("curl --user-agent 'Mozilla/5.0' https://example.com", True),
    ("curl -e 'https://referrer.com' https://example.com", True),
    ("curl --referer 'https://referrer.com' https://example.com", True),
    #
    # --- Authentication (reading resources with creds - safe) ---
    #
    ("curl -u user:pass https://example.com", True),
    ("curl --user user:pass https://example.com", True),
    ("curl --basic https://example.com", True),
    ("curl --digest https://example.com", True),
    ("curl --negotiate https://example.com", True),
    ("curl --ntlm https://example.com", True),
    ("curl --anyauth https://example.com", True),
    ("curl --oauth2-bearer token https://example.com", True),
    ("curl -n https://example.com", True),
    ("curl --netrc https://example.com", True),
    #
    # --- SSL/TLS flags (safe) ---
    #
    ("curl -k https://example.com", True),
    ("curl --insecure https://example.com", True),
    ("curl --cacert ca.pem https://example.com", True),
    ("curl --capath /certs https://example.com", True),
    ("curl -E client.pem https://example.com", True),
    ("curl --cert client.pem https://example.com", True),
    ("curl --key key.pem https://example.com", True),
    ("curl --tlsv1.2 https://example.com", True),
    ("curl --tlsv1.3 https://example.com", True),
    ("curl -1 https://example.com", True),
    ("curl --ssl https://example.com", True),
    ("curl --ssl-reqd https://example.com", True),
    #
    # --- Proxy flags (safe - just routing) ---
    #
    ("curl -x http://proxy:8080 https://example.com", True),
    ("curl --proxy http://proxy:8080 https://example.com", True),
    ("curl --proxy-user user:pass https://example.com", True),
    ("curl --socks5 localhost:1080 https://example.com", True),
    ("curl --noproxy '*' https://example.com", True),
    #
    # --- Timeout and retry flags (safe) ---
    #
    ("curl --connect-timeout 10 https://example.com", True),
    ("curl -m 30 https://example.com", True),
    ("curl --max-time 30 https://example.com", True),
    ("curl --retry 3 https://example.com", True),
    ("curl --retry-delay 5 https://example.com", True),
    ("curl --retry-max-time 60 https://example.com", True),
    #
    # --- Range and conditional requests (safe) ---
    #
    ("curl -r 0-1023 https://example.com/bigfile", True),
    ("curl --range 0-1023 https://example.com/bigfile", True),
    ("curl -C - https://example.com/bigfile", True),
    ("curl --continue-at - https://example.com/bigfile", True),
    ("curl -z 'Jan 1 2024' https://example.com", True),
    ("curl --time-cond 'Jan 1 2024' https://example.com", True),
    #
    # --- DNS and networking flags (safe) ---
    #
    ("curl --resolve example.com:443:1.2.3.4 https://example.com", True),
    ("curl --connect-to example.com:443:other.com:443 https://example.com", True),
    ("curl --interface eth0 https://example.com", True),
    ("curl -4 https://example.com", True),
    ("curl --ipv4 https://example.com", True),
    ("curl -6 https://example.com", True),
    ("curl --ipv6 https://example.com", True),
    ("curl --dns-servers 8.8.8.8 https://example.com", True),
    ("curl --doh-url https://dns.google/dns-query https://example.com", True),
    #
    # --- HTTP version flags (safe) ---
    #
    ("curl -0 https://example.com", True),
    ("curl --http1.0 https://example.com", True),
    ("curl --http1.1 https://example.com", True),
    ("curl --http2 https://example.com", True),
    ("curl --http3 https://example.com", True),
    #
    # --- Other safe flags ---
    #
    ("curl --compressed https://example.com", True),
    ("curl -N https://example.com", True),
    ("curl --no-buffer https://example.com", True),
    ("curl -g 'https://example.com/{a,b,c}'", True),
    ("curl --globoff 'https://example.com/{a,b,c}'", True),
    ("curl --parallel https://example.com/a https://example.com/b", True),
    ("curl -Z https://example.com/a https://example.com/b", True),
    ("curl -f https://example.com", True),
    ("curl --fail https://example.com", True),
    ("curl --fail-with-body https://example.com", True),
    ("curl --create-dirs -o /tmp/dir/file https://example.com", False),
    ("curl --xattr -O https://example.com/file", True),
    ("curl --etag-save etag.txt https://example.com", True),
    ("curl --etag-compare etag.txt https://example.com", True),
    #
    # --- Help and version (safe) ---
    #
    ("curl --help", True),
    ("curl -h", True),
    ("curl --version", True),
    ("curl -V", True),
    ("curl --manual", True),
    ("curl -M", True),
    #
    # --- Unsafe methods ---
    #
    ("curl -X POST https://example.com", False),
    ("curl -X PUT https://example.com", False),
    ("curl -X DELETE https://example.com", False),
    ("curl -X PATCH https://example.com", False),
    ("curl --request POST https://example.com", False),
    ("curl --request PUT https://example.com", False),
    ("curl --request DELETE https://example.com", False),
    ("curl --request=POST https://example.com", False),
    ("curl --request=PUT https://example.com", False),
    ("curl --request=DELETE https://example.com", False),
    ("curl --request=PATCH https://example.com", False),
    # Case insensitivity for unsafe methods
    ("curl -X post https://example.com", False),
    ("curl -X Post https://example.com", False),
    ("curl -X delete https://example.com", False),
    #
    # --- Data sending flags (imply POST, unsafe) ---
    #
    ("curl -d 'data' https://example.com", False),
    ("curl --data 'data' https://example.com", False),
    ("curl --data='foo=bar' https://example.com", False),
    ("curl --data-ascii 'data' https://example.com", False),
    ("curl --data-binary '@file' https://example.com", False),
    ("curl --data-raw 'data' https://example.com", False),
    ("curl --data-urlencode 'key=value' https://example.com", False),
    ('curl --json \'{"key":"value"}\' https://example.com', False),
    # --url-query is safe - it just adds URL query parameters for GET requests
    ("curl --url-query 'key=value' https://example.com", True),
    #
    # --- Form/multipart data (unsafe) ---
    #
    ("curl -F 'file=@test.txt' https://example.com", False),
    ("curl --form 'file=@test.txt' https://example.com", False),
    ("curl --form-string 'name=value' https://example.com", False),
    #
    # --- Upload flags (unsafe) ---
    #
    ("curl -T file.txt ftp://example.com", False),
    ("curl --upload-file file.txt ftp://example.com", False),
    ("curl -a -T file.txt ftp://example.com", False),
    ("curl --append -T file.txt ftp://example.com", False),
    #
    # --- FTP write operations (unsafe) ---
    #
    ("curl --ftp-create-dirs ftp://example.com/newdir/file.txt", False),
    ("curl -Q 'DELE file.txt' ftp://example.com", False),
    ("curl --quote 'DELE file.txt' ftp://example.com", False),
    ("curl -Q 'MKD newdir' ftp://example.com", False),
    ("curl -Q 'RMD olddir' ftp://example.com", False),
    ("curl -Q 'RNFR old.txt' -Q 'RNTO new.txt' ftp://example.com", False),
    # FTP read-only quote commands (safe) - list, pwd, etc.
    ("curl -Q 'PWD' ftp://example.com", True),
    ("curl -Q 'LIST' ftp://example.com", True),
    ("curl -Q 'NLST' ftp://example.com", True),
    ("curl -Q 'STAT' ftp://example.com", True),
    ("curl -Q 'SIZE file.txt' ftp://example.com", True),
    ("curl -Q 'MDTM file.txt' ftp://example.com", True),
    ("curl -Q 'NOOP' ftp://example.com", True),
    ("curl -Q 'HELP' ftp://example.com", True),
    ("curl -Q 'SYST' ftp://example.com", True),
    ("curl -Q 'TYPE I' ftp://example.com", True),
    ("curl -Q 'PASV' ftp://example.com", True),
    ("curl -Q 'CWD /dir' ftp://example.com", True),
    ("curl -Q 'CDUP' ftp://example.com", True),
    #
    # --- Mail operations (unsafe - sends email) ---
    #
    ("curl --mail-from sender@example.com smtp://mail.example.com", False),
    ("curl --mail-rcpt recipient@example.com smtp://mail.example.com", False),
    (
        "curl --mail-from sender@example.com --mail-rcpt recipient@example.com smtp://mail.example.com",
        False,
    ),
    #
    # --- Config file (unsafe - arbitrary commands) ---
    #
    ("curl -K config.txt", False),
    ("curl --config config.txt", False),
    #
    # --- Combined flags with unsafe options ---
    #
    ("curl -sSL -d 'data' https://example.com", False),
    ("curl -v -X POST https://example.com", False),
    ("curl -H 'Content-Type: application/json' -d '{}' https://example.com", False),
    ("curl -o output.txt -X DELETE https://example.com", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool) -> None:
    """Test that command safety is detected correctly."""
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approved for: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirmation for: {command}"


class TestCurlSafeRedirectTargets:
    """curl -o to safe targets should be auto-approved without config."""

    def test_curl_output_to_dev_stdout(self, check):
        """curl -o /dev/stdout should be approved without config."""
        result = check("curl -o /dev/stdout https://example.com")
        assert is_approved(result)


class TestCurlWithRedirectRules:
    """curl -o should respect redirect rules for the output file."""

    def test_curl_output_denied_by_rule(self, check, tmp_path):
        """curl -o to denied path should be denied."""
        cfg = Config(redirect_rules=[Rule("deny", "/etc/*")])
        result = check(
            "curl -o /etc/config https://example.com", config=cfg, cwd=tmp_path
        )
        output = result.get("hookSpecificOutput", {})
        assert output.get("permissionDecision") == "deny"

    def test_curl_output_long_flag_denied(self, check, tmp_path):
        """curl --output to denied path should be denied."""
        cfg = Config(redirect_rules=[Rule("deny", "/etc/*")])
        result = check(
            "curl --output /etc/passwd https://example.com", config=cfg, cwd=tmp_path
        )
        output = result.get("hookSpecificOutput", {})
        assert output.get("permissionDecision") == "deny"

    def test_curl_output_equals_denied(self, check, tmp_path):
        """curl --output=file to denied path should be denied."""
        cfg = Config(redirect_rules=[Rule("deny", "/etc/*")])
        result = check(
            "curl --output=/etc/config https://example.com", config=cfg, cwd=tmp_path
        )
        output = result.get("hookSpecificOutput", {})
        assert output.get("permissionDecision") == "deny"
