"""Test cases for kubernetes cli (kubectl)."""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import is_approved, needs_confirmation
from dippy.core.config import Config, Rule

#
# ==========================================================================
# Kubernetes CLI (kubectl)
# ==========================================================================
#
TESTS = [
    ("kubectl --context delete get pods", True),
    ("kubectl -n delete get pods", True),
    ("kubectl --namespace exec get pods", True),
    ("kubectl --context mycluster delete pod foo", False),
    # Kubectl with flags before action
    ("kubectl --context=foo get pods", True),
    ("kubectl --context=foo get managedcertificate ci-api -o jsonpath='{}'", True),
    ("kubectl -n kube-system describe pod foo", True),
    ("kubectl delete pod foo", False),
    ("kubectl --context=foo delete pod list", False),  # deleting pod named "list"
    ("kubectl apply -f foo.yaml", False),
    ("kubectl exec -it foo -- bash", False),
    # Kubectl - comprehensive tests
    # kubectl - safe (read-only commands)
    ("kubectl get pods", True),
    ("kubectl get pods -n kube-system", True),
    ("kubectl get pods --all-namespaces", True),
    ("kubectl get pods -A", True),
    ("kubectl get pods -o wide", True),
    ("kubectl get pods -o json", True),
    ("kubectl get pods -o yaml", True),
    ("kubectl get pods -o jsonpath='{.items[*].metadata.name}'", True),
    ("kubectl get pods --watch", True),
    ("kubectl get pods -w", True),
    ("kubectl get pods --selector=app=nginx", True),
    ("kubectl get nodes", True),
    ("kubectl get services", True),
    ("kubectl get deployments", True),
    ("kubectl get namespaces", True),
    ("kubectl get all", True),
    ("kubectl get all -A", True),
    ("kubectl get configmaps", True),
    ("kubectl get secrets", True),
    ("kubectl get ingress", True),
    ("kubectl get pv", True),
    ("kubectl get pvc", True),
    ("kubectl get events", True),
    ("kubectl get events --sort-by='.lastTimestamp'", True),
    ("kubectl describe pod nginx", True),
    ("kubectl describe pod nginx -n default", True),
    ("kubectl describe node worker-1", True),
    ("kubectl describe deployment nginx", True),
    ("kubectl describe service nginx", True),
    ("kubectl describe configmap my-config", True),
    ("kubectl logs nginx", True),
    ("kubectl logs nginx -c container", True),
    ("kubectl logs nginx --all-containers", True),
    ("kubectl logs nginx -f", True),
    ("kubectl logs nginx --follow", True),
    ("kubectl logs nginx --tail=100", True),
    ("kubectl logs nginx --since=1h", True),
    ("kubectl logs nginx --timestamps", True),
    ("kubectl logs deployment/nginx", True),
    ("kubectl logs -l app=nginx", True),
    ("kubectl explain pods", True),
    ("kubectl explain pods.spec", True),
    ("kubectl explain pods.spec.containers", True),
    ("kubectl explain deployment.spec.template", True),
    ("kubectl top pods", True),
    ("kubectl top pods -n kube-system", True),
    ("kubectl top nodes", True),
    ("kubectl top pod nginx --containers", True),
    ("kubectl cluster-info", True),
    ("kubectl cluster-info dump", True),
    ("kubectl cluster-info dump --output-directory=/tmp/cluster-state", True),
    ("kubectl api-resources", True),
    ("kubectl api-resources --namespaced=true", True),
    ("kubectl api-resources --api-group=apps", True),
    ("kubectl api-versions", True),
    ("kubectl version", True),
    ("kubectl version --client", True),
    ("kubectl version -o json", True),
    ("kubectl diff -f deployment.yaml", True),
    ("kubectl diff -f ./manifests/", True),
    ("kubectl wait --for=condition=Ready pod/nginx", True),
    ("kubectl wait --for=condition=Available deployment/nginx", True),
    ("kubectl wait --for=delete pod/nginx --timeout=60s", True),
    ("kubectl auth can-i get pods", True),
    ("kubectl auth can-i create deployments", True),
    ("kubectl auth can-i '*' '*' -n default", True),
    ("kubectl auth can-i --list", True),
    ("kubectl auth can-i get pods --as system:serviceaccount:default:default", True),
    ("kubectl auth whoami", True),
    ("kubectl rollout status deployment/nginx", True),
    ("kubectl rollout status daemonset/fluentd -n kube-system", True),
    ("kubectl rollout history deployment/nginx", True),
    ("kubectl rollout history deployment/nginx --revision=2", True),
    ("kubectl config view", True),
    ("kubectl config view --minify", True),
    ("kubectl config view -o jsonpath='{.users[*].name}'", True),
    ("kubectl config get-contexts", True),
    ("kubectl config get-clusters", True),
    ("kubectl config get-users", True),
    ("kubectl config current-context", True),
    ("kubectl plugin list", True),
    ("kubectl completion bash", True),
    ("kubectl completion zsh", True),
    ("kubectl kustomize ./overlays/production", True),
    ("kubectl --help", True),
    ("kubectl -h", True),
    ("kubectl get --help", True),
    ("kubectl --version", True),
    # kubectl - unsafe (resource modification)
    ("kubectl apply -f deployment.yaml", False),
    ("kubectl apply -f ./manifests/", False),
    ("kubectl apply -k ./overlays/production", False),
    ("kubectl apply --dry-run=client -f deployment.yaml", False),
    ("kubectl create deployment nginx --image=nginx", False),
    ("kubectl create namespace test", False),
    ("kubectl create configmap my-config --from-literal=key=value", False),
    ("kubectl create secret generic my-secret --from-literal=password=secret", False),
    ("kubectl create -f pod.yaml", False),
    ("kubectl delete pod nginx", False),
    ("kubectl delete pod nginx -n default", False),
    ("kubectl delete pods --all", False),
    ("kubectl delete -f deployment.yaml", False),
    ("kubectl delete deployment nginx", False),
    ("kubectl delete namespace test", False),
    ("kubectl edit deployment nginx", False),
    ("kubectl edit configmap my-config", False),
    ('kubectl patch deployment nginx -p \'{"spec":{"replicas":3}}\'', False),
    (
        'kubectl patch pod nginx --type=\'json\' -p=\'[{"op": "replace", "path": "/spec/containers/0/image", "value":"nginx:latest"}]\'',
        False,
    ),
    ("kubectl replace -f deployment.yaml", False),
    ("kubectl replace --force -f pod.yaml", False),
    ("kubectl label pods nginx app=v2", False),
    ("kubectl label pods nginx app-", False),
    ("kubectl label pods --all status=running", False),
    ("kubectl annotate pods nginx description='my pod'", False),
    ("kubectl annotate pods nginx description-", False),
    ("kubectl set image deployment/nginx nginx=nginx:1.19", False),
    (
        "kubectl set resources deployment/nginx -c=nginx --limits=cpu=200m,memory=512Mi",
        False,
    ),
    ("kubectl set env deployment/nginx ENV_VAR=value", False),
    # kubectl - unsafe (scaling)
    ("kubectl scale deployment nginx --replicas=3", False),
    ("kubectl scale --replicas=5 -f deployment.yaml", False),
    ("kubectl autoscale deployment nginx --min=2 --max=10 --cpu-percent=80", False),
    # kubectl exec - delegates to inner command analysis
    ("kubectl exec nginx -- ls /", True),  # ls is safe
    ("kubectl exec -it nginx -- bash", False),  # bash is unknown, asks
    ("kubectl exec -it nginx -c container -- sh", False),  # sh is unknown, asks
    ("kubectl run nginx --image=nginx", False),
    ("kubectl run nginx --image=nginx --restart=Never", False),
    ("kubectl run -it busybox --image=busybox -- sh", False),
    ("kubectl attach nginx -c container", False),
    ("kubectl debug nginx --image=busybox", False),
    ("kubectl debug nginx -it --image=ubuntu", False),
    ("kubectl cp /tmp/foo nginx:/tmp/bar", False),
    ("kubectl cp nginx:/tmp/foo /tmp/bar", False),
    ("kubectl port-forward pod/nginx 8080:80", False),
    ("kubectl port-forward svc/nginx 8080:80", False),
    ("kubectl proxy", False),
    ("kubectl proxy --port=8001", False),
    # kubectl - unsafe (rollout mutations)
    ("kubectl rollout restart deployment/nginx", False),
    ("kubectl rollout undo deployment/nginx", False),
    ("kubectl rollout undo deployment/nginx --to-revision=2", False),
    ("kubectl rollout pause deployment/nginx", False),
    ("kubectl rollout resume deployment/nginx", False),
    # kubectl - unsafe (node management)
    ("kubectl cordon node-1", False),
    ("kubectl uncordon node-1", False),
    ("kubectl drain node-1", False),
    ("kubectl drain node-1 --ignore-daemonsets", False),
    ("kubectl drain node-1 --delete-emptydir-data", False),
    ("kubectl taint nodes node-1 key=value:NoSchedule", False),
    ("kubectl taint nodes node-1 key:NoSchedule-", False),
    # kubectl - unsafe (config modifications)
    ("kubectl config use-context production", False),
    ("kubectl config use production", False),
    ("kubectl config set-context --current --namespace=test", False),
    ("kubectl config set-context production --cluster=prod-cluster", False),
    ("kubectl config set-cluster prod-cluster --server=https://k8s.example.com", False),
    ("kubectl config set-credentials user --token=token123", False),
    ("kubectl config delete-context production", False),
    ("kubectl config delete-cluster prod-cluster", False),
    ("kubectl config delete-user admin", False),
    ("kubectl config rename-context old-name new-name", False),
    # kubectl - unsafe (certificate management)
    ("kubectl certificate approve csr-name", False),
    ("kubectl certificate deny csr-name", False),
    # kubectl - unsafe (expose services)
    ("kubectl expose deployment nginx --port=80 --target-port=8080", False),
    ("kubectl expose pod nginx --port=80 --type=NodePort", False),
    #
    # kubectl exec - delegation to inner command
    #
    ("kubectl exec pod -- cat /etc/passwd", True),  # cat is safe
    ("kubectl exec -it pod -c container -- ls /app", True),  # ls is safe
    ("kubectl exec pod -- rm -rf /", False),  # rm is unsafe
    ("kubectl exec pod -- sh -c 'rm -rf /'", False),  # shell with rm is unsafe
    ("kubectl exec pod", False),  # no -- separator
    ("kubectl exec pod --", False),  # no command after --
    (
        "kubectl exec -n mynamespace pod -- pwd",
        True,
    ),  # namespace flag with safe command
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_kubectl(check, command: str, expected: bool) -> None:
    """Test command safety."""
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approved for: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirmation for: {command}"


class TestKubectlExecRemoteMode:
    """Test that kubectl exec delegates to inner command with remote mode semantics."""

    def test_command_rules_still_apply(self, check, tmp_path):
        """Command-based deny rules should still apply inside pods."""
        config = Config(rules=[Rule("deny", "rm -rf *")])
        # rm -rf inside pod should still be denied by command rule
        result = check("kubectl exec pod -- rm -rf /", config, tmp_path)
        assert not is_approved(result)  # deny rules return deny, not ask

    def test_redirect_rules_skipped_for_pod_paths(self, check, tmp_path):
        """Redirect rules should NOT apply to pod paths."""
        home = str(Path.home())
        config = Config(redirect_rules=[Rule("deny", f"{home}/.ssh/*")])
        # cat ~/.ssh/id_rsa inside pod - should be approved because
        # the path is pod-local, not host-local
        result = check("kubectl exec pod -- cat ~/.ssh/id_rsa", config, tmp_path)
        assert is_approved(result)

    def test_path_expansion_skipped_for_pod_paths(self, check, tmp_path):
        """Relative paths should not expand to host cwd."""
        config = Config(rules=[Rule("deny", f"cat {tmp_path}/*")])
        # cat ./foo inside pod - should be approved because ./foo
        # refers to pod's cwd, not host's tmp_path
        result = check("kubectl exec pod -- cat ./foo", config, tmp_path)
        assert is_approved(result)

    def test_absolute_path_rules_skipped_for_pod(self, check, tmp_path):
        """Absolute path rules should not apply to pod paths."""
        config = Config(redirect_rules=[Rule("deny", "/etc/passwd")])
        # Reading /etc/passwd in pod should be approved
        result = check("kubectl exec pod -- cat /etc/passwd", config, tmp_path)
        assert is_approved(result)
