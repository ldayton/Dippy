"""
Comprehensive tests for Auth0 CLI handler.

Tests cover auth0 commands for identity management.
"""

from __future__ import annotations

import pytest

from conftest import is_approved, needs_confirmation


TESTS = [
    #
    # === APPS ===
    #
    # --- List/Show (safe) ---
    ("auth0 apps list", True),
    ("auth0 apps ls", True),
    ("auth0 apps show app_12345", True),
    #
    # --- Create/Update/Delete (unsafe) ---
    ("auth0 apps create", False),
    ("auth0 apps create --name myapp", False),
    ("auth0 apps update app_12345", False),
    ("auth0 apps delete app_12345", False),
    ("auth0 apps rm app_12345", False),
    #
    # --- Open (safe, just opens browser) ---
    ("auth0 apps open app_12345", False),  # Might trigger browser, safer to confirm
    #
    # === USERS ===
    #
    # --- Search/Show (safe) ---
    ("auth0 users search", True),
    ("auth0 users search --query email:user@example.com", True),
    ("auth0 users search-by-email user@example.com", True),
    ("auth0 users show user_12345", True),
    #
    # --- Create/Update/Delete (unsafe) ---
    ("auth0 users create", False),
    ("auth0 users update auth0|123456", False),
    ("auth0 users delete auth0|123456", False),
    ("auth0 users import", False),
    ("auth0 users import --connection myconn", False),
    #
    # === LOGS ===
    #
    # --- List/Tail (safe, read-only) ---
    ("auth0 logs list", True),
    ("auth0 logs ls", True),
    ("auth0 logs tail", True),
    ("auth0 logs tail --filter type:s", True),
    #
    # === ACTIONS ===
    #
    # --- List/Show/Diff (safe) ---
    ("auth0 actions list", True),
    ("auth0 actions ls", True),
    ("auth0 actions show act_12345", True),
    ("auth0 actions diff act_12345", True),
    #
    # --- Create/Update/Delete/Deploy (unsafe) ---
    ("auth0 actions create", False),
    ("auth0 actions update act_12345", False),
    ("auth0 actions delete act_12345", False),
    ("auth0 actions rm act_12345", False),
    ("auth0 actions deploy act_12345", False),
    #
    # === APIS ===
    #
    # --- List/Show (safe) ---
    ("auth0 apis list", True),
    ("auth0 apis ls", True),
    ("auth0 apis show api_12345", True),
    #
    # --- Create/Update/Delete (unsafe) ---
    ("auth0 apis create", False),
    ("auth0 apis update api_12345", False),
    ("auth0 apis delete api_12345", False),
    ("auth0 apis rm api_12345", False),
    #
    # --- Scopes (list is safe) ---
    ("auth0 apis scopes list api_12345", True),
    ("auth0 apis scopes ls api_12345", True),
    #
    # === ROLES ===
    #
    # --- List/Show (safe) ---
    ("auth0 roles list", True),
    ("auth0 roles ls", True),
    ("auth0 roles show rol_12345", True),
    #
    # --- Create/Update/Delete (unsafe) ---
    ("auth0 roles create", False),
    ("auth0 roles update rol_12345", False),
    ("auth0 roles delete rol_12345", False),
    ("auth0 roles rm rol_12345", False),
    #
    # --- Permissions (list safe, add/remove unsafe) ---
    ("auth0 roles permissions list rol_12345", True),
    ("auth0 roles perms list rol_12345", True),
    ("auth0 roles permissions add rol_12345", False),
    ("auth0 roles permissions remove rol_12345", False),
    ("auth0 roles perms rm rol_12345", False),
    #
    # === ORGANIZATIONS ===
    #
    # --- List/Show (safe) ---
    ("auth0 orgs list", True),
    ("auth0 orgs ls", True),
    ("auth0 orgs show org_12345", True),
    #
    # --- Create/Update/Delete (unsafe) ---
    ("auth0 orgs create", False),
    ("auth0 orgs update org_12345", False),
    ("auth0 orgs delete org_12345", False),
    ("auth0 orgs rm org_12345", False),
    #
    # --- Members (list safe) ---
    ("auth0 orgs members list org_12345", True),
    ("auth0 orgs members ls org_12345", True),
    #
    # === RULES (deprecated but still supported) ===
    #
    # --- List/Show (safe) ---
    ("auth0 rules list", True),
    ("auth0 rules ls", True),
    ("auth0 rules show rul_12345", True),
    #
    # --- Create/Update/Delete/Enable/Disable (unsafe) ---
    ("auth0 rules create", False),
    ("auth0 rules update rul_12345", False),
    ("auth0 rules delete rul_12345", False),
    ("auth0 rules rm rul_12345", False),
    ("auth0 rules enable rul_12345", False),
    ("auth0 rules disable rul_12345", False),
    #
    # === DOMAINS ===
    #
    # --- List/Show (safe) ---
    ("auth0 domains list", True),
    ("auth0 domains ls", True),
    ("auth0 domains show cd_12345", True),
    #
    # --- Create/Update/Delete/Verify (unsafe) ---
    ("auth0 domains create", False),
    ("auth0 domains update cd_12345", False),
    ("auth0 domains delete cd_12345", False),
    ("auth0 domains rm cd_12345", False),
    ("auth0 domains verify cd_12345", False),
    #
    # === PROTECTION ===
    #
    # --- Show (safe) ---
    ("auth0 protection breached-password-detection show", True),
    ("auth0 protection bpd show", True),
    ("auth0 protection brute-force-protection show", True),
    ("auth0 protection bfp show", True),
    ("auth0 protection suspicious-ip-throttling show", True),
    ("auth0 protection sit show", True),
    ("auth0 ap bpd show", True),
    ("auth0 attack-protection bpd show", True),
    #
    # --- Update (unsafe) ---
    ("auth0 protection breached-password-detection update", False),
    ("auth0 protection bpd update", False),
    ("auth0 protection brute-force-protection update", False),
    ("auth0 protection suspicious-ip-throttling update", False),
    #
    # === TENANTS ===
    #
    # --- List (safe) ---
    ("auth0 tenants list", True),
    ("auth0 tenants ls", True),
    #
    # --- Use (unsafe - changes active tenant) ---
    ("auth0 tenants use mytenant", False),
    #
    # === QUICKSTARTS ===
    #
    # --- List (safe) ---
    ("auth0 quickstarts list", True),
    ("auth0 qs list", True),
    ("auth0 quickstarts ls", True),
    #
    # --- Download (unsafe - writes files) ---
    ("auth0 quickstarts download", False),
    ("auth0 qs download", False),
    #
    # === EMAIL ===
    #
    # --- Templates show (safe) ---
    ("auth0 email templates show", True),
    #
    # --- Templates update (unsafe) ---
    ("auth0 email templates update", False),
    #
    # --- Provider show (safe) ---
    ("auth0 email provider show", True),
    #
    # --- Provider create/update/delete (unsafe) ---
    ("auth0 email provider create", False),
    ("auth0 email provider update", False),
    ("auth0 email provider delete", False),
    ("auth0 email provider rm", False),
    #
    # === UNIVERSAL LOGIN ===
    #
    # --- Show (safe) ---
    ("auth0 universal-login show", True),
    ("auth0 ul show", True),
    #
    # --- Update/Customize (unsafe) ---
    ("auth0 universal-login update", False),
    ("auth0 ul update", False),
    ("auth0 universal-login customize", False),
    ("auth0 ul customize", False),
    #
    # --- Templates show (safe) ---
    ("auth0 universal-login templates show", True),
    ("auth0 ul templates show", True),
    #
    # --- Templates update (unsafe) ---
    ("auth0 universal-login templates update", False),
    ("auth0 ul templates update", False),
    #
    # --- Prompts (read-only operations) ---
    ("auth0 universal-login prompts show login", True),
    ("auth0 ul prompts show login", True),
    ("auth0 universal-login prompts update login", False),
    #
    # === TEST ===
    #
    # --- Token/Login (safe - just gets a token or opens browser) ---
    ("auth0 test token", False),  # Gets actual tokens
    ("auth0 test login", False),  # Initiates auth flow
    #
    # === API (raw management API) ===
    #
    # --- GET requests (safe) ---
    ("auth0 api get clients", True),
    ("auth0 api get tenants/settings", True),
    ("auth0 api clients", True),  # defaults to GET
    ("auth0 api stats/daily", True),
    ("auth0 api get users -q search_engine:v3", True),
    #
    # --- POST/PUT/PATCH/DELETE (unsafe) ---
    ("auth0 api post clients", False),
    ("auth0 api put clients/client_id", False),
    ("auth0 api patch clients/client_id", False),
    ("auth0 api delete actions/actions/act_id", False),
    ('auth0 api clients --data \'{"name":"test"}\'', False),
    ('auth0 api clients -d \'{"name":"test"}\'', False),
    #
    # === GLOBAL FLAGS ===
    #
    # --- Tenant flag should not affect safety ---
    ("auth0 --tenant mytenant apps list", True),
    ("auth0 -t mytenant apps list", True),
    ("auth0 apps list --tenant mytenant", True),
    ("auth0 --tenant mytenant apps create", False),
    #
    # --- Debug/no-color flags (safe, informational) ---
    ("auth0 --debug apps list", True),
    ("auth0 --no-color apps list", True),
    ("auth0 --no-input apps list", True),
    #
    # === EDGE CASES ===
    #
    ("auth0", False),  # No subcommand
    ("auth0 --help", True),  # Help is read-only
    ("auth0 apps --help", True),  # Help is read-only
    ("auth0 unknown-command", False),  # Unknown command
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool) -> None:
    """Test that command safety is detected correctly."""
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approved for: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirmation for: {command}"
