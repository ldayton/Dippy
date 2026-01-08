"""
Comprehensive tests for Azure CLI (az) handler.

Azure CLI has many services with consistent patterns:
- Safe: show, list, get, exists, download
- Unsafe: create, delete, update, start, stop, restart
"""

import pytest

from conftest import is_approved, needs_confirmation


TESTS = [
    # === SAFE: Version/help ===
    ("az version", True),
    ("az --version", True),
    ("az --help", True),
    ("az -h", True),
    ("az vm --help", True),
    ("az vm list --help", True),
    ("az find 'how to create vm'", True),
    #
    # === SAFE: Account (viewing) ===
    ("az account show", True),
    ("az account list", True),
    ("az account list --output table", True),
    ("az account list-locations", True),
    ("az account get-access-token", True),
    ("az account get-access-token --resource-type ms-graph", True),
    #
    # === UNSAFE: Account (modifying) ===
    ("az account set -s subscription_id", False),  # changes active subscription
    ("az account clear", False),
    #
    # === UNSAFE: Login/logout ===
    ("az login", False),
    ("az login --use-device-code", False),
    ("az login --service-principal", False),
    ("az logout", False),
    ("az configure", False),
    #
    # === SAFE: VM (viewing) ===
    ("az vm list", True),
    ("az vm list -g mygroup", True),
    ("az vm list --output table", True),
    ("az vm show -g mygroup -n myvm", True),
    ("az vm show --resource-group mygroup --name myvm", True),
    ("az vm list-sizes -l eastus", True),
    ("az vm list-skus -l eastus", True),
    ("az vm image list", True),
    ("az vm image list-offers -l eastus -p Canonical", True),
    ("az vm image list-publishers -l eastus", True),
    ("az vm image list-skus -l eastus -p Canonical -f UbuntuServer", True),
    ("az vm get-instance-view -g mygroup -n myvm", True),
    #
    # === UNSAFE: VM (lifecycle) ===
    ("az vm create -g mygroup -n myvm --image UbuntuLTS", False),
    ("az vm delete -g mygroup -n myvm", False),
    ("az vm start -g mygroup -n myvm", False),
    ("az vm stop -g mygroup -n myvm", False),
    ("az vm restart -g mygroup -n myvm", False),
    ("az vm deallocate -g mygroup -n myvm", False),
    ("az vm update -g mygroup -n myvm --set tags.env=prod", False),
    ("az vm run-command invoke -g mygroup -n myvm --command-id RunShellScript", False),
    #
    # === SAFE: Resource group (viewing) ===
    ("az group list", True),
    ("az group show -n mygroup", True),
    ("az group exists -n mygroup", True),
    #
    # === UNSAFE: Resource group (modifying) ===
    ("az group create -n mygroup -l eastus", False),
    ("az group delete -n mygroup", False),
    ("az group update -n mygroup --tags env=prod", False),
    #
    # === SAFE: AKS (viewing) ===
    ("az aks list", True),
    ("az aks list -g mygroup", True),
    ("az aks show -g mygroup -n mycluster", True),
    ("az aks get-upgrades -g mygroup -n mycluster", True),
    ("az aks get-versions -l eastus", True),
    #
    # === UNSAFE: AKS (modifying) ===
    ("az aks create -g mygroup -n mycluster", False),
    ("az aks delete -g mygroup -n mycluster", False),
    ("az aks update -g mygroup -n mycluster", False),
    ("az aks start -g mygroup -n mycluster", False),
    ("az aks stop -g mygroup -n mycluster", False),
    ("az aks get-credentials -g mygroup -n mycluster", False),  # modifies kubeconfig
    #
    # === SAFE: ACR (viewing) ===
    ("az acr list", True),
    ("az acr show -n myregistry", True),
    ("az acr repository list -n myregistry", True),
    ("az acr repository show -n myregistry --repository myimage", True),
    ("az acr repository show-tags -n myregistry --repository myimage", True),
    #
    # === UNSAFE: ACR (modifying) ===
    ("az acr create -n myregistry -g mygroup --sku Basic", False),
    ("az acr delete -n myregistry", False),
    ("az acr update -n myregistry --admin-enabled true", False),
    ("az acr login -n myregistry", False),
    ("az acr repository delete -n myregistry --repository myimage", False),
    #
    # === SAFE: Storage account (viewing) ===
    ("az storage account list", True),
    ("az storage account show -n mystorageaccount", True),
    ("az storage account show-connection-string -n mystorageaccount", True),
    #
    # === UNSAFE: Storage account (modifying) ===
    ("az storage account create -n mystorageaccount -g mygroup", False),
    ("az storage account delete -n mystorageaccount", False),
    ("az storage account update -n mystorageaccount --sku Standard_GRS", False),
    #
    # === SAFE: Storage blob (viewing/downloading) ===
    ("az storage blob list -c mycontainer --account-name mystorageaccount", True),
    ("az storage blob show -c mycontainer -n myblob --account-name mystorageaccount", True),
    ("az storage blob exists -c mycontainer -n myblob --account-name mystorageaccount", True),
    ("az storage blob download -c mycontainer -n myblob -f file.txt --account-name mystorageaccount", True),
    ("az storage blob download-batch -s mycontainer -d ./local --account-name mystorageaccount", True),
    ("az storage blob url -c mycontainer -n myblob --account-name mystorageaccount", True),
    #
    # === UNSAFE: Storage blob (modifying) ===
    ("az storage blob upload -c mycontainer -n myblob -f file.txt --account-name mystorageaccount", False),
    ("az storage blob delete -c mycontainer -n myblob --account-name mystorageaccount", False),
    ("az storage blob copy start --source-uri https://... -c mycontainer -b myblob", False),
    #
    # === SAFE: Storage container (viewing) ===
    ("az storage container list --account-name mystorageaccount", True),
    ("az storage container show -n mycontainer --account-name mystorageaccount", True),
    ("az storage container exists -n mycontainer --account-name mystorageaccount", True),
    #
    # === UNSAFE: Storage container (modifying) ===
    ("az storage container create -n mycontainer --account-name mystorageaccount", False),
    ("az storage container delete -n mycontainer --account-name mystorageaccount", False),
    #
    # === SAFE: Network (viewing) ===
    ("az network vnet list", True),
    ("az network vnet show -g mygroup -n myvnet", True),
    ("az network nsg list", True),
    ("az network nsg show -g mygroup -n mynsg", True),
    ("az network public-ip list", True),
    ("az network public-ip show -g mygroup -n myip", True),
    ("az network nic list", True),
    ("az network nic show -g mygroup -n mynic", True),
    #
    # === UNSAFE: Network (modifying) ===
    ("az network vnet create -g mygroup -n myvnet", False),
    ("az network vnet delete -g mygroup -n myvnet", False),
    ("az network nsg create -g mygroup -n mynsg", False),
    ("az network nsg delete -g mygroup -n mynsg", False),
    ("az network nsg rule create -g mygroup --nsg-name mynsg -n myrule", False),
    ("az network public-ip create -g mygroup -n myip", False),
    ("az network public-ip delete -g mygroup -n myip", False),
    #
    # === SAFE: App Service/Web App (viewing) ===
    ("az webapp list", True),
    ("az webapp show -g mygroup -n myapp", True),
    ("az webapp log tail -g mygroup -n myapp", True),
    ("az webapp log show -g mygroup -n myapp", True),
    #
    # === UNSAFE: App Service/Web App (modifying) ===
    ("az webapp create -g mygroup -n myapp -p myplan", False),
    ("az webapp delete -g mygroup -n myapp", False),
    ("az webapp start -g mygroup -n myapp", False),
    ("az webapp stop -g mygroup -n myapp", False),
    ("az webapp restart -g mygroup -n myapp", False),
    ("az webapp update -g mygroup -n myapp", False),
    ("az webapp deployment source config -g mygroup -n myapp --repo-url https://...", False),
    #
    # === SAFE: Container (viewing) ===
    ("az container list", True),
    ("az container show -g mygroup -n mycontainer", True),
    ("az container logs -g mygroup -n mycontainer", True),
    #
    # === UNSAFE: Container (modifying) ===
    ("az container create -g mygroup -n mycontainer --image nginx", False),
    ("az container delete -g mygroup -n mycontainer", False),
    ("az container start -g mygroup -n mycontainer", False),
    ("az container stop -g mygroup -n mycontainer", False),
    ("az container restart -g mygroup -n mycontainer", False),
    ("az container exec -g mygroup -n mycontainer --exec-command /bin/bash", False),
    #
    # === SAFE: Disk (viewing) ===
    ("az disk list", True),
    ("az disk show -g mygroup -n mydisk", True),
    #
    # === UNSAFE: Disk (modifying) ===
    ("az disk create -g mygroup -n mydisk --size-gb 100", False),
    ("az disk delete -g mygroup -n mydisk", False),
    ("az disk update -g mygroup -n mydisk --size-gb 200", False),
    #
    # === SAFE: Image (viewing) ===
    ("az image list", True),
    ("az image show -g mygroup -n myimage", True),
    #
    # === UNSAFE: Image (modifying) ===
    ("az image create -g mygroup -n myimage --source myvm", False),
    ("az image delete -g mygroup -n myimage", False),
    #
    # === SAFE: DevOps (viewing) ===
    ("az devops project list", True),
    ("az devops project show -p myproject", True),
    ("az devops configure --list", True),
    ("az repos list -p myproject", True),
    ("az repos show -r myrepo -p myproject", True),
    ("az pipelines list -p myproject", True),
    ("az pipelines show --id 123 -p myproject", True),
    ("az pipelines runs list --pipeline-id 123 -p myproject", True),
    #
    # === UNSAFE: DevOps (modifying) ===
    ("az devops configure", False),
    ("az devops project create --name myproject", False),
    ("az devops project delete --id project-id", False),
    ("az repos create --name myrepo -p myproject", False),
    ("az repos delete --id repo-id -p myproject", False),
    ("az pipelines create --name mypipeline -p myproject", False),
    ("az pipelines delete --id 123 -p myproject", False),
    ("az pipelines run --id 123 -p myproject", False),
    #
    # === SAFE: Redis (viewing) ===
    ("az redis list", True),
    ("az redis show -g mygroup -n myredis", True),
    ("az redis list-keys -g mygroup -n myredis", True),
    #
    # === UNSAFE: Redis (modifying) ===
    ("az redis create -g mygroup -n myredis -l eastus --sku Basic --vm-size c0", False),
    ("az redis delete -g mygroup -n myredis", False),
    ("az redis update -g mygroup -n myredis", False),
    #
    # === SAFE: Provider (viewing) ===
    ("az provider list", True),
    ("az provider show -n Microsoft.Compute", True),
    #
    # === UNSAFE: Provider (modifying) ===
    ("az provider register -n Microsoft.Compute", False),
    ("az provider unregister -n Microsoft.Compute", False),
    #
    # === SAFE: Lock (viewing) ===
    ("az lock list", True),
    ("az lock show -n mylock -g mygroup", True),
    #
    # === UNSAFE: Lock (modifying) ===
    ("az lock create -n mylock -g mygroup --lock-type CanNotDelete", False),
    ("az lock delete -n mylock -g mygroup", False),
    #
    # === SAFE: Tag (viewing) ===
    ("az tag list", True),
    ("az tag show -n mytag", True),
    #
    # === UNSAFE: Tag (modifying) ===
    ("az tag create -n mytag", False),
    ("az tag delete -n mytag", False),
    ("az tag add-value -n mytag --value myvalue", False),
    #
    # === SAFE: Advisor ===
    ("az advisor recommendation list", True),
    ("az advisor recommendation list -g mygroup", True),
    #
    # === SAFE: Config (viewing) ===
    ("az config get", True),
    #
    # === UNSAFE: Config (modifying) ===
    ("az config set defaults.group=mygroup", False),
    ("az config unset defaults.group", False),
    #
    # === UNSAFE: Upgrade ===
    ("az upgrade", False),
    #
    # === SAFE: Bicep (viewing) ===
    ("az bicep version", True),
    ("az bicep list-versions", True),
    #
    # === UNSAFE: Bicep (modifying) ===
    ("az bicep install", False),
    ("az bicep upgrade", False),
    ("az bicep build -f main.bicep", False),
    #
    # === SAFE: Cognitive Services (viewing) ===
    ("az cognitiveservices account list", True),
    ("az cognitiveservices account show -g mygroup -n myaccount", True),
    ("az cognitiveservices account list-skus -g mygroup -n myaccount", True),
    #
    # === UNSAFE: Cognitive Services (modifying) ===
    ("az cognitiveservices account create -g mygroup -n myaccount --kind TextAnalytics --sku S0 -l eastus", False),
    ("az cognitiveservices account delete -g mygroup -n myaccount", False),
    #
    # === SAFE: SSH Key (viewing) ===
    ("az sshkey list", True),
    ("az sshkey show -g mygroup -n mykey", True),
    #
    # === UNSAFE: SSH Key (modifying) ===
    ("az sshkey create -g mygroup -n mykey", False),
    ("az sshkey delete -g mygroup -n mykey", False),
    #
    # === SAFE: App Config (viewing) ===
    ("az appconfig list", True),
    ("az appconfig show -n myconfig", True),
    ("az appconfig kv list -n myconfig", True),
    #
    # === UNSAFE: App Config (modifying) ===
    ("az appconfig create -g mygroup -n myconfig -l eastus", False),
    ("az appconfig delete -n myconfig", False),
    ("az appconfig kv set -n myconfig --key mykey --value myvalue", False),
    ("az appconfig kv delete -n myconfig --key mykey", False),
    #
    # === SAFE: APIM (viewing) ===
    ("az apim list", True),
    ("az apim show -g mygroup -n myapim", True),
    #
    # === UNSAFE: APIM (modifying) ===
    ("az apim create -g mygroup -n myapim -l eastus --publisher-email admin@example.com --publisher-name MyCompany", False),
    ("az apim delete -g mygroup -n myapim", False),
    #
    # === SAFE: Logic App (viewing) ===
    ("az logicapp list", True),
    ("az logicapp show -g mygroup -n mylogicapp", True),
    #
    # === UNSAFE: Logic App (modifying) ===
    ("az logicapp create -g mygroup -n mylogicapp --storage-account mystorageaccount", False),
    ("az logicapp delete -g mygroup -n mylogicapp", False),
    ("az logicapp start -g mygroup -n mylogicapp", False),
    ("az logicapp stop -g mygroup -n mylogicapp", False),
    #
    # === SAFE: Quantum (viewing) ===
    ("az quantum workspace list", True),
    ("az quantum workspace show -g mygroup -n myworkspace", True),
    #
    # === UNSAFE: Quantum (modifying) ===
    ("az quantum workspace create -g mygroup -n myworkspace -l eastus", False),
    ("az quantum workspace delete -g mygroup -n myworkspace", False),
    #
    # === UNSAFE: Serial Console (interactive) ===
    ("az serial-console connect -g mygroup -n myvm", False),  # interactive console access
    #
    # === UNSAFE: Feedback (sends data) ===
    ("az feedback", False),  # sends data to Microsoft
    #
    # === SAFE: Storage table/queue/entity (viewing) ===
    ("az storage table list --account-name mystorageaccount", True),
    ("az storage queue list --account-name mystorageaccount", True),
    ("az storage entity query -t mytable --account-name mystorageaccount", True),
    #
    # === UNSAFE: Storage table/queue/entity (modifying) ===
    ("az storage table create -n mytable --account-name mystorageaccount", False),
    ("az storage table delete -n mytable --account-name mystorageaccount", False),
    ("az storage queue create -n myqueue --account-name mystorageaccount", False),
    ("az storage queue delete -n myqueue --account-name mystorageaccount", False),
    ("az storage entity insert -t mytable -e PartitionKey=pk RowKey=rk --account-name mystorageaccount", False),
    ("az storage entity delete -t mytable -e PartitionKey=pk RowKey=rk --account-name mystorageaccount", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool) -> None:
    """Test that command safety is detected correctly."""
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approved for: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirmation for: {command}"
