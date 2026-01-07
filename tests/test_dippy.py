"""Test cases for dippy."""

import sys
from pathlib import Path

from dippy.dippy import (
    parse_commands,
    is_command_safe,
    get_command_description,
    get_unsafe_commands,
    _load_custom_configs,
)

# Load custom configs (normally done in main(), but tests call functions directly)
_load_custom_configs()

# (command, expected_approved_by_hook)
TESTS = [
    # CLI tools - safe
    ("aws help", True),
    ("aws s3 help", True),
    ("aws ec2 help", True),
    ("aws s3 ls", True),
    ("aws ec2 describe-instances", True),
    ("aws --profile prod ec2 describe-instances", True),
    ("aws --region us-east-1 ec2 describe-instances", True),
    ("aws --output json s3 ls", True),
    ("aws --profile prod --region us-west-2 lambda list-functions", True),
    ("aws --endpoint-url http://localhost:4566 s3 ls", True),
    ("aws --no-cli-pager ec2 describe-instances", True),
    ("aws logs filter-log-events --log-group-name test", True),
    ("aws cloudtrail lookup-events", True),
    ("aws dynamodb batch-get-item --request-items file://items.json", True),
    ("aws dynamodb query --table-name mytable", True),
    ("aws dynamodb scan --table-name mytable", True),
    ("aws dynamodb transact-get-items --transact-items file://items.json", True),
    ("aws cloudformation validate-template --template-body file://t.yaml", True),
    ("git status", True),
    ("git log", True),
    ("kubectl get pods", True),
    ("gh pr list", True),
    ("gh pr view 123 --repo foo/bar", True),
    ("gh --repo foo/bar pr list", True),
    ("gh -R foo/bar pr view 123", True),
    ("docker ps", True),
    ("docker --host tcp://localhost:2375 ps", True),
    ("docker -H unix:///var/run/docker.sock images", True),
    ("brew list", True),
    # CLI tools - unsafe (should defer)
    ("aws s3 rm s3://bucket/key", False),
    ("aws ec2 terminate-instances --instance-ids i-123", False),
    ("aws --profile prod ec2 terminate-instances --instance-ids i-123", False),
    ("aws --region us-east-1 s3 rm s3://bucket/file", False),
    ("git push", False),
    ("git commit -m 'message'", False),
    ("git commit -m 'multiline\n\nmessage'", False),
    ('git commit -m "line1\n\nline2: 110 → 45"', False),
    # Heredoc commit messages (bashlex can't parse, but pattern-matched as safe)
    ("git commit -m \"$(cat <<'EOF'\nmessage\nEOF\n)\"", False),  # commit is unsafe
    ("git -C /path commit -m \"$(cat <<'EOF'\nmessage\nEOF\n)\"", False),
    ("git branch -D feature", False),
    ("git stash drop", False),
    ("git config --unset user.name", False),
    ("git tag -d v1.0", False),
    ("kubectl delete pod foo", False),
    ("gh pr create", False),
    ("gh -R foo/bar pr create", False),
    ("docker run ubuntu", False),
    ("docker --host tcp://localhost run ubuntu", False),
    ("brew install foo", False),
    # Custom checks
    ("find . -name '*.py'", True),
    ("find . -exec rm {} \\;", False),
    ("find . -delete", False),
    ("sort file.txt", True),
    ("sort -o output.txt file.txt", False),
    ("sed 's/foo/bar/' file.txt", True),
    ("sed -n '1,10p' file.txt", True),
    ("sed -i 's/foo/bar/' file.txt", False),
    ("sed -i.bak 's/foo/bar/' file.txt", False),
    ("sed --in-place 's/foo/bar/' file.txt", False),
    ("awk '{print $1}' file.txt", True),
    ("awk -F: '{print $1}' /etc/passwd", True),
    ("awk -f script.awk file.txt", False),
    ("awk '{print > \"out.txt\"}' file.txt", False),
    ("awk '{system(\"rm file\")}'", False),
    # Curl - safe (GET/HEAD only)
    ("curl https://example.com", True),
    ("curl -I https://example.com", True),
    ("curl --head https://example.com", True),
    ("curl -X GET https://example.com", True),
    ("curl -X HEAD https://example.com", True),
    ("curl -X OPTIONS https://example.com", True),
    ("curl -X TRACE https://example.com", True),
    ("curl -s -o /dev/null -w '%{http_code}' https://example.com", True),
    # Curl - unsafe (POST/PUT/DELETE or data-sending)
    ("curl -X POST https://example.com", False),
    ("curl -X PUT https://example.com", False),
    ("curl -X DELETE https://example.com", False),
    ("curl --request=DELETE https://example.com", False),
    ("curl -d 'data' https://example.com", False),
    ("curl --data='foo=bar' https://example.com", False),
    ("curl -F 'file=@test.txt' https://example.com", False),
    ("curl --form 'file=@test.txt' https://example.com", False),
    ("curl -T file.txt ftp://example.com", False),
    ("curl --upload-file file.txt ftp://example.com", False),
    # Curl wrappers (from tests/dippy-test.toml)
    ("curl-wrapper.sh query foo", True),
    ("/path/to/curl-wrapper.sh get metrics", True),
    ("curl-wrapper.sh --help", True),
    ("curl-wrapper.sh -X POST data", False),
    ("curl-wrapper.sh -d 'data' https://example.com", False),
    ("curl-wrapper.sh --data=foo", False),
    # Chained commands - should check ALL commands
    ("aws s3 ls && aws s3 ls", True),  # both safe
    ("aws s3 ls && aws s3 rm foo", False),  # second unsafe
    ("aws s3 rm foo && aws s3 ls", False),  # first unsafe
    ("git status || git push", False),  # second unsafe
    # Pipes - should check ALL commands
    ("git log | grep foo", True),  # both safe (grep handled separately?)
    ("docker ps | grep foo", True),
    # Wrappers - should unwrap and check inner command
    ("time git status", True),
    ("time aws s3 ls", True),
    ("time aws s3 rm foo", False),
    ("nice git log", True),
    ("nice -n 10 git status", True),
    ("timeout 5 kubectl get pods", True),
    # Nested wrappers
    ("time nice git status", True),
    # uv run wrapper
    ("uv run cdk synth", True),
    ("uv run cdk synth --quiet", True),
    ("uv run --quiet cdk diff", True),
    ("uv run cdk deploy", False),
    ("uv run rm foo", False),
    ("uv sync", True),
    ("uv sync --all-groups", True),
    ("uv lock", True),
    ("uv add foo", False),
    ("uv remove foo", False),
    ("uv pip install foo", False),
    ("uv version", True),
    ("uv tree", True),
    ("uv pip list", True),
    ("uv pip show foo", True),
    ("uv run ruff check --fix && uv run ruff format", True),
    ("uv run --project tools-base-mcp ruff check", True),
    ("uv run --project tools-base-mcp ruff format", True),
    ("uv run --group cdk cdk synth", True),
    ("uv run --group cdk cdk deploy", False),
    ("uv run pytest", True),
    ("uv run pytest -v tests/", True),
    ("pytest", True),
    ("pytest -xvs tests/test_foo.py", True),
    ("uv run ruff check", True),
    ("uv run ruff format", True),
    ("ruff check --fix", True),
    ("ruff format .", True),
    ("ruff clean", False),  # not in safe actions
    # Complex chains with wrappers
    ("time git status && git log", True),
    ("time git status && git push", False),
    # Simple commands (now handled by hook too)
    ("ls", True),
    ("ls -la", True),
    ("grep foo bar.txt", True),
    ("cat file.txt", True),
    # Scripts with paths (basename matching, from tests/dippy-test.toml)
    ("./safe-test-script.sh", True),
    ("/path/to/safe-test-script.sh", True),
    ("./unknown-script.py", False),
    # Python running dippy (allow dippy to run itself) - tested separately
    ("python malicious.py", False),
    ("python script.py", False),
    ("python /tmp/fake/dippy.py", False),
    # Simple commands chained
    ("ls && cat foo", True),
    ("ls && rm foo", False),
    # Output redirects - should defer (write to files)
    ("ls > file.txt", False),
    ("cat foo >> bar.txt", False),
    ("ls 2> err.txt", False),
    ("cmd &> all.txt", False),
    ("git log > changes.txt", False),
    # Safe redirects to /dev/null
    ("grep foo bar 2>/dev/null", True),
    ("ls 2>/dev/null", True),
    ("ls &>/dev/null", True),
    ("grep -r pattern /dir 2>/dev/null | head -10", True),
    # fd redirects (2>&1 style) - safe
    ("ls 2>&1", True),
    ("uv run cdk synth 2>&1 | head -10", True),
    # Input redirects - safe (read only)
    ("cat < input.txt", True),
    ("grep foo < file.txt", True),
    # Mixed chains with redirects
    ("ls && cat foo > out.txt", False),
    ("cat < in.txt && ls", True),
    # Variable assignment prefix
    ("FOO=BAR ls -l", True),
    ("FOO=BAR rm file", False),
    # Prefix commands
    ("git config --get user.name", True),
    ("git config --list", True),
    ("git stash list", True),
    ("node --version", True),
    ("python --version", True),
    ("pre-commit run", True),
    ("pre-commit run --all-files", True),
    # Prefix commands - unsafe variants
    ("git config user.name foo", False),
    ("git config --unset user.name", False),
    ("git stash pop", False),
    ("git stash drop", False),
    ("node script.js", False),
    ("python script.py", False),
    # Prefix commands in pipelines
    ("git config --get user.name | cat", True),
    ("node --version && ls", True),
    ("python --version | grep 3", True),
    # Prefix commands - partial token matches should NOT match
    ("python --version-info", False),
    ("pre-commit-hook", False),
    # --help makes any command safe
    ("gh api --help", True),
    ("gh api repos --help", True),
    ("aws s3 rm --help", True),
    ("kubectl delete --help", True),
    ("docker run --help", True),
    ("git push --help", True),
    ("unknown-command --help", True),
    ("./mystery-script.sh --help", True),
    # gh api - safe (GET requests)
    ("gh api repos/owner/repo", True),
    ("gh api repos/{owner}/{repo}/pulls", True),
    ("gh api /user", True),
    ("gh api -X GET repos/owner/repo", True),
    ("gh api --method GET repos/owner/repo", True),
    ("gh api --method=GET repos/owner/repo", True),
    ("gh api -XGET repos/owner/repo", True),
    (
        "gh api -X GET search/issues -f q='repo:cli/cli'",
        True,
    ),  # -f ok with explicit GET
    (
        "gh api -f q='repo:cli/cli' -X GET search/issues",
        True,
    ),  # -X GET after -f is still safe
    ("gh api --paginate repos/owner/repo/issues", True),
    ("gh api -q '.[] | .name' repos/owner/repo", True),
    # gh api - unsafe (mutations)
    ("gh api repos/owner/repo --raw-field=foo=bar", False),  # --flag=value form
    ("gh api repos/owner/repo --field=foo=bar", False),
    ("gh api repos/owner/repo/issues -f title='bug'", False),  # -f implies POST
    ("gh api repos/owner/repo/issues -F body=@file.txt", False),  # -F implies POST
    ("gh api repos/owner/repo/issues --field title=bug", False),
    ("gh api -X POST repos/owner/repo/issues", False),
    ("gh api -X DELETE repos/owner/repo/issues/1", False),
    ("gh api --method POST repos/owner/repo/hooks", False),
    ("gh api --method=PATCH repos/owner/repo", False),
    ("gh api -XPOST repos/owner/repo/issues", False),
    ("gh api repos/owner/repo --input payload.json", False),
    ("gh api graphql -f query='mutation { ... }'", False),
    # Git with -C flag
    ("git -C /some/path status", True),
    ("git -C /some/path log --oneline -5", True),
    ("git -C /tmp push --force", False),
    ("git --git-dir=/some/.git status", True),
    ("git -c core.editor=vim log", True),
    # Gcloud with global flags (values could match action names)
    ("gcloud --project delete compute instances list", True),
    ("gcloud --format delete compute instances list", True),
    ("gcloud --project myproj compute instances delete foo", False),
    # Gcloud with --flag value patterns
    ("gcloud compute instances list", True),
    ("gcloud compute instances list --project foo", True),
    ("gcloud compute backend-services describe k8s-be --global --project foo", True),
    ("gcloud iap settings get --project foo --resource-type=compute", True),
    ("gcloud auth list", True),
    ("gcloud compute instances delete foo", False),
    ("gcloud compute instances delete list", False),  # deleting instance named "list"
    ("gcloud compute instances create foo", False),
    ("gcloud container clusters get-credentials foo", True),  # get- prefix
    # Gcloud nested services (variable depth)
    ("gcloud run services list", True),
    ("gcloud run services describe myservice --region us-central1", True),
    ("gcloud run services update myservice --region us-central1", False),
    ("gcloud run services delete myservice", False),
    ("gcloud compute backend-services list --project foo", True),
    ("gcloud compute ssl-certificates describe mycert --global", True),
    ("gcloud iap web get-iam-policy --resource-type=backend-services", True),
    ("gcloud artifacts docker images list us-central1-docker.pkg.dev/proj/repo", True),
    ("gcloud iam service-accounts list", True),
    ("gcloud iam service-accounts delete sa@proj.iam.gserviceaccount.com", False),
    ("gcloud secrets list --project foo", True),
    ("gcloud secrets describe mysecret", True),
    ("gcloud secrets create newsecret", False),
    ("gcloud dns record-sets list --zone myzone", True),
    ("gcloud functions list --project foo", True),
    ("gcloud config get-value project", True),
    ("gcloud config set project foo", False),
    ("gcloud logging read 'resource.type=cloud_run_revision'", True),
    ("gcloud storage buckets describe gs://mybucket", True),
    ("gcloud beta run services describe myservice", True),
    ("gcloud beta run services update myservice", False),
    ("gcloud certificate-manager trust-configs describe myconfig", True),
    ("gcloud network-security server-tls-policies describe mypolicy", True),
    ("gcloud container images list-tags gcr.io/proj/image", True),
    ("gcloud projects list", True),
    ("gcloud projects describe myproject", True),
    ("gcloud projects get-iam-policy myproject", True),
    ("gcloud projects add-iam-policy-binding myproject --member=user:foo", False),
    # Az with global flags (values could match action names)
    ("az --subscription delete vm list", True),
    ("az --query delete vm show", True),
    ("az -o delete vm list", True),
    ("az --subscription mysub vm delete foo", False),
    # Az with positional args before flags
    ("az vm list --resource-group mygroup", True),
    ("az vm show myvm --resource-group mygroup", True),
    ("az storage account list", True),
    ("az keyvault secret show --name mysecret --vault-name myvault", True),
    ("az vm delete myvm --resource-group mygroup", False),
    ("az vm delete list", False),  # deleting vm named "list"
    ("az vm create myvm --resource-group mygroup", False),
    ("az vm start myvm", False),
    # Az nested services (variable depth)
    ("az boards work-item show --id 12345", True),
    ("az boards work-item list --project myproj", True),
    ("az boards work-item create --type Bug", False),
    ("az boards work-item update --id 12345", False),
    ("az boards query --wiql 'SELECT [System.Id] FROM WorkItems'", True),
    ("az boards iteration team list --team MyTeam", True),
    ("az deployment group show --resource-group rg --name main", True),
    ("az deployment group list --resource-group rg", True),
    ("az deployment group create --resource-group rg --template-file t.bicep", False),
    ("az deployment operation group list --resource-group rg --name main", True),
    ("az devops team list --project myproj", True),
    ("az devops team list-member --team MyTeam", True),
    ("az cognitiveservices model list --location eastus", True),
    ("az cognitiveservices account list", True),
    ("az cognitiveservices account show --name myaccount --resource-group rg", True),
    (
        "az cognitiveservices account deployment list --name myaccount --resource-group rg",
        True,
    ),
    (
        "az cognitiveservices account deployment show --name myaccount --resource-group rg --deployment-name dep",
        True,
    ),
    (
        "az cognitiveservices account deployment create --name myaccount --resource-group rg",
        False,
    ),
    (
        "az cognitiveservices account deployment delete --name myaccount --resource-group rg",
        False,
    ),
    ("az cognitiveservices account create --name foo", False),
    ("az containerapp show --name myapp --resource-group rg", True),
    ("az containerapp list --resource-group rg", True),
    ("az containerapp revision list --name myapp --resource-group rg", True),
    ("az containerapp logs show --name myapp --resource-group rg --type console", True),
    ("az containerapp delete --name myapp --resource-group rg", False),
    ("az acr repository list --name myacr", True),
    ("az acr repository show-tags --name myacr --repository myrepo", True),
    ("az acr repository delete --name myacr --repository myrepo", False),
    ("az monitor log-analytics query --workspace ws --analytics-query q", True),
    ("az monitor activity-log list", True),
    ("az resource list --resource-group rg", True),
    ("az resource show --ids /subscriptions/.../resource", True),
    ("az resource delete --ids /subscriptions/.../resource", False),
    # Az role (RBAC)
    ("az role assignment list", True),
    ("az role assignment list --assignee user@example.com", True),
    ("az role definition list", True),
    ("az role assignment create --assignee user@example.com --role Reader", False),
    ("az role assignment delete --assignee user@example.com --role Reader", False),
    # Az ML (Machine Learning)
    ("az ml workspace list", True),
    ("az ml workspace show --name myws --resource-group rg", True),
    ("az ml model list --workspace-name myws --resource-group rg", True),
    ("az ml endpoint list --workspace-name myws --resource-group rg", True),
    ("az ml workspace create --name myws --resource-group rg", False),
    ("az ml workspace delete --name myws --resource-group rg", False),
    ("az ml model delete --name mymodel --workspace-name myws", False),
    # Kubectl with global flags (values could match action names)
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
    # Terraform
    ("terraform plan", True),
    ("terraform plan -out=plan.tfplan", True),
    ("terraform show", True),
    ("terraform state list", True),
    ("terraform validate", True),
    ("terraform fmt -check", True),
    ("terraform output", True),
    ("terraform apply", False),
    ("terraform destroy", False),
    ("terraform init", False),
    ("terraform import aws_instance.foo i-123", False),
    # tar - safe (list only)
    ("tar -tf archive.tar", True),
    ("tar -tvf archive.tar.gz", True),
    ("tar --list -f archive.tar", True),
    ("tar -ztf archive.tar.gz", True),
    ("tar tf archive.tar", True),
    ("tar -t -f archive.tar", True),
    # tar - unsafe (create/extract)
    ("tar -cf archive.tar file.txt", False),
    ("tar -czf archive.tar.gz dir/", False),
    ("tar -xf archive.tar", False),
    ("tar -xvf archive.tar.gz", False),
    ("tar --extract -f archive.tar", False),
    ("tar -rf archive.tar newfile.txt", False),
    ("tar xf archive.tar", False),
    # unzip - safe (list only)
    ("unzip -l archive.zip", True),
    ("unzip -lv archive.zip", True),
    ("unzip -lq archive.zip", True),
    # unzip - unsafe (extract)
    ("unzip archive.zip", False),
    ("unzip archive.zip -d outdir", False),
    ("unzip -o archive.zip", False),
    ("unzip -x archive.zip", False),
    # 7z - safe (list only)
    ("7z l archive.7z", True),
    ("7z l -slt archive.7z", True),
    # 7z - unsafe (add/extract)
    ("7z a archive.7z file.txt", False),
    ("7z x archive.7z", False),
    ("7z e archive.7z", False),
    ("7z d archive.7z file.txt", False),
    # npm - safe (read-only)
    ("npm list", True),
    ("npm ls", True),
    ("npm ls --depth=0", True),
    ("npm view lodash", True),
    ("npm view lodash version", True),
    ("npm show express", True),
    ("npm outdated", True),
    ("npm audit", True),
    ("npm search lodash", True),
    ("npm explain lodash", True),
    ("npm fund", True),
    ("npm doctor", True),
    ("npm why lodash", True),
    ("npm help install", True),
    # npm - unsafe (mutations)
    ("npm install", False),
    ("npm install lodash", False),
    ("npm i lodash", False),
    ("npm uninstall lodash", False),
    ("npm update", False),
    ("npm publish", False),
    ("npm run build", False),
    ("npm init", False),
    ("npm link", False),
    # pip - safe (read-only)
    ("pip list", True),
    ("pip show requests", True),
    ("pip freeze", True),
    ("pip check", True),
    ("pip index versions requests", True),
    ("pip help install", True),
    # pip - unsafe (mutations)
    ("pip install requests", False),
    ("pip install -r requirements.txt", False),
    ("pip uninstall requests", False),
    ("pip download requests", False),
    # yarn - safe (read-only)
    ("yarn list", True),
    ("yarn info lodash", True),
    ("yarn why lodash", True),
    ("yarn audit", True),
    ("yarn outdated", True),
    ("yarn licenses list", True),
    ("yarn help", True),
    # yarn - unsafe (mutations)
    ("yarn add lodash", False),
    ("yarn remove lodash", False),
    ("yarn install", False),
    ("yarn upgrade", False),
    ("yarn run build", False),
    # pnpm - safe (read-only)
    ("pnpm list", True),
    ("pnpm ls", True),
    ("pnpm why lodash", True),
    ("pnpm audit", True),
    ("pnpm outdated", True),
    ("pnpm licenses list", True),
    # pnpm - unsafe (mutations)
    ("pnpm add lodash", False),
    ("pnpm remove lodash", False),
    ("pnpm install", False),
    ("pnpm update", False),
    ("pnpm run build", False),
    # Openssl x509 with -noout (read-only)
    ("openssl x509 -noout -text", True),
    ("openssl x509 -noout -text -in cert.pem", True),
    ("openssl x509 -noout -subject -issuer", True),
    ("openssl x509 -text", False),  # no -noout, could write encoded output
    ("openssl x509 -in cert.pem -out cert.der", False),
    ("openssl req -new -key key.pem", False),
    # Network diagnostic tools with checks
    ("ip addr", True),
    ("ip addr show", True),
    ("ip route", True),
    ("ip link show", True),
    ("ip -4 addr show", True),
    ("ip addr add 192.168.1.1/24 dev eth0", False),
    ("ip link set eth0 up", False),
    ("ip route del default", False),
    ("ip netns exec myns ip addr", False),  # runs commands in namespace
    ("ifconfig", True),
    ("ifconfig eth0", True),
    ("ifconfig eth0 up", False),
    ("ifconfig eth0 down", False),
    ("ifconfig eth0 192.168.1.1", True),  # viewing, not setting without netmask
    ("ifconfig eth0 192.168.1.1 netmask 255.255.255.0", False),
    ("journalctl", True),
    ("journalctl -f", True),
    ("journalctl -u sshd", True),
    ("journalctl --rotate", False),
    ("journalctl --vacuum-time=1d", False),
    ("journalctl --flush", False),
    ("dmesg", True),
    ("dmesg -T", True),
    ("dmesg -c", False),
    ("dmesg --clear", False),
    ("ping google.com", True),
    ("ping -c 4 google.com", True),
    # Auth0 CLI - safe (read-only actions)
    ("auth0 apps list", True),
    ("auth0 apps show app123", True),
    ("auth0 users search", True),
    ("auth0 users search-by-email", True),
    ("auth0 users show user123", True),
    ("auth0 logs list", True),
    ("auth0 logs tail", True),
    ("auth0 actions list", True),
    ("auth0 actions show action123", True),
    ("auth0 actions diff", True),
    ("auth0 roles list", True),
    ("auth0 orgs list", True),
    ("auth0 apis list", True),
    ("auth0 domains list", True),
    ("auth0 tenants list", True),
    ("auth0 event-streams stats", True),
    ("auth0 --tenant foo.auth0.com apps list", True),
    ("auth0 --tenant foo.auth0.com users show user123", True),
    # Auth0 CLI - unsafe (mutations)
    ("auth0 apps create", False),
    ("auth0 apps update app123", False),
    ("auth0 apps delete app123", False),
    ("auth0 users create", False),
    ("auth0 users update user123", False),
    ("auth0 users delete user123", False),
    ("auth0 actions deploy", False),
    ("auth0 roles create", False),
    ("auth0 orgs create", False),
    ("auth0 --tenant foo.auth0.com apps create", False),
    # Auth0 api - safe (GET requests)
    ("auth0 api tenants/settings", True),
    ("auth0 api get tenants/settings", True),
    ("auth0 api get clients", True),
    ("auth0 api users", True),
    # Auth0 api - unsafe (mutations)
    ("auth0 api post clients", False),
    ("auth0 api put clients/123", False),
    ("auth0 api patch clients/123", False),
    ("auth0 api delete clients/123", False),
    ("auth0 api clients -d '{}'", False),
    ("auth0 api clients --data '{}'", False),
    # Shell -c wrappers - safe inner commands
    ("bash -c 'echo hello'", True),
    ("bash -c 'ls -la'", True),
    ("bash -c 'git status'", True),
    ("bash -c 'echo foo && ls'", True),
    ("sh -c 'cat file.txt'", True),
    ("sh -c 'grep pattern file'", True),
    ("zsh -c 'pwd'", True),
    ("zsh -c 'git log --oneline'", True),
    ('bash -c "echo hello"', True),
    ('bash -c "aws s3 ls"', True),
    # Shell -c wrappers - unsafe inner commands
    ("bash -c 'rm -rf /'", False),
    ("bash -c 'git push'", False),
    ("bash -c 'echo foo && rm bar'", False),
    ("sh -c 'aws s3 rm s3://bucket/key'", False),
    ("zsh -c 'kubectl delete pod foo'", False),
    ('bash -c "rm file"', False),
    # Shell -c edge cases
    ("bash -c", False),  # missing command
    ("bash -x -c 'echo'", True),  # other flags before -c
    ("bash script.sh", False),  # no -c flag, not safe
    # Shell combined flags (-lc, -xc, -cl, etc.)
    ("bash -lc 'echo hello'", True),
    ("bash -xc 'git status'", True),
    ("bash -ilc 'ls -la'", True),
    ("zsh -ilc 'pwd'", True),
    ("sh -lc 'cat file'", True),
    ("bash -lc 'rm foo'", False),
    ("bash -xc 'git push'", False),
    ("bash -cl 'echo hello'", True),  # -c not at end
    ("bash -cxl 'ls'", True),  # -c at start
    ("sh -cl 'git status'", True),
    ("bash -cl 'rm foo'", False),
    # xargs - safe (inner command is safe)
    ("xargs ls", True),
    ("xargs cat", True),
    ("xargs grep pattern", True),
    ("xargs rg -l pattern", True),
    ("find . -name '*.py' | xargs grep TODO", True),
    ("fd -t f | xargs head -5", True),
    ("xargs -0 cat", True),
    ("xargs -I {} cat {}", True),
    ("xargs -n 1 ls", True),
    ("xargs -P 4 grep pattern", True),
    ("xargs --null rg pattern", True),
    ("xargs -d '\\n' cat", True),
    ("xargs --delimiter='\\n' cat", True),
    ("xargs -I {} -P 4 head -10 {}", True),
    ("ls | xargs -I {} stat {}", True),
    ("xargs -- cat", True),  # -- ends flag parsing
    ("xargs -0 -- rg pattern", True),
    # xargs - unsafe (inner command is unsafe)
    ("xargs rm", False),
    ("xargs rm -rf", False),
    ("find . | xargs rm", False),
    ("xargs -0 rm", False),
    ("xargs -I {} rm {}", False),
    ("xargs -n 1 rm", False),
    ("xargs mv", False),
    ("xargs cp", False),
    ("xargs chmod 777", False),
    ("xargs -- rm", False),
    # xargs - no command (defer)
    ("xargs", False),
    ("xargs -0", False),
    ("xargs -I {}", False),
    # xargs with shell -c (delegates to check_shell_c)
    ("xargs -I {} sh -c 'echo {}'", True),
    ("xargs -I {} bash -c 'cat {}'", True),
    ("xargs -I {} sh -c 'rm {}'", False),
    ("xargs -I {} bash -c 'echo {} && rm {}'", False),
    # Safe patterns (from tests/dippy-test.toml)
    (f"{Path.home()}/test-tools/foo/bin/run.sh", True),
    (f"{Path.home()}/test-tools/bar/bin/run.sh --test", True),
    (f"{Path.home()}/test-tools/baz/bin/run.sh --prod", True),
    ("/other/path/run.sh", False),
    (f"{Path.home()}/test-tools/foo/run.sh", False),  # not in bin/
    # === Regression tests for refactor 1: flag skipping ===
    # AWS global flags before service
    ("aws --no-cli-pager --output json s3 ls", True),
    ("aws --cli-connect-timeout 30 --ca-bundle /path ec2 describe-instances", True),
    # env wrapper with mixed flags and VAR=val
    ("env -i FOO=bar BAR=baz ls", True),
    ("env --ignore-environment PATH=/bin ls", True),
    ("env -u HOME -- git status", True),
    # uv run with multiple flags consuming args
    ("uv run --python 3.12 --with requests --group dev pytest", True),
    ("uv run --no-project --python 3.11 ruff check", True),
    # === Regression tests for refactor 2: token rejection ===
    # sed prefix matching
    ("sed -i'' 's/foo/bar/' file.txt", False),
    ("sed -i.backup 's/foo/bar/' file.txt", False),
    ("sed --in-place=.bak 's/foo/bar/' file.txt", False),
    # sort prefix matching
    ("sort -ooutput.txt file.txt", False),
    # journalctl prefix matching
    ("journalctl --vacuum-size=100M", False),
    ("journalctl --vacuum-files=10", False),
    # find exact matching (not prefix)
    ("find . -executable", True),
    ("find . -name '*exec*'", True),
    # === Regression tests for refactor 3: inner command extraction ===
    # xargs with -- separator
    ("xargs -0 -I {} -- cat {}", True),
    ("xargs -P 4 -n 1 -- grep pattern", True),
    # shell -c with flags that take args
    ("bash -o pipefail -c 'git log'", True),
    ("bash -o pipefail -c 'rm foo'", False),
    # shell with combined flags containing -c
    ("bash -exc 'git status'", True),
    ("bash -xec 'git log | head'", True),
    ("sh -lc 'aws s3 ls'", True),
    # xargs with flags consuming args
    ("xargs -E EOF cat", True),
    ("xargs -L 5 -I LINE head LINE", True),
    ("xargs -d '\\n' wc -l", True),
]


DESCRIPTION_TESTS = [
    # AWS
    (
        ["aws", "cloudformation", "delete-stack", "--stack-name", "foo"],
        "aws cloudformation delete-stack",
    ),
    (["aws", "--profile", "prod", "s3", "rm", "s3://bucket"], "aws s3 rm"),
    (["aws", "s3", "rm"], "aws s3 rm"),
    (
        [
            "aws",
            "--profile",
            "prod",
            "--region",
            "us-east-1",
            "ec2",
            "terminate-instances",
        ],
        "aws ec2 terminate-instances",
    ),
    (["aws"], "aws"),  # incomplete
    (["aws", "help"], "aws help"),  # help is service, no action
    (["aws", "--profile", "prod"], "aws"),  # only flags, no service/action
    # Az (variable_depth)
    (["az", "vm", "delete", "myvm"], "az vm delete"),
    (["az", "boards", "work-item", "create"], "az boards work-item create"),
    (
        ["az", "cognitiveservices", "account", "deployment", "create"],
        "az cognitiveservices account deployment create",
    ),
    (["az", "--subscription", "mysub", "vm", "delete", "foo"], "az vm delete"),
    (["az"], "az"),  # incomplete
    # Gcloud (variable_depth)
    (
        ["gcloud", "compute", "instances", "delete", "foo"],
        "gcloud compute instances delete",
    ),
    (
        ["gcloud", "run", "services", "update", "myservice"],
        "gcloud run services update",
    ),
    (
        ["gcloud", "--project", "myproj", "compute", "instances", "create", "foo"],
        "gcloud compute instances create",
    ),
    # Kubectl (first_token)
    (["kubectl", "delete", "pod", "foo"], "kubectl delete"),
    (["kubectl", "--context", "mycluster", "delete", "pod", "foo"], "kubectl delete"),
    (["kubeat", "delete", "pod", "foo"], "kubectl delete"),  # alias
    (["kubeci", "apply", "-f", "foo.yaml"], "kubectl apply"),  # alias
    # Gh (second_token)
    (["gh", "pr", "create"], "gh pr create"),
    (["gh", "issue", "list"], "gh issue list"),
    (["gh", "-R", "foo/bar", "pr", "create"], "gh pr create"),
    (["gh", "pr"], "gh"),  # missing action - fallback to cmd
    # Git (first_token)
    (["git", "push"], "git push"),
    (["git", "-C", "/path", "push", "--force"], "git push"),
    (["git", "status"], "git status"),
    # Auth0 (second_token)
    (["auth0", "apps", "create"], "auth0 apps create"),
    (["auth0", "--tenant", "foo", "users", "delete"], "auth0 users delete"),
    # Docker (first_token)
    (["docker", "run", "ubuntu"], "docker run"),
    (["docker", "--host", "tcp://localhost", "run", "ubuntu"], "docker run"),
    # Uv
    (["uv", "sync"], "uv sync"),
    (["uv", "pip", "install", "foo"], "uv pip install"),
    # Simple commands (no CLI config)
    (["rm", "foo"], "rm"),
    (["cp", "a", "b"], "cp"),
    # Wrappers
    (["time", "aws", "s3", "rm", "foo"], "aws s3 rm"),
    (["uv", "run", "aws", "s3", "rm", "foo"], "aws s3 rm"),
    (["time", "rm", "foo"], "rm"),
    # Edge cases
    ([], "empty command"),
    (["time"], "empty command"),  # wrapper with nothing after
]


import pytest


@pytest.mark.parametrize("cmd,expected_safe", TESTS)
def test_command(cmd, expected_safe):
    """Test a command directly using the module's functions."""
    result = parse_commands(cmd)
    if result.error or not result.commands:
        is_safe = False
    else:
        is_safe = all(is_command_safe(tokens) for tokens in result.commands)
    assert is_safe == expected_safe


@pytest.mark.parametrize("tokens,expected_desc", DESCRIPTION_TESTS)
def test_description(tokens, expected_desc):
    """Test command description extraction."""
    assert get_command_description(tokens) == expected_desc


def test_python_dippy_self():
    """Test that dippy allows running itself."""
    import dippy.dippy as dippy_module

    dippy_path = Path(dippy_module.__file__).resolve()
    # Absolute path
    assert is_command_safe(["python", str(dippy_path)]) is True
    # Relative path from project root
    assert is_command_safe(["python", "src/dippy/dippy.py"]) is True
    # With flags
    assert is_command_safe(["python", "-u", str(dippy_path)]) is True
    # Wrong path should fail
    assert is_command_safe(["python", "/tmp/dippy.py"]) is False


def test_dippy_self_via_uv():
    """Test that dippy allows running itself via uv run (self-executing)."""
    import dippy.dippy as dippy_module

    dippy_path = Path(dippy_module.__file__).resolve()
    # After uv run wrapper stripping, just the script path remains
    assert is_command_safe([str(dippy_path)]) is True
    assert is_command_safe(["src/dippy/dippy.py"]) is True
    # Wrong path should fail
    assert is_command_safe(["/tmp/other.py"]) is False


def test_python_bashlex_oneliner():
    """Test that dippy allows bashlex one-liners for debugging."""
    # Bashlex import allowed
    assert (
        is_command_safe(["python", "-c", "import bashlex; print(bashlex.parse('ls'))"])
        is True
    )
    # Other one-liners rejected
    assert (
        is_command_safe(["python", "-c", "import os; os.system('rm -rf /')"]) is False
    )
    assert is_command_safe(["python", "-c", "print('hello')"]) is False


def test_heredoc_preprocessing():
    """Test that heredocs in command substitution are handled."""
    from dippy.dippy import preprocess_command

    # Single quotes EOF
    cmd = '''git commit -m "$(cat <<'EOF'
message line 1
message line 2
EOF
)"'''
    assert "HEREDOC_PLACEHOLDER" in preprocess_command(cmd)
    # No quotes EOF
    cmd2 = '''git commit -m "$(cat <<EOF
message
EOF
)"'''
    assert "HEREDOC_PLACEHOLDER" in preprocess_command(cmd2)
    # With -C flag
    cmd3 = '''git -C /path commit -m "$(cat <<'EOF'
msg
EOF
)"'''
    assert "HEREDOC_PLACEHOLDER" in preprocess_command(cmd3)
    # Chained commands
    cmd4 = '''git add -A && git commit -m "$(cat <<'EOF'
msg
EOF
)"'''
    assert "HEREDOC_PLACEHOLDER" in preprocess_command(cmd4)


def test_heredoc_commit_parses():
    """Test that git commit with heredoc can be parsed and evaluated."""
    # git commit should be unsafe (requires approval)
    cmd = '''git commit -m "$(cat <<'EOF'
message
EOF
)"'''
    result = parse_commands(cmd)
    assert result.error is None
    assert result.commands is not None
    assert not all(is_command_safe(tokens) for tokens in result.commands)
    # git add && git commit - both parsed, commit unsafe
    cmd2 = '''git add -A && git commit -m "$(cat <<'EOF'
msg
EOF
)"'''
    result2 = parse_commands(cmd2)
    assert result2.error is None
    assert result2.commands is not None
    assert len(result2.commands) == 2


def test_get_unsafe_commands_multiple():
    """Test that compound commands report all unsafe commands."""
    result = parse_commands("git add foo/ && git commit -m 'message'")
    assert result.commands is not None
    unsafe = get_unsafe_commands(result.commands)
    assert unsafe == ["git add", "git commit"]


def test_get_unsafe_commands_dedupe():
    """Test that duplicate unsafe commands are deduplicated."""
    result = parse_commands("source foo && source bar")
    assert result.commands is not None
    unsafe = get_unsafe_commands(result.commands)
    assert unsafe == ["source"]


def test_get_unsafe_commands_mixed():
    """Test compound with safe and unsafe commands."""
    result = parse_commands("ls -la && rm -rf /")
    assert result.commands is not None
    unsafe = get_unsafe_commands(result.commands)
    assert unsafe == ["rm"]


def test_get_unsafe_commands_all_safe():
    """Test that all-safe compound returns empty list."""
    result = parse_commands("ls && pwd && echo hello")
    assert result.commands is not None
    unsafe = get_unsafe_commands(result.commands)
    assert unsafe == []
