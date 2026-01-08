"""
AWS CLI handler for Dippy.

Handles aws, aws-vault, and similar AWS tools.
"""

from typing import Optional


# Safe action prefixes that appear in AWS CLI commands
SAFE_ACTION_PREFIXES = frozenset({
    "describe-", "list-", "get-", "show-", "head-",
    "lookup-",  # cloudtrail lookup-events
    "filter-",  # logs filter-log-events (but not put-metric-filter!)
    "validate-",  # cloudformation validate-template
    "estimate-",  # cloudformation estimate-template-cost
    "simulate-",  # iam simulate-principal-policy
    "generate-",  # iam generate-credential-report
    "download-",  # rds download-db-log-file-portion
    "detect-",  # cloudformation detect-stack-drift
    "test-",  # route53 test-dns-answer
    "check-if-",  # sns check-if-phone-number-is-opted-out
    "admin-get-",  # cognito admin-get-user
    "admin-list-",  # cognito admin-list-*
})

# Exact safe action names
SAFE_ACTIONS_EXACT = frozenset({
    "ls", "wait", "help", "query", "scan", "tail",
    "receive-message",  # sqs
    "batch-get-item", "transact-get-items",  # dynamodb
    "batch-get-image",  # ecr
    "start-query", "stop-query",  # logs
})

# Actions that look safe but should require confirmation
UNSAFE_EXCEPTIONS = frozenset({
    "assume-role", "assume-role-with-saml", "assume-role-with-web-identity",
    "get-secret-value",  # Sensitive data exposure
    "start-image-scan",  # ecr - triggers a scan
})


# Explicitly unsafe action keywords
UNSAFE_ACTION_KEYWORDS = frozenset({
    "create", "delete", "remove", "rm",
    "put", "update", "modify", "set",
    "start", "stop", "terminate", "reboot",
    "attach", "detach", "associate", "disassociate",
    "authorize", "revoke",
    "copy", "cp", "mv", "sync", "mb", "rb",  # s3 mutations
    "invoke",  # Lambda invoke
    "execute", "run",
    "enable", "disable",
    "register", "deregister",
    "import", "export",
})


# Services where all commands are safe
ALWAYS_SAFE_SERVICES = frozenset({
    "pricing",  # Price lookups
})

# STS safe actions (assume-role variants are NOT safe)
STS_SAFE_ACTIONS = frozenset({
    "get-caller-identity", "get-session-token", "get-access-key-info",
    "get-federation-token", "decode-authorization-message",
})


# Specific safe commands (service, action pairs)
SAFE_COMMANDS = {
    ("s3", "ls"),
    ("s3api", "list-buckets"),
    ("s3api", "list-objects"),
    ("s3api", "list-objects-v2"),
    ("s3api", "head-object"),
    ("s3api", "head-bucket"),
    ("s3api", "get-object-tagging"),
    ("s3api", "get-bucket-tagging"),
    ("s3api", "get-bucket-location"),
    ("ec2", "describe-instances"),
    ("ec2", "describe-vpcs"),
    ("ec2", "describe-subnets"),
    ("ec2", "describe-security-groups"),
    ("iam", "list-users"),
    ("iam", "list-roles"),
    ("iam", "list-policies"),
    ("iam", "get-user"),
    ("iam", "get-role"),
    ("lambda", "list-functions"),
    ("lambda", "get-function"),
    ("rds", "describe-db-instances"),
    ("rds", "describe-db-clusters"),
    ("ecs", "list-clusters"),
    ("ecs", "list-services"),
    ("ecs", "list-tasks"),
    ("ecs", "describe-clusters"),
    ("ecs", "describe-services"),
    ("ecs", "describe-tasks"),
    ("cloudformation", "list-stacks"),
    ("cloudformation", "describe-stacks"),
    ("cloudformation", "describe-stack-resources"),
    ("cloudformation", "get-template"),
    ("logs", "describe-log-groups"),
    ("logs", "describe-log-streams"),
    ("logs", "filter-log-events"),
    ("logs", "get-log-events"),
    ("ssm", "describe-parameters"),
    ("ssm", "get-parameter"),
    ("ssm", "get-parameters"),
    ("ssm", "get-parameters-by-path"),
    ("secretsmanager", "list-secrets"),
    ("secretsmanager", "describe-secret"),
    # Note: get-secret-value is read-only but sensitive
    ("route53", "list-hosted-zones"),
    ("route53", "list-resource-record-sets"),
    ("cloudwatch", "list-metrics"),
    ("cloudwatch", "get-metric-statistics"),
    ("cloudwatch", "describe-alarms"),
    ("sqs", "list-queues"),
    ("sqs", "get-queue-attributes"),
    ("sns", "list-topics"),
    ("sns", "list-subscriptions"),
    ("dynamodb", "list-tables"),
    ("dynamodb", "describe-table"),
}


def check(command: str, tokens: list[str]) -> tuple[Optional[str], str]:
    """
    Check if an AWS CLI command should be approved or denied.

    Returns:
        (decision, description) where decision is "approve" or None.
    """
    if len(tokens) < 2:
        return (None, "aws")

    # Find the service and action
    # aws [global-opts] service action [opts]
    service = None
    action = None

    # Check for --help anywhere (makes command safe)
    if "--help" in tokens or "-h" in tokens:
        return ("approve", "aws help")

    # Global options that take a value
    global_opts_with_value = {
        "--region", "--profile", "--output", "--endpoint-url",
        "--cli-connect-timeout", "--cli-read-timeout",
        "--ca-bundle", "--color", "--query",
    }

    i = 1
    while i < len(tokens):
        token = tokens[i]

        # Skip global options
        if token.startswith("--"):
            # Check if option takes a value
            if token in global_opts_with_value:
                i += 2
                continue
            # Handle --option=value format
            if "=" in token:
                i += 1
                continue
            i += 1
            continue

        # First non-option is service
        if service is None:
            service = token
            i += 1
            continue

        # Second non-option is action
        if action is None:
            action = token
            break

        i += 1

    if not service:
        return (None, "aws")

    # Build description
    desc = f"aws {service}" + (f" {action}" if action else "")

    # Help is always safe
    if service == "help" or action == "help":
        return ("approve", desc)

    # Always-safe services
    if service in ALWAYS_SAFE_SERVICES:
        return ("approve", desc)

    # STS special handling
    if service == "sts":
        if action in STS_SAFE_ACTIONS:
            return ("approve", desc)
        return (None, desc)  # assume-role variants need confirmation

    # Configure special handling
    if service == "configure":
        if action in {"list", "list-profiles", "get"}:
            return ("approve", desc)
        return (None, desc)  # set, sso, import, export-credentials need confirmation

    # SSM special handling - --with-decryption exposes sensitive data
    if service == "ssm" and "--with-decryption" in tokens:
        return (None, desc)

    # Check specific safe commands
    if action and (service, action) in SAFE_COMMANDS:
        return ("approve", desc)

    # Check action patterns
    if action:
        # Check exceptions first (things that look safe but aren't)
        if action in UNSAFE_EXCEPTIONS:
            return (None, desc)

        # Exact safe actions
        if action in SAFE_ACTIONS_EXACT:
            return ("approve", desc)

        # Safe prefixes
        for prefix in SAFE_ACTION_PREFIXES:
            if action.startswith(prefix):
                return ("approve", desc)

        # Unsafe keywords - don't outright deny, just require confirmation
        for keyword in UNSAFE_ACTION_KEYWORDS:
            if keyword in action:
                return (None, desc)

    # Default: ask user
    return (None, desc)
