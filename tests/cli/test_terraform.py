"""Test cases for terraform."""

import pytest

from conftest import is_approved, needs_confirmation

#
# ==========================================================================
# Terraform
# ==========================================================================
#
TESTS = [
    ("terraform plan", True),
    ("terraform plan -out=plan.tfplan", True),
    ("terraform plan -var 'name=value'", True),
    ("terraform plan -var-file=vars.tfvars", True),
    ("terraform plan -target=aws_instance.foo", True),
    ("terraform plan -destroy", True),
    ("terraform plan -refresh-only", True),
    ("terraform plan -json", True),
    ("terraform show", True),
    ("terraform show plan.tfplan", True),
    ("terraform show -json", True),
    ("terraform show -json plan.tfplan", True),
    ("terraform state list", True),
    ("terraform state list aws_instance.foo", True),
    ("terraform state show aws_instance.foo", True),
    ("terraform state show -json aws_instance.foo", True),
    ("terraform state pull", True),
    ("terraform validate", True),
    ("terraform validate -json", True),
    ("terraform validate -no-color", True),
    ("terraform fmt", True),
    ("terraform fmt -check", True),
    ("terraform fmt -diff", True),
    ("terraform fmt -recursive", True),
    ("terraform fmt -write=false", True),
    ("terraform fmt -list=false", True),
    ("terraform output", True),
    ("terraform output my_output", True),
    ("terraform output -json", True),
    ("terraform output -raw my_output", True),
    ("terraform output -state=terraform.tfstate", True),
    ("terraform providers", True),
    ("terraform providers lock", True),
    ("terraform providers mirror ./providers", True),
    ("terraform providers schema -json", True),
    ("terraform graph", True),
    ("terraform graph -type=plan", True),
    ("terraform graph -draw-cycles", True),
    ("terraform graph | dot -Tpng > graph.png", False),  # has output redirect
    ("terraform console", True),
    ("terraform console -var 'name=value'", True),
    ("terraform get", True),
    ("terraform get -update", True),
    ("terraform version", True),
    ("terraform version -json", True),
    ("terraform modules", True),
    ("terraform modules -json", True),
    ("terraform metadata functions", True),
    ("terraform metadata functions -json", True),
    ("terraform test", True),
    ("terraform test -filter=test_file.tftest.hcl", True),
    ("terraform test -json", True),
    ("terraform refresh", True),
    ("terraform refresh -target=aws_instance.foo", True),
    ("terraform --help", True),
    ("terraform -help", True),
    ("terraform plan --help", True),
    ("terraform --version", True),
    # terraform - safe (workspace list/show/select)
    ("terraform workspace list", True),
    ("terraform workspace show", True),
    ("terraform workspace select default", True),
    ("terraform workspace select -or-create dev", True),
    # terraform - unsafe (apply/destroy/init)
    ("terraform apply", False),
    ("terraform apply -auto-approve", False),
    ("terraform apply plan.tfplan", False),
    ("terraform apply -var 'name=value'", False),
    ("terraform apply -target=aws_instance.foo", False),
    ("terraform destroy", False),
    ("terraform destroy -auto-approve", False),
    ("terraform destroy -target=aws_instance.foo", False),
    ("terraform init", False),
    ("terraform init -upgrade", False),
    ("terraform init -reconfigure", False),
    ("terraform init -migrate-state", False),
    ("terraform init -backend=false", False),
    ("terraform import aws_instance.foo i-123", False),
    ("terraform import -var 'name=value' aws_instance.foo i-123", False),
    # terraform - unsafe (state mutations)
    ("terraform state mv aws_instance.foo aws_instance.bar", False),
    ("terraform state rm aws_instance.foo", False),
    ("terraform state push terraform.tfstate", False),
    ("terraform state replace-provider hashicorp/aws registry.example.com/aws", False),
    # terraform - unsafe (resource marking)
    ("terraform taint aws_instance.foo", False),
    ("terraform untaint aws_instance.foo", False),
    # terraform - unsafe (workspace create/delete)
    ("terraform workspace new dev", False),
    ("terraform workspace delete dev", False),
    # terraform - unsafe (lock management)
    ("terraform force-unlock 1234-5678", False),
    # terraform - unsafe (authentication)
    ("terraform login", False),
    ("terraform login app.terraform.io", False),
    ("terraform logout", False),
    ("terraform logout app.terraform.io", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_terraform(check, command: str, expected: bool) -> None:
    """Test command safety."""
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approved for: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirmation for: {command}"
