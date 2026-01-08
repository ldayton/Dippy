"""Test cases for aws cdk."""

import pytest

from dippy.dippy import is_command_safe, parse_commands, _load_custom_configs

_load_custom_configs()

#
# ==========================================================================
# AWS CDK
# ==========================================================================
#
TESTS = [
    ("cdk list", True),
    ("cdk ls", True),
    ("cdk list --long", True),
    ("cdk ls -l", True),
    ("cdk list --app 'npx ts-node bin/app.ts'", True),
    ("cdk diff", True),
    ("cdk diff MyStack", True),
    ("cdk diff --app 'npx ts-node bin/app.ts'", True),
    ("cdk diff --template template.yaml", True),
    ("cdk diff --security-only", True),
    ("cdk diff --fail", True),
    ("cdk synth", True),
    ("cdk synthesize", True),
    ("cdk synth MyStack", True),
    ("cdk synth --quiet", True),
    ("cdk synth --json", True),
    ("cdk synth --app 'npx ts-node bin/app.ts'", True),
    ("cdk synth --output cdk.out", True),
    ("cdk synth --exclusively", True),
    ("cdk docs", True),
    ("cdk doctor", True),
    ("cdk metadata", True),
    ("cdk metadata MyStack", True),
    ("cdk notices", True),
    ("cdk notices --unacknowledged", True),
    ("cdk acknowledge 12345", True),
    ("cdk context", True),
    ("cdk context --json", True),
    ("cdk version", True),
    ("cdk --version", True),
    ("cdk --help", True),
    ("cdk -h", True),
    ("cdk deploy --help", True),
    # cdk - unsafe (infrastructure changes)
    ("cdk deploy", False),
    ("cdk deploy MyStack", False),
    ("cdk deploy --all", False),
    ("cdk deploy --require-approval never", False),
    ("cdk deploy --hotswap", False),
    ("cdk deploy --force", False),
    ("cdk deploy --app 'npx ts-node bin/app.ts'", False),
    ("cdk destroy", False),
    ("cdk destroy MyStack", False),
    ("cdk destroy --all", False),
    ("cdk destroy --force", False),
    ("cdk bootstrap", False),
    ("cdk bootstrap aws://123456789012/us-east-1", False),
    ("cdk bootstrap --trust 123456789012", False),
    # cdk - unsafe (project initialization)
    ("cdk init", False),
    ("cdk init app", False),
    ("cdk init app --language typescript", False),
    ("cdk init lib --language python", False),
    ("cdk init sample-app --language java", False),
    # cdk - unsafe (resource import/migration)
    ("cdk import", False),
    ("cdk import MyStack", False),
    ("cdk migrate", False),
    ("cdk migrate --from-path template.yaml", False),
    ("cdk migrate --from-stack MyCloudFormationStack", False),
    # cdk - unsafe (continuous deployment)
    ("cdk watch", False),
    ("cdk watch MyStack", False),
    ("cdk watch --hotswap", False),
    # cdk - unsafe (garbage collection)
    ("cdk gc", False),
    ("cdk gc --type all", False),
    # cdk - unsafe (context modifications)
    ("cdk context --reset", False),
    ("cdk context --clear", False),
    ("cdk context --reset key", False),
    # cdk - unsafe (refactoring)
    ("cdk refactor", False),
    ("cdk refactor --dry-run", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_cdk(command: str, expected: bool) -> None:
    """Test command safety."""
    result = parse_commands(command)
    if result.error or not result.commands:
        actual = False
    else:
        actual = all(is_command_safe(cmd) for cmd in result.commands)
    assert actual == expected, f"Expected {expected} for: {command}"
