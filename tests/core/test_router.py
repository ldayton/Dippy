"""
Tests for the main Dippy router and integration.
"""

import pytest


def is_approved(result: dict) -> bool:
    """Check if a hook result is an approval."""
    output = result.get("hookSpecificOutput", {})
    return output.get("permissionDecision") == "allow"


def needs_confirmation(result: dict) -> bool:
    """Check if a hook result requires user confirmation."""
    output = result.get("hookSpecificOutput", {})
    return output.get("permissionDecision") == "ask"


class TestRouterBasics:
    """Basic router functionality tests."""
    
    def test_empty_command(self, check):
        """Empty commands should ask user."""
        result = check("")
        assert needs_confirmation(result)
    
    def test_whitespace_only(self, check):
        """Whitespace-only commands should ask user."""
        result = check("   ")
        assert needs_confirmation(result)
    
    def test_simple_safe_command(self, check):
        """Simple safe commands should be approved."""
        result = check("ls")
        assert is_approved(result)
    
    def test_unknown_command(self, check):
        """Unknown commands should ask user."""
        result = check("some-unknown-command --flag")
        assert needs_confirmation(result)


class TestOutputRedirects:
    """Tests for output redirect handling."""
    
    def test_redirect_stdout(self, check):
        """Output redirect should require confirmation."""
        result = check("ls > file.txt")
        assert needs_confirmation(result)
    
    def test_redirect_append(self, check):
        """Append redirect should require confirmation."""
        result = check("echo hello >> file.txt")
        assert needs_confirmation(result)
    
    def test_safe_command_with_redirect(self, check):
        """Even safe commands with redirects need confirmation."""
        result = check("cat foo.txt > bar.txt")
        assert needs_confirmation(result)


class TestPipelines:
    """Tests for pipeline command handling."""
    
    def test_safe_pipeline(self, check):
        """Pipeline of safe commands should be approved."""
        result = check("ls | grep foo")
        assert is_approved(result)
    
    def test_safe_pipeline_multiple(self, check):
        """Multi-stage safe pipeline should be approved."""
        result = check("cat file.txt | grep pattern | wc -l")
        assert is_approved(result)
    
    def test_pipeline_with_unsafe(self, check):
        """Pipeline with unsafe command needs confirmation."""
        result = check("ls | rm -rf")
        assert needs_confirmation(result)


class TestPrefixCommands:
    """Tests for prefix command handling (time, env, etc.)."""
    
    def test_time_prefix(self, check):
        """time prefix with safe command should be approved."""
        result = check("time ls -la")
        assert is_approved(result)
    
    def test_env_prefix(self, check):
        """env prefix with safe command should be approved."""
        result = check("env FOO=bar ls")
        assert is_approved(result)
    
    def test_timeout_prefix(self, check):
        """timeout prefix with safe command should be approved."""
        result = check("timeout 5 cat file.txt")
        assert is_approved(result)


class TestVersionHelp:
    """Tests for version/help flag handling."""
    
    @pytest.mark.parametrize("cmd", [
        "python --version",
        "node --version",
        "cargo --help",
        "unknown-tool -h",
        "anything --version",
    ])
    def test_version_help_flags(self, check, cmd):
        """Version and help flags should always be safe."""
        result = check(cmd)
        assert is_approved(result)


class TestCLIRouting:
    """Tests for CLI handler routing."""
    
    def test_routes_to_git(self, check):
        """Git commands should route to git handler."""
        result = check("git status")
        assert is_approved(result)
    
    def test_routes_to_aws(self, check):
        """AWS commands should route to aws handler."""
        result = check("aws s3 ls")
        assert is_approved(result)
    
    def test_routes_to_kubectl(self, check):
        """Kubectl commands should route to kubectl handler."""
        result = check("kubectl get pods")
        assert is_approved(result)
    
    def test_routes_kubectl_directly(self, check_single):
        """Test kubectl handler directly."""
        from dippy.cli import kubectl
        decision, desc = kubectl.check("kubectl get pods", ["kubectl", "get", "pods"])
        assert decision == "approve"
    
    def test_routes_to_docker(self, check):
        """Docker commands should route to docker handler."""
        result = check("docker ps")
        assert is_approved(result)
    
    def test_routes_to_terraform(self, check):
        """Terraform commands should route to terraform handler."""
        result = check("terraform plan")
        assert is_approved(result)
