"""
Comprehensive tests for helm CLI handler.

Helm is the Kubernetes package manager. Safe operations are read-only queries
and dry-run modes. Unsafe operations mutate cluster state, local files,
or remote registries.
"""

from __future__ import annotations

import pytest

from conftest import is_approved, needs_confirmation


TESTS = [
    # === SAFE: Help and version ===
    ("helm --help", True),
    ("helm -h", True),
    ("helm --version", True),
    ("helm version", True),
    ("helm help", True),
    ("helm help install", True),
    ("helm install --help", True),
    #
    # === SAFE: Environment info ===
    ("helm env", True),
    #
    # === SAFE: Completion ===
    ("helm completion bash", True),
    ("helm completion zsh", True),
    ("helm completion fish", True),
    ("helm completion powershell", True),
    #
    # === SAFE: List releases ===
    ("helm list", True),
    ("helm ls", True),
    ("helm list -A", True),
    ("helm list --all-namespaces", True),
    ("helm list -n production", True),
    ("helm list --namespace production", True),
    ("helm list -o json", True),
    ("helm list --output yaml", True),
    ("helm list --filter nginx", True),
    ("helm list --deployed", True),
    ("helm list --failed", True),
    ("helm list --pending", True),
    ("helm list --superseded", True),
    ("helm list --uninstalled", True),
    ("helm list --uninstalling", True),
    #
    # === SAFE: Get release info (read from cluster) ===
    ("helm get all myrelease", True),
    ("helm get hooks myrelease", True),
    ("helm get manifest myrelease", True),
    ("helm get metadata myrelease", True),
    ("helm get notes myrelease", True),
    ("helm get values myrelease", True),
    ("helm get values myrelease -a", True),
    ("helm get values myrelease --all", True),
    ("helm get values myrelease -n production", True),
    ("helm get all myrelease --revision 3", True),
    #
    # === SAFE: Show chart info ===
    ("helm show all nginx/nginx", True),
    ("helm show chart nginx/nginx", True),
    ("helm show crds nginx/nginx", True),
    ("helm show readme nginx/nginx", True),
    ("helm show values nginx/nginx", True),
    ("helm inspect all nginx/nginx", True),  # alias
    ("helm inspect chart nginx/nginx", True),
    ("helm inspect values nginx/nginx", True),
    ("helm show all ./mychart", True),
    ("helm show values ./mychart --version 1.2.3", True),
    #
    # === SAFE: Status ===
    ("helm status myrelease", True),
    ("helm status myrelease -n production", True),
    ("helm status myrelease --revision 3", True),
    ("helm status myrelease -o json", True),
    #
    # === SAFE: History ===
    ("helm history myrelease", True),
    ("helm history myrelease -n production", True),
    ("helm history myrelease --max 10", True),
    ("helm history myrelease -o json", True),
    #
    # === SAFE: Search ===
    ("helm search hub nginx", True),
    ("helm search repo nginx", True),
    ("helm search hub nginx --max-col-width 80", True),
    ("helm search repo nginx --versions", True),
    ("helm search repo nginx -l", True),
    ("helm search repo nginx --version ^2.0.0", True),
    #
    # === SAFE: Template (local rendering, stdout only) ===
    ("helm template myrelease nginx/nginx", True),
    ("helm template myrelease ./mychart", True),
    ("helm template myrelease nginx/nginx --set key=value", True),
    ("helm template myrelease nginx/nginx -f values.yaml", True),
    ("helm template myrelease nginx/nginx --values values.yaml", True),
    ("helm template myrelease nginx/nginx --version 1.2.3", True),
    ("helm template myrelease nginx/nginx --namespace production", True),
    ("helm template myrelease nginx/nginx --include-crds", True),
    ("helm template myrelease nginx/nginx --skip-crds", True),
    ("helm template myrelease nginx/nginx --no-hooks", True),
    ("helm template myrelease nginx/nginx --validate", True),
    #
    # === SAFE: Lint ===
    ("helm lint ./mychart", True),
    ("helm lint ./mychart --strict", True),
    ("helm lint ./mychart --with-subcharts", True),
    ("helm lint ./mychart --set key=value", True),
    ("helm lint ./mychart -f values.yaml", True),
    #
    # === SAFE: Verify ===
    ("helm verify ./mychart-1.0.0.tgz", True),
    ("helm verify ./mychart-1.0.0.tgz --keyring pubring.gpg", True),
    #
    # === SAFE: Repo list ===
    ("helm repo list", True),
    ("helm repo ls", True),
    ("helm repo list -o json", True),
    #
    # === SAFE: Dependency list ===
    ("helm dependency list ./mychart", True),
    ("helm dep list ./mychart", True),
    ("helm dependency ls ./mychart", True),
    ("helm dep ls ./mychart", True),
    #
    # === SAFE: Plugin list and verify ===
    ("helm plugin list", True),
    ("helm plugin ls", True),
    ("helm plugin verify ./myplugin", True),
    #
    # === SAFE: Dry-run modes ===
    ("helm install myrelease nginx/nginx --dry-run", True),
    ("helm install myrelease nginx/nginx --dry-run=client", True),
    ("helm install myrelease nginx/nginx --dry-run=server", True),
    ("helm upgrade myrelease nginx/nginx --dry-run", True),
    ("helm upgrade myrelease nginx/nginx --dry-run=client", True),
    ("helm uninstall myrelease --dry-run", True),
    ("helm rollback myrelease 2 --dry-run", True),
    ("helm install myrelease nginx/nginx -n prod --dry-run", True),
    ("helm install myrelease nginx/nginx --set foo=bar --dry-run", True),
    ("helm upgrade --install myrelease nginx/nginx --dry-run", True),
    #
    # === UNSAFE: Install (mutates cluster) ===
    ("helm install myrelease nginx/nginx", False),
    ("helm install myrelease ./mychart", False),
    ("helm install myrelease nginx/nginx -n production", False),
    ("helm install myrelease nginx/nginx --namespace production", False),
    ("helm install myrelease nginx/nginx --create-namespace", False),
    ("helm install myrelease nginx/nginx --set key=value", False),
    ("helm install myrelease nginx/nginx -f values.yaml", False),
    ("helm install myrelease nginx/nginx --values values.yaml", False),
    ("helm install myrelease nginx/nginx --version 1.2.3", False),
    ("helm install myrelease nginx/nginx --wait", False),
    ("helm install myrelease nginx/nginx --timeout 5m", False),
    ("helm install myrelease nginx/nginx --atomic", False),
    ("helm install nginx/nginx --generate-name", False),
    ("helm install nginx/nginx -g", False),
    #
    # === UNSAFE: Upgrade (mutates cluster) ===
    ("helm upgrade myrelease nginx/nginx", False),
    ("helm upgrade myrelease ./mychart", False),
    ("helm upgrade myrelease nginx/nginx -n production", False),
    ("helm upgrade myrelease nginx/nginx --install", False),
    ("helm upgrade --install myrelease nginx/nginx", False),
    ("helm upgrade myrelease nginx/nginx --set key=value", False),
    ("helm upgrade myrelease nginx/nginx -f values.yaml", False),
    ("helm upgrade myrelease nginx/nginx --reuse-values", False),
    ("helm upgrade myrelease nginx/nginx --reset-values", False),
    ("helm upgrade myrelease nginx/nginx --force", False),
    ("helm upgrade myrelease nginx/nginx --cleanup-on-fail", False),
    #
    # === UNSAFE: Uninstall (mutates cluster) ===
    ("helm uninstall myrelease", False),
    ("helm delete myrelease", False),  # alias
    ("helm del myrelease", False),  # alias
    ("helm un myrelease", False),  # alias
    ("helm uninstall myrelease -n production", False),
    ("helm uninstall myrelease --keep-history", False),
    ("helm uninstall myrelease --no-hooks", False),
    ("helm uninstall myrelease --wait", False),
    #
    # === UNSAFE: Rollback (mutates cluster) ===
    ("helm rollback myrelease", False),
    ("helm rollback myrelease 2", False),
    ("helm rollback myrelease 2 -n production", False),
    ("helm rollback myrelease 2 --force", False),
    ("helm rollback myrelease 2 --no-hooks", False),
    ("helm rollback myrelease 2 --wait", False),
    #
    # === UNSAFE: Test (runs in cluster) ===
    ("helm test myrelease", False),
    ("helm test myrelease -n production", False),
    ("helm test myrelease --logs", False),
    ("helm test myrelease --timeout 5m", False),
    #
    # === UNSAFE: Create (creates local files) ===
    ("helm create mychart", False),
    ("helm create ./path/to/mychart", False),
    ("helm create mychart --starter mystarter", False),
    #
    # === UNSAFE: Package (creates local file) ===
    ("helm package ./mychart", False),
    ("helm package ./mychart -d ./output", False),
    ("helm package ./mychart --destination ./output", False),
    ("helm package ./mychart --version 1.2.3", False),
    ("helm package ./mychart --app-version 2.0.0", False),
    ("helm package ./mychart --sign", False),
    ("helm package ./mychart -u", False),
    ("helm package ./mychart --dependency-update", False),
    #
    # === UNSAFE: Pull (downloads/creates local files) ===
    ("helm pull nginx/nginx", False),
    ("helm fetch nginx/nginx", False),  # alias
    ("helm pull nginx/nginx --untar", False),
    ("helm pull nginx/nginx --untardir ./charts", False),
    ("helm pull nginx/nginx -d ./charts", False),
    ("helm pull nginx/nginx --destination ./charts", False),
    ("helm pull nginx/nginx --version 1.2.3", False),
    ("helm pull oci://registry.example.com/charts/nginx", False),
    #
    # === UNSAFE: Push (mutates remote registry) ===
    ("helm push mychart-1.0.0.tgz oci://registry.example.com/charts", False),
    ("helm push ./mychart-1.0.0.tgz oci://registry.example.com/charts", False),
    #
    # === UNSAFE: Repo mutations ===
    ("helm repo add stable https://charts.helm.sh/stable", False),
    ("helm repo add bitnami https://charts.bitnami.com/bitnami", False),
    (
        "helm repo add myrepo https://example.com/charts --username user --password pass",
        False,
    ),
    ("helm repo remove stable", False),
    ("helm repo rm stable", False),  # alias
    ("helm repo update", False),
    ("helm repo up", False),  # alias
    ("helm repo index ./charts", False),
    ("helm repo index ./charts --url https://example.com/charts", False),
    ("helm repo index ./charts --merge index.yaml", False),
    #
    # === UNSAFE: Dependency mutations ===
    ("helm dependency update ./mychart", False),
    ("helm dep update ./mychart", False),
    ("helm dep up ./mychart", False),
    ("helm dependency build ./mychart", False),
    ("helm dep build ./mychart", False),
    ("helm dependency update ./mychart --skip-refresh", False),
    #
    # === UNSAFE: Plugin mutations ===
    ("helm plugin install https://github.com/example/helm-plugin", False),
    ("helm plugin install ./path/to/plugin", False),
    ("helm plugin uninstall myplugin", False),
    ("helm plugin update myplugin", False),
    ("helm plugin package ./myplugin", False),
    #
    # === UNSAFE: Registry auth ===
    ("helm registry login registry.example.com", False),
    ("helm registry login registry.example.com -u user", False),
    ("helm registry login registry.example.com --username user --password pass", False),
    ("helm registry logout registry.example.com", False),
    #
    # === Edge cases ===
    ("helm", False),  # No subcommand
    ("helm --debug list", True),  # Global flag before subcommand
    ("helm -n production list", True),
    ("helm --namespace production list", True),
    ("helm --kube-context dev list", True),
    ("helm list --debug", True),  # Flag after subcommand
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool) -> None:
    """Test that command safety is detected correctly."""
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approved for: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirmation for: {command}"
