"""
AWS CLI handler for Dippy.

Handles aws, aws-vault, and similar AWS tools.
"""


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


def check(tokens: list[str]) -> bool:
    """Check if AWS CLI command is safe."""
    if len(tokens) < 2:
        return False

    # Check for --help anywhere (makes command safe)
    if "--help" in tokens or "-h" in tokens:
        return True

    # Find the service and action
    service = None
    action = None

    global_opts_with_value = {
        "--region", "--profile", "--output", "--endpoint-url",
        "--cli-connect-timeout", "--cli-read-timeout",
        "--ca-bundle", "--color", "--query",
    }

    i = 1
    while i < len(tokens):
        token = tokens[i]

        if token.startswith("--"):
            if token in global_opts_with_value:
                i += 2
                continue
            if "=" in token:
                i += 1
                continue
            i += 1
            continue

        if service is None:
            service = token
            i += 1
            continue

        if action is None:
            action = token
            break

        i += 1

    if not service:
        return False

    # Help is always safe
    if service == "help" or action == "help":
        return True

    # Always-safe services
    if service in ALWAYS_SAFE_SERVICES:
        return True

    # STS special handling
    if service == "sts":
        return action in STS_SAFE_ACTIONS

    # Configure special handling
    if service == "configure":
        return action in {"list", "list-profiles", "get"}

    # SSM special handling - --with-decryption exposes sensitive data
    if service == "ssm" and "--with-decryption" in tokens:
        return False

    # Check specific safe commands
    if action and (service, action) in SAFE_COMMANDS:
        return True

    # Check action patterns
    if action:
        # Check exceptions first (things that look safe but aren't)
        if action in UNSAFE_EXCEPTIONS:
            return False

        # Exact safe actions
        if action in SAFE_ACTIONS_EXACT:
            return True

        # Safe prefixes
        for prefix in SAFE_ACTION_PREFIXES:
            if action.startswith(prefix):
                return True

        # Unsafe keywords
        for keyword in UNSAFE_ACTION_KEYWORDS:
            if keyword in action:
                return False

    # Default: ask user
    return False
