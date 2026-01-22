"""
AWS CLI handler for Dippy.

Handles aws, aws-vault, and similar AWS tools.
"""

import re

from dippy.cli import Classification

# SQL read-only detection for Athena queries
_SKIP_PATTERN = re.compile(r"\s+|--[^\n]*|/\*.*?\*/", re.DOTALL)
_KEYWORD_PATTERN = re.compile(r"[A-Za-z_]\w*")
_READONLY_KEYWORDS = frozenset({"SELECT", "SHOW", "DESCRIBE", "EXPLAIN"})
_WRITE_KEYWORDS = frozenset(
    {
        "INSERT",
        "CREATE",
        "ALTER",
        "DROP",
        "TRUNCATE",
        "DELETE",
        "UPDATE",
        "MERGE",
        "MSCK",
        "VACUUM",
        "UNLOAD",
        "GRANT",
        "REVOKE",
    }
)


def _skip_cte(sql: str, pos: int) -> int:
    """Skip over CTE definitions (name AS (...), ...) to find main statement."""
    length = len(sql)
    expect_as = True  # After WITH/comma, expect: name AS (...)
    while pos < length:
        # Skip whitespace and comments
        m = _SKIP_PATTERN.match(sql, pos)
        if m:
            pos = m.end()
            continue
        # Check for opening paren - skip balanced parens
        if sql[pos] == "(":
            depth = 1
            pos += 1
            while pos < length and depth > 0:
                if sql[pos] == "(":
                    depth += 1
                elif sql[pos] == ")":
                    depth -= 1
                pos += 1
            expect_as = False  # After CTE body, expect comma or main statement
            continue
        # Check for comma (another CTE follows)
        if sql[pos] == ",":
            pos += 1
            expect_as = True  # After comma, expect another CTE name
            continue
        # Check for identifier/keyword
        m = _KEYWORD_PATTERN.match(sql, pos)
        if m:
            kw = m.group().upper()
            if expect_as:
                # This is a CTE name or AS keyword - skip it
                pos = m.end()
                if kw == "AS":
                    expect_as = False
                continue
            # Not expecting AS - check if this is the main statement
            if kw in _READONLY_KEYWORDS or kw in _WRITE_KEYWORDS:
                return pos
            # Unknown keyword after CTE - skip it
            pos = m.end()
            continue
        # Unknown character - move forward
        pos += 1
    return pos


def is_readonly_sql(sql: str) -> bool | None:
    """Check if SQL is read-only. Returns True if read-only, False if write, None if unknown."""
    pos = 0
    while pos < len(sql):
        # Skip whitespace and comments
        m = _SKIP_PATTERN.match(sql, pos)
        if m:
            pos = m.end()
            continue
        # Find keyword
        m = _KEYWORD_PATTERN.match(sql, pos)
        if not m:
            return None
        kw = m.group().upper()
        if kw == "WITH":
            # CTE - skip past all CTE definitions to find actual statement
            pos = _skip_cte(sql, m.end())
            continue
        if kw in _READONLY_KEYWORDS:
            return True
        if kw in _WRITE_KEYWORDS:
            return False
        return None
    return None


def _extract_athena_query_string(tokens: list[str]) -> str | None:
    """Extract --query-string value from Athena command tokens."""
    for i, token in enumerate(tokens):
        if token == "--query-string" and i + 1 < len(tokens):
            return tokens[i + 1]
        if token.startswith("--query-string="):
            return token[len("--query-string=") :]
    return None

COMMANDS = ["aws"]

# Safe action prefixes that appear in AWS CLI commands
SAFE_ACTION_PREFIXES = frozenset(
    {
        "describe-",
        "list-",
        "get-",
        "show-",
        "head-",
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
    }
)

# Exact safe action names
SAFE_ACTIONS_EXACT = frozenset(
    {
        "ls",
        "wait",
        "help",
        "query",
        "scan",
        "tail",
        "receive-message",  # sqs
        "batch-get-item",
        "transact-get-items",  # dynamodb
        "batch-get-image",  # ecr
        "start-query",
        "stop-query",  # logs
    }
)

# Actions that look safe but should require confirmation
UNSAFE_EXCEPTIONS = frozenset(
    {
        "assume-role",
        "assume-role-with-saml",
        "assume-role-with-web-identity",
        "get-secret-value",  # Sensitive data exposure
        "start-image-scan",  # ecr - triggers a scan
    }
)


# Explicitly unsafe action keywords
UNSAFE_ACTION_KEYWORDS = frozenset(
    {
        "create",
        "delete",
        "remove",
        "rm",
        "put",
        "update",
        "modify",
        "set",
        "start",
        "stop",
        "terminate",
        "reboot",
        "attach",
        "detach",
        "associate",
        "disassociate",
        "authorize",
        "revoke",
        "copy",
        "cp",
        "mv",
        "sync",
        "mb",
        "rb",  # s3 mutations
        "invoke",  # Lambda invoke
        "execute",
        "run",
        "enable",
        "disable",
        "register",
        "deregister",
        "import",
        "export",
    }
)


# Services where all commands are safe
ALWAYS_SAFE_SERVICES = frozenset(
    {
        "pricing",  # Price lookups
    }
)

# STS safe actions (assume-role variants are NOT safe)
STS_SAFE_ACTIONS = frozenset(
    {
        "get-caller-identity",
        "get-session-token",
        "get-access-key-info",
        "get-federation-token",
        "decode-authorization-message",
    }
)


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
    # Athena - query service for S3 data
    ("athena", "list-databases"),
    ("athena", "list-data-catalogs"),
    ("athena", "list-engine-versions"),
    ("athena", "list-named-queries"),
    ("athena", "list-query-executions"),
    ("athena", "list-prepared-statements"),
    ("athena", "list-work-groups"),
    ("athena", "list-table-metadata"),
    ("athena", "list-tags-for-resource"),
    ("athena", "get-database"),
    ("athena", "get-data-catalog"),
    ("athena", "get-named-query"),
    ("athena", "get-prepared-statement"),
    ("athena", "get-query-execution"),
    ("athena", "get-query-results"),
    ("athena", "get-query-runtime-statistics"),
    ("athena", "get-table-metadata"),
    ("athena", "get-work-group"),
    ("athena", "batch-get-named-query"),
    ("athena", "batch-get-query-execution"),
    ("athena", "batch-get-prepared-statement"),
}


def get_description(tokens: list[str]) -> str:
    """Compute description for aws command."""
    if len(tokens) < 2:
        return "aws"
    # Find service and action
    service = None
    action = None
    global_opts_with_value = {
        "--region",
        "--profile",
        "--output",
        "--endpoint-url",
        "--cli-connect-timeout",
        "--cli-read-timeout",
        "--ca-bundle",
        "--color",
        "--query",
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
    if service and action:
        return f"aws {service} {action}"
    if service:
        return f"aws {service}"
    return "aws"


def classify(tokens: list[str]) -> Classification:
    """Classify AWS CLI command."""
    base = tokens[0] if tokens else "aws"
    if len(tokens) < 2:
        return Classification("ask", description=base)

    desc = get_description(tokens)

    # Check for --help anywhere (makes command safe)
    if "--help" in tokens or "-h" in tokens:
        return Classification("approve", description=desc)

    # Find the service and action
    service = None
    action = None

    global_opts_with_value = {
        "--region",
        "--profile",
        "--output",
        "--endpoint-url",
        "--cli-connect-timeout",
        "--cli-read-timeout",
        "--ca-bundle",
        "--color",
        "--query",
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
        return Classification("ask", description=desc)

    # Help is always safe
    if service == "help" or action == "help":
        return Classification("approve", description=desc)

    # Always-safe services
    if service in ALWAYS_SAFE_SERVICES:
        return Classification("approve", description=desc)

    # STS special handling
    if service == "sts":
        if action in STS_SAFE_ACTIONS:
            return Classification("approve", description=desc)
        return Classification("ask", description=desc)

    # Configure special handling
    if service == "configure":
        if action in {"list", "list-profiles", "get"}:
            return Classification("approve", description=desc)
        return Classification("ask", description=desc)

    # SSM special handling - --with-decryption exposes sensitive data
    if service == "ssm" and "--with-decryption" in tokens:
        return Classification("ask", description=desc)

    # Athena special handling - analyze SQL for read-only queries
    if service == "athena" and action == "start-query-execution":
        query_string = _extract_athena_query_string(tokens)
        if query_string is not None:
            readonly = is_readonly_sql(query_string)
            if readonly is True:
                return Classification("approve", description=desc)
        # Not read-only or couldn't determine - ask
        return Classification("ask", description=desc)

    # Check specific safe commands
    if action and (service, action) in SAFE_COMMANDS:
        return Classification("approve", description=desc)

    # Check action patterns
    if action:
        # Check exceptions first (things that look safe but aren't)
        if action in UNSAFE_EXCEPTIONS:
            return Classification("ask", description=desc)

        # Exact safe actions
        if action in SAFE_ACTIONS_EXACT:
            return Classification("approve", description=desc)

        # Safe prefixes
        for prefix in SAFE_ACTION_PREFIXES:
            if action.startswith(prefix):
                return Classification("approve", description=desc)

        # Unsafe keywords
        for keyword in UNSAFE_ACTION_KEYWORDS:
            if keyword in action:
                return Classification("ask", description=desc)

    # Default: ask user
    return Classification("ask", description=desc)
