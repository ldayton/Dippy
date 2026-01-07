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
    # AWS - comprehensive coverage from tldr
    # aws sts - Security Token Service
    ("aws sts get-caller-identity", True),
    ("aws sts get-session-token", True),
    ("aws sts get-access-key-info --access-key-id AKIA...", True),
    ("aws sts assume-role --role-arn arn:aws:iam::123:role/myrole --role-session-name sess", False),
    ("aws sts assume-role-with-saml --role-arn arn --principal-arn arn --saml-assertion ...", False),
    # aws ec2 - Elastic Compute Cloud
    ("aws ec2 describe-instances", True),
    ("aws ec2 describe-instances --instance-ids i-123", True),
    ("aws ec2 describe-instances --filters Name=tag:Name,Values=myserver", True),
    ("aws ec2 describe-volumes", True),
    ("aws ec2 describe-volumes --volume-ids vol-123", True),
    ("aws ec2 describe-images", True),
    ("aws ec2 describe-images --owners self", True),
    ("aws ec2 describe-security-groups", True),
    ("aws ec2 describe-subnets", True),
    ("aws ec2 describe-vpcs", True),
    ("aws ec2 describe-key-pairs", True),
    ("aws ec2 describe-snapshots --owner-ids self", True),
    ("aws ec2 describe-availability-zones", True),
    ("aws ec2 describe-regions", True),
    ("aws ec2 describe-addresses", True),
    ("aws ec2 describe-network-interfaces", True),
    ("aws ec2 describe-route-tables", True),
    ("aws ec2 describe-internet-gateways", True),
    ("aws ec2 describe-nat-gateways", True),
    ("aws ec2 describe-launch-templates", True),
    ("aws ec2 get-console-output --instance-id i-123", True),
    ("aws ec2 get-password-data --instance-id i-123", True),
    ("aws ec2 run-instances --image-id ami-123 --instance-type t2.micro", False),
    ("aws ec2 start-instances --instance-ids i-123", False),
    ("aws ec2 stop-instances --instance-ids i-123", False),
    ("aws ec2 reboot-instances --instance-ids i-123", False),
    ("aws ec2 terminate-instances --instance-ids i-123", False),
    ("aws ec2 create-snapshot --volume-id vol-123", False),
    ("aws ec2 delete-snapshot --snapshot-id snap-123", False),
    ("aws ec2 delete-volume --volume-id vol-123", False),
    ("aws ec2 create-image --instance-id i-123 --name myami", False),
    ("aws ec2 create-key-pair --key-name mykey", False),
    ("aws ec2 delete-key-pair --key-name mykey", False),
    ("aws ec2 create-security-group --group-name mysg --description desc", False),
    ("aws ec2 delete-security-group --group-id sg-123", False),
    ("aws ec2 authorize-security-group-ingress --group-id sg-123 --protocol tcp --port 22 --cidr 0.0.0.0/0", False),
    ("aws ec2 modify-instance-attribute --instance-id i-123 --instance-type t3.micro", False),
    # aws s3 - Simple Storage Service (high-level commands)
    ("aws s3 ls", True),
    ("aws s3 ls s3://mybucket", True),
    ("aws s3 ls s3://mybucket/prefix/", True),
    ("aws s3 ls s3://mybucket --recursive", True),
    ("aws s3 cp s3://src/file s3://dst/file", False),
    ("aws s3 cp localfile s3://bucket/file", False),
    ("aws s3 cp s3://bucket/file localfile", False),
    ("aws s3 mv s3://src/file s3://dst/file", False),
    ("aws s3 rm s3://bucket/file", False),
    ("aws s3 rm s3://bucket/ --recursive", False),
    ("aws s3 sync ./local s3://bucket", False),
    ("aws s3 sync s3://bucket ./local", False),
    ("aws s3 mb s3://newbucket", False),
    ("aws s3 rb s3://bucket", False),
    ("aws s3 rb s3://bucket --force", False),
    ("aws s3 presign s3://bucket/file", False),  # generates URL but could leak
    ("aws s3 website s3://bucket --index-document index.html", False),
    # aws s3api - S3 API commands
    ("aws s3api list-buckets", True),
    ("aws s3api list-objects --bucket mybucket", True),
    ("aws s3api list-objects-v2 --bucket mybucket", True),
    ("aws s3api list-object-versions --bucket mybucket", True),
    ("aws s3api list-multipart-uploads --bucket mybucket", True),
    ("aws s3api get-bucket-location --bucket mybucket", True),
    ("aws s3api get-bucket-versioning --bucket mybucket", True),
    ("aws s3api get-bucket-acl --bucket mybucket", True),
    ("aws s3api get-bucket-policy --bucket mybucket", True),
    ("aws s3api get-bucket-logging --bucket mybucket", True),
    ("aws s3api get-bucket-encryption --bucket mybucket", True),
    ("aws s3api get-bucket-lifecycle-configuration --bucket mybucket", True),
    ("aws s3api get-bucket-tagging --bucket mybucket", True),
    ("aws s3api get-object --bucket mybucket --key mykey outfile", True),
    ("aws s3api get-object-acl --bucket mybucket --key mykey", True),
    ("aws s3api get-object-tagging --bucket mybucket --key mykey", True),
    ("aws s3api head-bucket --bucket mybucket", True),
    ("aws s3api head-object --bucket mybucket --key mykey", True),
    ("aws s3api put-object --bucket mybucket --key mykey --body file", False),
    ("aws s3api delete-object --bucket mybucket --key mykey", False),
    ("aws s3api delete-objects --bucket mybucket --delete file://delete.json", False),
    ("aws s3api create-bucket --bucket newbucket", False),
    ("aws s3api delete-bucket --bucket mybucket", False),
    ("aws s3api put-bucket-policy --bucket mybucket --policy file://policy.json", False),
    ("aws s3api put-bucket-acl --bucket mybucket --acl public-read", False),
    # aws iam - Identity and Access Management
    ("aws iam list-users", True),
    ("aws iam list-groups", True),
    ("aws iam list-roles", True),
    ("aws iam list-policies", True),
    ("aws iam list-policies --scope Local", True),
    ("aws iam list-attached-user-policies --user-name myuser", True),
    ("aws iam list-attached-role-policies --role-name myrole", True),
    ("aws iam list-attached-group-policies --group-name mygroup", True),
    ("aws iam list-user-policies --user-name myuser", True),
    ("aws iam list-role-policies --role-name myrole", True),
    ("aws iam list-group-policies --group-name mygroup", True),
    ("aws iam list-access-keys", True),
    ("aws iam list-access-keys --user-name myuser", True),
    ("aws iam list-mfa-devices", True),
    ("aws iam list-mfa-devices --user-name myuser", True),
    ("aws iam list-account-aliases", True),
    ("aws iam list-instance-profiles", True),
    ("aws iam list-server-certificates", True),
    ("aws iam list-signing-certificates", True),
    ("aws iam list-ssh-public-keys", True),
    ("aws iam get-user", True),
    ("aws iam get-user --user-name myuser", True),
    ("aws iam get-group --group-name mygroup", True),
    ("aws iam get-role --role-name myrole", True),
    ("aws iam get-policy --policy-arn arn:aws:iam::123:policy/mypolicy", True),
    ("aws iam get-policy-version --policy-arn arn --version-id v1", True),
    ("aws iam get-account-summary", True),
    ("aws iam get-account-password-policy", True),
    ("aws iam get-account-authorization-details", True),
    ("aws iam get-credential-report", True),
    ("aws iam get-instance-profile --instance-profile-name myprofile", True),
    ("aws iam get-login-profile --user-name myuser", True),
    ("aws iam get-access-key-last-used --access-key-id AKIA...", True),
    ("aws iam generate-credential-report", True),
    ("aws iam simulate-principal-policy --policy-source-arn arn --action-names s3:GetObject", True),
    ("aws iam create-user --user-name newuser", False),
    ("aws iam delete-user --user-name myuser", False),
    ("aws iam create-group --group-name newgroup", False),
    ("aws iam delete-group --group-name mygroup", False),
    ("aws iam create-role --role-name newrole --assume-role-policy-document file://trust.json", False),
    ("aws iam delete-role --role-name myrole", False),
    ("aws iam create-policy --policy-name newpolicy --policy-document file://policy.json", False),
    ("aws iam delete-policy --policy-arn arn", False),
    ("aws iam attach-user-policy --user-name myuser --policy-arn arn", False),
    ("aws iam detach-user-policy --user-name myuser --policy-arn arn", False),
    ("aws iam attach-role-policy --role-name myrole --policy-arn arn", False),
    ("aws iam detach-role-policy --role-name myrole --policy-arn arn", False),
    ("aws iam add-user-to-group --user-name myuser --group-name mygroup", False),
    ("aws iam remove-user-from-group --user-name myuser --group-name mygroup", False),
    ("aws iam create-access-key --user-name myuser", False),
    ("aws iam delete-access-key --access-key-id AKIA... --user-name myuser", False),
    ("aws iam update-access-key --access-key-id AKIA... --status Inactive", False),
    ("aws iam create-login-profile --user-name myuser --password pass", False),
    ("aws iam update-login-profile --user-name myuser --password newpass", False),
    ("aws iam delete-login-profile --user-name myuser", False),
    ("aws iam change-password --old-password old --new-password new", False),
    ("aws iam put-user-policy --user-name myuser --policy-name pol --policy-document file://p.json", False),
    ("aws iam put-role-policy --role-name myrole --policy-name pol --policy-document file://p.json", False),
    # aws lambda - Lambda Functions
    ("aws lambda list-functions", True),
    ("aws lambda list-functions --region us-east-1", True),
    ("aws lambda list-aliases --function-name myfunc", True),
    ("aws lambda list-versions-by-function --function-name myfunc", True),
    ("aws lambda list-event-source-mappings", True),
    ("aws lambda list-event-source-mappings --function-name myfunc", True),
    ("aws lambda list-layers", True),
    ("aws lambda list-layer-versions --layer-name mylayer", True),
    ("aws lambda list-tags --resource arn:aws:lambda:...", True),
    ("aws lambda get-function --function-name myfunc", True),
    ("aws lambda get-function-configuration --function-name myfunc", True),
    ("aws lambda get-function-concurrency --function-name myfunc", True),
    ("aws lambda get-function-url-config --function-name myfunc", True),
    ("aws lambda get-alias --function-name myfunc --name myalias", True),
    ("aws lambda get-policy --function-name myfunc", True),
    ("aws lambda get-account-settings", True),
    ("aws lambda get-layer-version --layer-name mylayer --version-number 1", True),
    ("aws lambda invoke --function-name myfunc response.json", False),
    ("aws lambda invoke --function-name myfunc --payload '{}' response.json", False),
    ("aws lambda create-function --function-name newfunc --runtime python3.9 --role arn --handler handler.main --zip-file fileb://code.zip", False),
    ("aws lambda delete-function --function-name myfunc", False),
    ("aws lambda update-function-code --function-name myfunc --zip-file fileb://code.zip", False),
    ("aws lambda update-function-configuration --function-name myfunc --timeout 30", False),
    ("aws lambda publish-version --function-name myfunc", False),
    ("aws lambda create-alias --function-name myfunc --name myalias --function-version 1", False),
    ("aws lambda delete-alias --function-name myfunc --name myalias", False),
    ("aws lambda add-permission --function-name myfunc --statement-id stmt --action lambda:InvokeFunction --principal s3.amazonaws.com", False),
    ("aws lambda remove-permission --function-name myfunc --statement-id stmt", False),
    ("aws lambda put-function-concurrency --function-name myfunc --reserved-concurrent-executions 10", False),
    # aws dynamodb - DynamoDB
    ("aws dynamodb list-tables", True),
    ("aws dynamodb list-tables --region us-east-1", True),
    ("aws dynamodb list-global-tables", True),
    ("aws dynamodb list-backups", True),
    ("aws dynamodb list-exports", True),
    ("aws dynamodb list-imports", True),
    ("aws dynamodb list-contributor-insights", True),
    ("aws dynamodb describe-table --table-name mytable", True),
    ("aws dynamodb describe-continuous-backups --table-name mytable", True),
    ("aws dynamodb describe-time-to-live --table-name mytable", True),
    ("aws dynamodb describe-limits", True),
    ("aws dynamodb describe-endpoints", True),
    ("aws dynamodb describe-backup --backup-arn arn", True),
    ("aws dynamodb describe-global-table --global-table-name mytable", True),
    ("aws dynamodb describe-global-table-settings --global-table-name mytable", True),
    ("aws dynamodb get-item --table-name mytable --key file://key.json", True),
    ("aws dynamodb batch-get-item --request-items file://items.json", True),
    ("aws dynamodb query --table-name mytable --key-condition-expression 'pk = :pk' --expression-attribute-values file://vals.json", True),
    ("aws dynamodb scan --table-name mytable", True),
    ("aws dynamodb scan --table-name mytable --filter-expression 'attr > :val'", True),
    ("aws dynamodb transact-get-items --transact-items file://items.json", True),
    ("aws dynamodb create-table --table-name newtable --attribute-definitions ... --key-schema ... --billing-mode PAY_PER_REQUEST", False),
    ("aws dynamodb delete-table --table-name mytable", False),
    ("aws dynamodb update-table --table-name mytable --billing-mode PAY_PER_REQUEST", False),
    ("aws dynamodb put-item --table-name mytable --item file://item.json", False),
    ("aws dynamodb update-item --table-name mytable --key file://key.json --update-expression 'SET attr = :val'", False),
    ("aws dynamodb delete-item --table-name mytable --key file://key.json", False),
    ("aws dynamodb batch-write-item --request-items file://items.json", False),
    ("aws dynamodb transact-write-items --transact-items file://items.json", False),
    ("aws dynamodb create-backup --table-name mytable --backup-name mybackup", False),
    ("aws dynamodb delete-backup --backup-arn arn", False),
    ("aws dynamodb restore-table-from-backup --target-table-name newtable --backup-arn arn", False),
    # aws rds - Relational Database Service
    ("aws rds describe-db-instances", True),
    ("aws rds describe-db-instances --db-instance-identifier mydb", True),
    ("aws rds describe-db-clusters", True),
    ("aws rds describe-db-clusters --db-cluster-identifier mycluster", True),
    ("aws rds describe-db-snapshots", True),
    ("aws rds describe-db-snapshots --db-snapshot-identifier mysnap", True),
    ("aws rds describe-db-cluster-snapshots", True),
    ("aws rds describe-db-parameter-groups", True),
    ("aws rds describe-db-parameters --db-parameter-group-name mygroup", True),
    ("aws rds describe-db-subnet-groups", True),
    ("aws rds describe-db-security-groups", True),
    ("aws rds describe-db-engine-versions", True),
    ("aws rds describe-db-log-files --db-instance-identifier mydb", True),
    ("aws rds describe-events", True),
    ("aws rds describe-events --source-type db-instance", True),
    ("aws rds describe-reserved-db-instances", True),
    ("aws rds describe-orderable-db-instance-options --engine postgres", True),
    ("aws rds describe-account-attributes", True),
    ("aws rds describe-certificates", True),
    ("aws rds describe-pending-maintenance-actions", True),
    ("aws rds list-tags-for-resource --resource-name arn:aws:rds:...", True),
    ("aws rds download-db-log-file-portion --db-instance-identifier mydb --log-file-name error.log", True),
    ("aws rds create-db-instance --db-instance-identifier newdb --db-instance-class db.t3.micro --engine postgres", False),
    ("aws rds delete-db-instance --db-instance-identifier mydb", False),
    ("aws rds delete-db-instance --db-instance-identifier mydb --skip-final-snapshot", False),
    ("aws rds start-db-instance --db-instance-identifier mydb", False),
    ("aws rds stop-db-instance --db-instance-identifier mydb", False),
    ("aws rds reboot-db-instance --db-instance-identifier mydb", False),
    ("aws rds modify-db-instance --db-instance-identifier mydb --db-instance-class db.t3.medium", False),
    ("aws rds modify-db-instance --db-instance-identifier mydb --apply-immediately", False),
    ("aws rds create-db-snapshot --db-instance-identifier mydb --db-snapshot-identifier mysnap", False),
    ("aws rds delete-db-snapshot --db-snapshot-identifier mysnap", False),
    ("aws rds restore-db-instance-from-db-snapshot --db-instance-identifier newdb --db-snapshot-identifier mysnap", False),
    ("aws rds create-db-cluster --db-cluster-identifier mycluster --engine aurora-postgresql", False),
    ("aws rds delete-db-cluster --db-cluster-identifier mycluster", False),
    # aws eks - Elastic Kubernetes Service
    ("aws eks list-clusters", True),
    ("aws eks list-nodegroups --cluster-name mycluster", True),
    ("aws eks list-fargate-profiles --cluster-name mycluster", True),
    ("aws eks list-addons --cluster-name mycluster", True),
    ("aws eks list-identity-provider-configs --cluster-name mycluster", True),
    ("aws eks list-updates --name mycluster", True),
    ("aws eks describe-cluster --name mycluster", True),
    ("aws eks describe-nodegroup --cluster-name mycluster --nodegroup-name mynodegroup", True),
    ("aws eks describe-fargate-profile --cluster-name mycluster --fargate-profile-name myprofile", True),
    ("aws eks describe-addon --cluster-name mycluster --addon-name vpc-cni", True),
    ("aws eks describe-addon-versions --addon-name vpc-cni", True),
    ("aws eks describe-update --name mycluster --update-id id", True),
    ("aws eks describe-identity-provider-config --cluster-name mycluster --identity-provider-config type=oidc,name=myconfig", True),
    ("aws eks create-cluster --name newcluster --role-arn arn --resources-vpc-config subnetIds=...", False),
    ("aws eks delete-cluster --name mycluster", False),
    ("aws eks update-cluster-config --name mycluster --resources-vpc-config ...", False),
    ("aws eks update-cluster-version --name mycluster --kubernetes-version 1.27", False),
    ("aws eks update-kubeconfig --name mycluster", False),
    ("aws eks create-nodegroup --cluster-name mycluster --nodegroup-name newnodegroup --subnets ... --node-role arn", False),
    ("aws eks delete-nodegroup --cluster-name mycluster --nodegroup-name mynodegroup", False),
    ("aws eks create-addon --cluster-name mycluster --addon-name vpc-cni", False),
    ("aws eks delete-addon --cluster-name mycluster --addon-name vpc-cni", False),
    # aws ecr - Elastic Container Registry
    ("aws ecr describe-repositories", True),
    ("aws ecr describe-repositories --repository-names myrepo", True),
    ("aws ecr describe-images --repository-name myrepo", True),
    ("aws ecr describe-image-scan-findings --repository-name myrepo --image-id imageTag=latest", True),
    ("aws ecr list-images --repository-name myrepo", True),
    ("aws ecr list-tags-for-resource --resource-arn arn", True),
    ("aws ecr get-repository-policy --repository-name myrepo", True),
    ("aws ecr get-lifecycle-policy --repository-name myrepo", True),
    ("aws ecr get-lifecycle-policy-preview --repository-name myrepo", True),
    ("aws ecr get-login-password", True),
    ("aws ecr get-login-password --region us-east-1", True),
    ("aws ecr get-authorization-token", True),
    ("aws ecr batch-get-image --repository-name myrepo --image-ids imageTag=latest", True),
    ("aws ecr create-repository --repository-name newrepo", False),
    ("aws ecr delete-repository --repository-name myrepo", False),
    ("aws ecr delete-repository --repository-name myrepo --force", False),
    ("aws ecr put-image --repository-name myrepo --image-manifest file://manifest.json", False),
    ("aws ecr batch-delete-image --repository-name myrepo --image-ids imageTag=latest", False),
    ("aws ecr put-lifecycle-policy --repository-name myrepo --lifecycle-policy-text file://policy.json", False),
    ("aws ecr set-repository-policy --repository-name myrepo --policy-text file://policy.json", False),
    ("aws ecr start-image-scan --repository-name myrepo --image-id imageTag=latest", False),
    # aws cloudformation - CloudFormation
    ("aws cloudformation list-stacks", True),
    ("aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE", True),
    ("aws cloudformation list-stack-resources --stack-name mystack", True),
    ("aws cloudformation list-stack-sets", True),
    ("aws cloudformation list-exports", True),
    ("aws cloudformation list-imports --export-name myexport", True),
    ("aws cloudformation list-types", True),
    ("aws cloudformation list-change-sets --stack-name mystack", True),
    ("aws cloudformation describe-stacks", True),
    ("aws cloudformation describe-stacks --stack-name mystack", True),
    ("aws cloudformation describe-stack-events --stack-name mystack", True),
    ("aws cloudformation describe-stack-resource --stack-name mystack --logical-resource-id myresource", True),
    ("aws cloudformation describe-stack-resources --stack-name mystack", True),
    ("aws cloudformation describe-stack-resource-drifts --stack-name mystack", True),
    ("aws cloudformation describe-stack-set --stack-set-name myset", True),
    ("aws cloudformation describe-change-set --change-set-name mychangeset --stack-name mystack", True),
    ("aws cloudformation describe-type --type-name AWS::S3::Bucket", True),
    ("aws cloudformation get-stack-policy --stack-name mystack", True),
    ("aws cloudformation get-template --stack-name mystack", True),
    ("aws cloudformation get-template-summary --stack-name mystack", True),
    ("aws cloudformation detect-stack-drift --stack-name mystack", True),
    ("aws cloudformation detect-stack-resource-drift --stack-name mystack --logical-resource-id res", True),
    ("aws cloudformation validate-template --template-body file://template.yaml", True),
    ("aws cloudformation estimate-template-cost --template-body file://template.yaml", True),
    ("aws cloudformation create-stack --stack-name newstack --template-body file://template.yaml", False),
    ("aws cloudformation delete-stack --stack-name mystack", False),
    ("aws cloudformation update-stack --stack-name mystack --template-body file://template.yaml", False),
    ("aws cloudformation execute-change-set --change-set-name mychangeset --stack-name mystack", False),
    ("aws cloudformation cancel-update-stack --stack-name mystack", False),
    ("aws cloudformation continue-update-rollback --stack-name mystack", False),
    ("aws cloudformation create-change-set --stack-name mystack --change-set-name mychangeset --template-body file://t.yaml", False),
    ("aws cloudformation delete-change-set --change-set-name mychangeset --stack-name mystack", False),
    ("aws cloudformation signal-resource --stack-name mystack --logical-resource-id res --unique-id id --status SUCCESS", False),
    # aws logs - CloudWatch Logs
    ("aws logs describe-log-groups", True),
    ("aws logs describe-log-groups --log-group-name-prefix /aws/lambda", True),
    ("aws logs describe-log-streams --log-group-name mygroup", True),
    ("aws logs describe-log-streams --log-group-name mygroup --order-by LastEventTime --descending", True),
    ("aws logs describe-metric-filters --log-group-name mygroup", True),
    ("aws logs describe-subscription-filters --log-group-name mygroup", True),
    ("aws logs describe-export-tasks", True),
    ("aws logs describe-queries", True),
    ("aws logs describe-query-definitions", True),
    ("aws logs describe-destinations", True),
    ("aws logs describe-resource-policies", True),
    ("aws logs filter-log-events --log-group-name mygroup", True),
    ("aws logs filter-log-events --log-group-name mygroup --filter-pattern ERROR", True),
    ("aws logs filter-log-events --log-group-name mygroup --start-time 1234567890000", True),
    ("aws logs get-log-events --log-group-name mygroup --log-stream-name mystream", True),
    ("aws logs get-log-record --log-record-pointer ptr", True),
    ("aws logs get-query-results --query-id id", True),
    ("aws logs start-query --log-group-name mygroup --start-time 0 --end-time 1 --query-string 'fields @message'", True),
    ("aws logs stop-query --query-id id", True),
    ("aws logs tail --log-group-name mygroup", True),
    ("aws logs tail --log-group-name mygroup --follow", True),
    ("aws logs create-log-group --log-group-name newgroup", False),
    ("aws logs delete-log-group --log-group-name mygroup", False),
    ("aws logs create-log-stream --log-group-name mygroup --log-stream-name newstream", False),
    ("aws logs delete-log-stream --log-group-name mygroup --log-stream-name mystream", False),
    ("aws logs put-log-events --log-group-name mygroup --log-stream-name mystream --log-events ...", False),
    ("aws logs put-retention-policy --log-group-name mygroup --retention-in-days 30", False),
    ("aws logs delete-retention-policy --log-group-name mygroup", False),
    ("aws logs put-metric-filter --log-group-name mygroup --filter-name myfilter --filter-pattern ERROR --metric-transformations ...", False),
    ("aws logs delete-metric-filter --log-group-name mygroup --filter-name myfilter", False),
    # aws cloudwatch - CloudWatch Metrics/Alarms
    ("aws cloudwatch list-metrics", True),
    ("aws cloudwatch list-metrics --namespace AWS/EC2", True),
    ("aws cloudwatch list-dashboards", True),
    ("aws cloudwatch list-tags-for-resource --resource-arn arn", True),
    ("aws cloudwatch describe-alarms", True),
    ("aws cloudwatch describe-alarms --alarm-names myalarm", True),
    ("aws cloudwatch describe-alarms-for-metric --metric-name CPUUtilization --namespace AWS/EC2", True),
    ("aws cloudwatch describe-alarm-history --alarm-name myalarm", True),
    ("aws cloudwatch describe-anomaly-detectors", True),
    ("aws cloudwatch describe-insight-rules", True),
    ("aws cloudwatch get-dashboard --dashboard-name mydash", True),
    ("aws cloudwatch get-metric-data --metric-data-queries file://queries.json --start-time 2023-01-01 --end-time 2023-01-02", True),
    ("aws cloudwatch get-metric-statistics --namespace AWS/EC2 --metric-name CPUUtilization --start-time 2023-01-01 --end-time 2023-01-02 --period 3600 --statistics Average", True),
    ("aws cloudwatch get-metric-widget-image --metric-widget file://widget.json", True),
    ("aws cloudwatch get-insight-rule-report --rule-name myrule --start-time 2023-01-01 --end-time 2023-01-02 --period 3600", True),
    ("aws cloudwatch put-metric-alarm --alarm-name newalarm --metric-name CPUUtilization --namespace AWS/EC2 --threshold 80 --comparison-operator GreaterThanThreshold --evaluation-periods 2 --period 300 --statistic Average", False),
    ("aws cloudwatch delete-alarms --alarm-names myalarm", False),
    ("aws cloudwatch put-dashboard --dashboard-name mydash --dashboard-body file://dash.json", False),
    ("aws cloudwatch delete-dashboards --dashboard-names mydash", False),
    ("aws cloudwatch put-metric-data --namespace MyNamespace --metric-name MyMetric --value 1", False),
    ("aws cloudwatch enable-alarm-actions --alarm-names myalarm", False),
    ("aws cloudwatch disable-alarm-actions --alarm-names myalarm", False),
    ("aws cloudwatch set-alarm-state --alarm-name myalarm --state-value OK --state-reason testing", False),
    # aws secretsmanager - Secrets Manager
    ("aws secretsmanager list-secrets", True),
    ("aws secretsmanager list-secrets --filters Key=name,Values=prod", True),
    ("aws secretsmanager list-secret-version-ids --secret-id mysecret", True),
    ("aws secretsmanager describe-secret --secret-id mysecret", True),
    ("aws secretsmanager get-resource-policy --secret-id mysecret", True),
    ("aws secretsmanager get-secret-value --secret-id mysecret", False),  # accessing secret data
    ("aws secretsmanager get-secret-value --secret-id mysecret --version-stage AWSCURRENT", False),
    ("aws secretsmanager create-secret --name newsecret --secret-string 'myvalue'", False),
    ("aws secretsmanager delete-secret --secret-id mysecret", False),
    ("aws secretsmanager delete-secret --secret-id mysecret --force-delete-without-recovery", False),
    ("aws secretsmanager update-secret --secret-id mysecret --secret-string 'newvalue'", False),
    ("aws secretsmanager put-secret-value --secret-id mysecret --secret-string 'value'", False),
    ("aws secretsmanager rotate-secret --secret-id mysecret", False),
    ("aws secretsmanager restore-secret --secret-id mysecret", False),
    ("aws secretsmanager tag-resource --secret-id mysecret --tags Key=env,Value=prod", False),
    ("aws secretsmanager put-resource-policy --secret-id mysecret --resource-policy file://policy.json", False),
    # aws sqs - Simple Queue Service
    ("aws sqs list-queues", True),
    ("aws sqs list-queues --queue-name-prefix prod", True),
    ("aws sqs list-queue-tags --queue-url https://sqs...", True),
    ("aws sqs list-dead-letter-source-queues --queue-url https://sqs...", True),
    ("aws sqs get-queue-url --queue-name myqueue", True),
    ("aws sqs get-queue-attributes --queue-url https://sqs... --attribute-names All", True),
    ("aws sqs receive-message --queue-url https://sqs...", True),
    ("aws sqs receive-message --queue-url https://sqs... --max-number-of-messages 10", True),
    ("aws sqs create-queue --queue-name newqueue", False),
    ("aws sqs delete-queue --queue-url https://sqs...", False),
    ("aws sqs purge-queue --queue-url https://sqs...", False),
    ("aws sqs send-message --queue-url https://sqs... --message-body hello", False),
    ("aws sqs send-message-batch --queue-url https://sqs... --entries file://entries.json", False),
    ("aws sqs delete-message --queue-url https://sqs... --receipt-handle handle", False),
    ("aws sqs delete-message-batch --queue-url https://sqs... --entries file://entries.json", False),
    ("aws sqs set-queue-attributes --queue-url https://sqs... --attributes file://attrs.json", False),
    ("aws sqs add-permission --queue-url https://sqs... --label perm --aws-account-ids 123 --actions SendMessage", False),
    ("aws sqs remove-permission --queue-url https://sqs... --label perm", False),
    ("aws sqs tag-queue --queue-url https://sqs... --tags env=prod", False),
    # aws sns - Simple Notification Service
    ("aws sns list-topics", True),
    ("aws sns list-subscriptions", True),
    ("aws sns list-subscriptions-by-topic --topic-arn arn", True),
    ("aws sns list-platform-applications", True),
    ("aws sns list-endpoints-by-platform-application --platform-application-arn arn", True),
    ("aws sns list-phone-numbers-opted-out", True),
    ("aws sns list-origination-numbers", True),
    ("aws sns list-sms-sandbox-phone-numbers", True),
    ("aws sns list-tags-for-resource --resource-arn arn", True),
    ("aws sns get-topic-attributes --topic-arn arn", True),
    ("aws sns get-subscription-attributes --subscription-arn arn", True),
    ("aws sns get-sms-attributes", True),
    ("aws sns get-sms-sandbox-account-status", True),
    ("aws sns get-endpoint-attributes --endpoint-arn arn", True),
    ("aws sns get-platform-application-attributes --platform-application-arn arn", True),
    ("aws sns get-data-protection-policy --resource-arn arn", True),
    ("aws sns check-if-phone-number-is-opted-out --phone-number +1234567890", True),
    ("aws sns create-topic --name newtopic", False),
    ("aws sns delete-topic --topic-arn arn", False),
    ("aws sns subscribe --topic-arn arn --protocol email --notification-endpoint email@example.com", False),
    ("aws sns unsubscribe --subscription-arn arn", False),
    ("aws sns confirm-subscription --topic-arn arn --token token", False),
    ("aws sns publish --topic-arn arn --message hello", False),
    ("aws sns publish --phone-number +1234567890 --message hello", False),
    ("aws sns set-topic-attributes --topic-arn arn --attribute-name DisplayName --attribute-value name", False),
    ("aws sns set-subscription-attributes --subscription-arn arn --attribute-name RawMessageDelivery --attribute-value true", False),
    ("aws sns add-permission --topic-arn arn --label perm --aws-account-id 123 --action-name Publish", False),
    ("aws sns remove-permission --topic-arn arn --label perm", False),
    ("aws sns tag-resource --resource-arn arn --tags Key=env,Value=prod", False),
    # aws kinesis - Kinesis Data Streams
    ("aws kinesis list-streams", True),
    ("aws kinesis list-shards --stream-name mystream", True),
    ("aws kinesis list-stream-consumers --stream-arn arn", True),
    ("aws kinesis list-tags-for-stream --stream-name mystream", True),
    ("aws kinesis describe-stream --stream-name mystream", True),
    ("aws kinesis describe-stream-summary --stream-name mystream", True),
    ("aws kinesis describe-stream-consumer --stream-arn arn --consumer-name consumer", True),
    ("aws kinesis describe-limits", True),
    ("aws kinesis get-shard-iterator --stream-name mystream --shard-id shardId-000 --shard-iterator-type TRIM_HORIZON", True),
    ("aws kinesis get-records --shard-iterator iter", True),
    ("aws kinesis create-stream --stream-name newstream --shard-count 1", False),
    ("aws kinesis delete-stream --stream-name mystream", False),
    ("aws kinesis put-record --stream-name mystream --partition-key key --data data", False),
    ("aws kinesis put-records --stream-name mystream --records file://records.json", False),
    ("aws kinesis split-shard --stream-name mystream --shard-to-split shardId-000 --new-starting-hash-key 123", False),
    ("aws kinesis merge-shards --stream-name mystream --shard-to-merge shardId-000 --adjacent-shard-to-merge shardId-001", False),
    ("aws kinesis increase-stream-retention-period --stream-name mystream --retention-period-hours 48", False),
    ("aws kinesis decrease-stream-retention-period --stream-name mystream --retention-period-hours 24", False),
    ("aws kinesis register-stream-consumer --stream-arn arn --consumer-name consumer", False),
    ("aws kinesis deregister-stream-consumer --stream-arn arn --consumer-name consumer", False),
    ("aws kinesis update-shard-count --stream-name mystream --target-shard-count 2 --scaling-type UNIFORM_SCALING", False),
    # aws route53 - Route 53 DNS
    ("aws route53 list-hosted-zones", True),
    ("aws route53 list-hosted-zones-by-name", True),
    ("aws route53 list-resource-record-sets --hosted-zone-id Z123", True),
    ("aws route53 list-health-checks", True),
    ("aws route53 list-query-logging-configs", True),
    ("aws route53 list-traffic-policies", True),
    ("aws route53 list-traffic-policy-instances", True),
    ("aws route53 list-vpc-association-authorizations --hosted-zone-id Z123", True),
    ("aws route53 list-tags-for-resource --resource-type hostedzone --resource-id Z123", True),
    ("aws route53 list-tags-for-resources --resource-type hostedzone --resource-ids Z123", True),
    ("aws route53 list-reusable-delegation-sets", True),
    ("aws route53 list-geo-locations", True),
    ("aws route53 list-cidr-collections", True),
    ("aws route53 list-cidr-blocks --collection-id col", True),
    ("aws route53 list-cidr-locations --collection-id col", True),
    ("aws route53 get-hosted-zone --id Z123", True),
    ("aws route53 get-hosted-zone-count", True),
    ("aws route53 get-health-check --health-check-id hc123", True),
    ("aws route53 get-health-check-count", True),
    ("aws route53 get-health-check-status --health-check-id hc123", True),
    ("aws route53 get-health-check-last-failure-reason --health-check-id hc123", True),
    ("aws route53 get-geo-location --continent-code EU", True),
    ("aws route53 get-change --id C123", True),
    ("aws route53 get-checker-ip-ranges", True),
    ("aws route53 get-dns-sec --hosted-zone-id Z123", True),
    ("aws route53 get-query-logging-config --id qlc123", True),
    ("aws route53 get-reusable-delegation-set --id N123", True),
    ("aws route53 get-traffic-policy --id tp123 --version 1", True),
    ("aws route53 get-traffic-policy-instance --id tpi123", True),
    ("aws route53 get-traffic-policy-instance-count", True),
    ("aws route53 test-dns-answer --hosted-zone-id Z123 --record-name example.com --record-type A", True),
    ("aws route53 create-hosted-zone --name example.com --caller-reference ref", False),
    ("aws route53 delete-hosted-zone --id Z123", False),
    ("aws route53 change-resource-record-sets --hosted-zone-id Z123 --change-batch file://changes.json", False),
    ("aws route53 create-health-check --caller-reference ref --health-check-config file://config.json", False),
    ("aws route53 delete-health-check --health-check-id hc123", False),
    ("aws route53 update-health-check --health-check-id hc123 --port 443", False),
    ("aws route53 associate-vpc-with-hosted-zone --hosted-zone-id Z123 --vpc VPCRegion=us-east-1,VPCId=vpc-123", False),
    ("aws route53 disassociate-vpc-from-hosted-zone --hosted-zone-id Z123 --vpc VPCRegion=us-east-1,VPCId=vpc-123", False),
    # aws cognito-idp - Cognito User Pools
    ("aws cognito-idp list-user-pools --max-results 10", True),
    ("aws cognito-idp list-users --user-pool-id us-east-1_abc123", True),
    ("aws cognito-idp list-users --user-pool-id us-east-1_abc123 --filter 'email = \"user@example.com\"'", True),
    ("aws cognito-idp list-groups --user-pool-id us-east-1_abc123", True),
    ("aws cognito-idp list-users-in-group --user-pool-id us-east-1_abc123 --group-name mygroup", True),
    ("aws cognito-idp list-user-pool-clients --user-pool-id us-east-1_abc123", True),
    ("aws cognito-idp list-identity-providers --user-pool-id us-east-1_abc123", True),
    ("aws cognito-idp list-resource-servers --user-pool-id us-east-1_abc123", True),
    ("aws cognito-idp list-tags-for-resource --resource-arn arn", True),
    ("aws cognito-idp describe-user-pool --user-pool-id us-east-1_abc123", True),
    ("aws cognito-idp describe-user-pool-client --user-pool-id us-east-1_abc123 --client-id clientid", True),
    ("aws cognito-idp describe-identity-provider --user-pool-id us-east-1_abc123 --provider-name Google", True),
    ("aws cognito-idp describe-resource-server --user-pool-id us-east-1_abc123 --identifier myrs", True),
    ("aws cognito-idp describe-user-import-job --user-pool-id us-east-1_abc123 --job-id jobid", True),
    ("aws cognito-idp get-user-pool-mfa-config --user-pool-id us-east-1_abc123", True),
    ("aws cognito-idp get-group --user-pool-id us-east-1_abc123 --group-name mygroup", True),
    ("aws cognito-idp get-ui-customization --user-pool-id us-east-1_abc123", True),
    ("aws cognito-idp get-csv-header --user-pool-id us-east-1_abc123", True),
    ("aws cognito-idp get-signing-certificate --user-pool-id us-east-1_abc123", True),
    ("aws cognito-idp admin-get-user --user-pool-id us-east-1_abc123 --username myuser", True),
    ("aws cognito-idp admin-list-groups-for-user --user-pool-id us-east-1_abc123 --username myuser", True),
    ("aws cognito-idp admin-list-user-auth-events --user-pool-id us-east-1_abc123 --username myuser", True),
    ("aws cognito-idp admin-list-devices --user-pool-id us-east-1_abc123 --username myuser", True),
    ("aws cognito-idp create-user-pool --pool-name newpool", False),
    ("aws cognito-idp delete-user-pool --user-pool-id us-east-1_abc123", False),
    ("aws cognito-idp update-user-pool --user-pool-id us-east-1_abc123 --auto-verified-attributes email", False),
    ("aws cognito-idp admin-create-user --user-pool-id us-east-1_abc123 --username newuser", False),
    ("aws cognito-idp admin-delete-user --user-pool-id us-east-1_abc123 --username myuser", False),
    ("aws cognito-idp admin-set-user-password --user-pool-id us-east-1_abc123 --username myuser --password pass --permanent", False),
    ("aws cognito-idp admin-confirm-sign-up --user-pool-id us-east-1_abc123 --username myuser", False),
    ("aws cognito-idp admin-enable-user --user-pool-id us-east-1_abc123 --username myuser", False),
    ("aws cognito-idp admin-disable-user --user-pool-id us-east-1_abc123 --username myuser", False),
    ("aws cognito-idp admin-add-user-to-group --user-pool-id us-east-1_abc123 --username myuser --group-name mygroup", False),
    ("aws cognito-idp admin-remove-user-from-group --user-pool-id us-east-1_abc123 --username myuser --group-name mygroup", False),
    ("aws cognito-idp admin-reset-user-password --user-pool-id us-east-1_abc123 --username myuser", False),
    ("aws cognito-idp create-group --user-pool-id us-east-1_abc123 --group-name newgroup", False),
    ("aws cognito-idp delete-group --user-pool-id us-east-1_abc123 --group-name mygroup", False),
    # aws ssm - Systems Manager
    ("aws ssm list-commands", True),
    ("aws ssm list-command-invocations --command-id cmd123", True),
    ("aws ssm list-documents", True),
    ("aws ssm list-document-versions --name mydoc", True),
    ("aws ssm list-associations", True),
    ("aws ssm list-association-versions --association-id assoc123", True),
    ("aws ssm list-inventory-entries --instance-id i-123 --type-name AWS:Application", True),
    ("aws ssm list-resource-compliance-summaries", True),
    ("aws ssm list-compliance-items --resource-ids i-123 --resource-types ManagedInstance", True),
    ("aws ssm list-compliance-summaries", True),
    ("aws ssm list-tags-for-resource --resource-type Document --resource-id mydoc", True),
    ("aws ssm describe-instance-information", True),
    ("aws ssm describe-instance-information --instance-information-filter-list key=InstanceIds,valueSet=i-123", True),
    ("aws ssm describe-parameters", True),
    ("aws ssm describe-document --name mydoc", True),
    ("aws ssm describe-automation-executions", True),
    ("aws ssm describe-automation-step-executions --automation-execution-id exec123", True),
    ("aws ssm describe-maintenance-windows", True),
    ("aws ssm describe-maintenance-window-executions --window-id mw-123", True),
    ("aws ssm describe-patch-baselines", True),
    ("aws ssm describe-patch-groups", True),
    ("aws ssm describe-patch-group-state --patch-group mygroup", True),
    ("aws ssm describe-instance-patches --instance-id i-123", True),
    ("aws ssm describe-instance-patch-states --instance-ids i-123", True),
    ("aws ssm describe-effective-patches-for-patch-baseline --baseline-id pb-123", True),
    ("aws ssm describe-ops-items", True),
    ("aws ssm describe-sessions --state Active", True),
    ("aws ssm get-parameter --name /my/param", True),
    ("aws ssm get-parameter --name /my/param --with-decryption", False),  # decryption could expose secrets
    ("aws ssm get-parameters --names /my/param1 /my/param2", True),
    ("aws ssm get-parameters --names /my/param1 --with-decryption", False),
    ("aws ssm get-parameters-by-path --path /my/path", True),
    ("aws ssm get-parameters-by-path --path /my/path --with-decryption", False),
    ("aws ssm get-parameter-history --name /my/param", True),
    ("aws ssm get-parameter-history --name /my/param --with-decryption", False),
    ("aws ssm get-document --name mydoc", True),
    ("aws ssm get-command-invocation --command-id cmd123 --instance-id i-123", True),
    ("aws ssm get-automation-execution --automation-execution-id exec123", True),
    ("aws ssm get-maintenance-window --window-id mw-123", True),
    ("aws ssm get-maintenance-window-execution --window-execution-id we-123", True),
    ("aws ssm get-patch-baseline --baseline-id pb-123", True),
    ("aws ssm get-ops-item --ops-item-id oi-123", True),
    ("aws ssm get-inventory-schema", True),
    ("aws ssm get-connection-status --target i-123", True),
    ("aws ssm put-parameter --name /my/param --value myvalue --type String", False),
    ("aws ssm put-parameter --name /my/param --value myvalue --type SecureString", False),
    ("aws ssm delete-parameter --name /my/param", False),
    ("aws ssm delete-parameters --names /my/param1 /my/param2", False),
    ("aws ssm send-command --instance-ids i-123 --document-name AWS-RunShellScript --parameters commands=ls", False),
    ("aws ssm start-automation-execution --document-name mydoc", False),
    ("aws ssm stop-automation-execution --automation-execution-id exec123", False),
    ("aws ssm cancel-command --command-id cmd123", False),
    ("aws ssm create-document --name newdoc --content file://doc.json --document-type Command", False),
    ("aws ssm delete-document --name mydoc", False),
    ("aws ssm update-document --name mydoc --content file://doc.json --document-version '$LATEST'", False),
    ("aws ssm start-session --target i-123", False),
    ("aws ssm terminate-session --session-id sess123", False),
    # aws configure - AWS CLI configuration (not the service)
    ("aws configure list", True),
    ("aws configure list-profiles", True),
    ("aws configure get region", True),
    ("aws configure get aws_access_key_id", True),
    ("aws configure set region us-east-1", False),
    ("aws configure set aws_access_key_id AKIA...", False),
    ("aws configure sso", False),
    ("aws configure sso-session", False),
    ("aws configure import --csv file://creds.csv", False),
    ("aws configure export-credentials", False),
    # aws help
    ("aws help", True),
    ("aws ec2 help", True),
    ("aws ec2 describe-instances help", True),
    ("aws s3 help", True),
    ("aws iam help", True),
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
    # Gcloud - from tldr examples (comprehensive coverage)
    # gcloud (base) - config, auth, compute, container, components
    ("gcloud config list", True),
    ("gcloud config get project", True),
    ("gcloud config get compute/zone", True),
    ("gcloud config set project my-project", False),
    ("gcloud config set compute/zone us-central1-a", False),
    ("gcloud config configurations list", True),
    ("gcloud config configurations create new-config", False),
    ("gcloud config configurations activate new-config", False),
    # gcloud auth (depth 1)
    ("gcloud auth login", False),
    ("gcloud auth activate-service-account", False),
    ("gcloud auth application-default login", False),
    ("gcloud auth print-access-token", False),
    ("gcloud auth revoke", False),
    ("gcloud auth configure-docker", False),
    # gcloud components (depth 1)
    ("gcloud components list", True),
    ("gcloud components install kubectl", False),
    ("gcloud components update", False),
    ("gcloud components update --version=1.2.3", False),
    ("gcloud components update --quiet", False),
    # gcloud compute (depth 2) - instances
    ("gcloud compute zones list", True),
    ("gcloud compute instances create my-instance", False),
    ("gcloud compute instances describe my-instance", True),
    ("gcloud compute instances list --filter='status=RUNNING'", True),
    ("gcloud compute instances delete my-instance", False),
    ("gcloud compute instances start my-instance", False),
    ("gcloud compute instances stop my-instance", False),
    # gcloud compute - disks/snapshots
    ("gcloud compute disks list", True),
    ("gcloud compute disks describe my-disk", True),
    ("gcloud compute disks snapshot my-disk --snapshot-names=my-snapshot", False),
    ("gcloud compute disks create my-disk", False),
    ("gcloud compute disks delete my-disk", False),
    ("gcloud compute snapshots list", True),
    ("gcloud compute snapshots describe my-snapshot", True),
    ("gcloud compute snapshots delete my-snapshot", False),
    # gcloud compute - ssh (depth 2)
    ("gcloud compute ssh my-instance", False),
    ("gcloud compute ssh user@my-instance --zone=us-central1-a", False),
    # gcloud compute - regions/zones
    ("gcloud compute regions list", True),
    ("gcloud compute regions describe us-central1", True),
    ("gcloud compute zones list", True),
    ("gcloud compute zones describe us-central1-a", True),
    # gcloud compute - networks
    ("gcloud compute networks list", True),
    ("gcloud compute networks describe my-network", True),
    ("gcloud compute networks create my-network", False),
    ("gcloud compute networks delete my-network", False),
    # gcloud compute - firewall rules
    ("gcloud compute firewall-rules list", True),
    ("gcloud compute firewall-rules describe my-rule", True),
    ("gcloud compute firewall-rules create my-rule --allow=tcp:22", False),
    ("gcloud compute firewall-rules delete my-rule", False),
    # gcloud container (depth 2) - clusters
    ("gcloud container clusters list", True),
    ("gcloud container clusters describe my-cluster", True),
    ("gcloud container clusters get-credentials my-cluster", True),
    ("gcloud container clusters create my-cluster", False),
    ("gcloud container clusters delete my-cluster", False),
    ("gcloud container clusters update my-cluster", False),
    ("gcloud container clusters resize my-cluster --size=5", False),
    # gcloud container - images
    ("gcloud container images list", True),
    ("gcloud container images describe gcr.io/my-project/my-image", True),
    ("gcloud container images list-tags gcr.io/my-project/my-image", True),
    ("gcloud container images delete gcr.io/my-project/my-image", False),
    # gcloud container - node-pools
    ("gcloud container node-pools list --cluster=my-cluster", True),
    ("gcloud container node-pools describe my-pool --cluster=my-cluster", True),
    ("gcloud container node-pools create my-pool --cluster=my-cluster", False),
    ("gcloud container node-pools delete my-pool --cluster=my-cluster", False),
    # gcloud iam (depth 2) - roles
    ("gcloud iam roles list", True),
    ("gcloud iam roles describe roles/editor", True),
    ("gcloud iam roles create my-role --project=my-project --file=role.yaml", False),
    ("gcloud iam roles delete my-role --project=my-project", False),
    ("gcloud iam list-grantable-roles //cloudresourcemanager.googleapis.com/projects/my-project", True),
    # gcloud iam - service accounts
    ("gcloud iam service-accounts list", True),
    ("gcloud iam service-accounts describe sa@project.iam.gserviceaccount.com", True),
    ("gcloud iam service-accounts create my-sa", False),
    ("gcloud iam service-accounts delete sa@project.iam.gserviceaccount.com", False),
    ("gcloud iam service-accounts add-iam-policy-binding sa@project.iam.gserviceaccount.com --member=user:foo --role=roles/iam.serviceAccountUser", False),
    ("gcloud iam service-accounts set-iam-policy sa@project.iam.gserviceaccount.com policy.json", False),
    ("gcloud iam service-accounts keys list --iam-account=sa@project.iam.gserviceaccount.com", True),
    ("gcloud iam service-accounts keys create key.json --iam-account=sa@project.iam.gserviceaccount.com", False),
    # gcloud app (depth 2 - default)
    ("gcloud app deploy", False),
    ("gcloud app deploy app.yaml", False),
    ("gcloud app versions list", True),
    ("gcloud app versions describe v1 --service=default", True),
    ("gcloud app versions delete v1 --service=default", False),
    ("gcloud app browse", False),  # opens browser, not read-only
    ("gcloud app create", False),
    ("gcloud app logs read", True),  # read is safe
    ("gcloud app describe", True),
    ("gcloud app services list", True),
    ("gcloud app services describe default", True),
    # gcloud projects (depth 1)
    ("gcloud projects create my-new-project", False),
    ("gcloud projects delete my-project", False),
    ("gcloud projects undelete my-project", False),
    # gcloud secrets (depth 1)
    ("gcloud secrets versions list my-secret", True),
    ("gcloud secrets versions describe 1 --secret=my-secret", True),
    ("gcloud secrets versions access 1 --secret=my-secret", False),  # accessing secret data
    ("gcloud secrets versions destroy 1 --secret=my-secret", False),
    ("gcloud secrets add-iam-policy-binding my-secret --member=user:foo --role=roles/secretmanager.secretAccessor", False),
    # gcloud functions (depth 1)
    ("gcloud functions describe my-function", True),
    ("gcloud functions logs read my-function", True),  # read is safe
    ("gcloud functions deploy my-function", False),
    ("gcloud functions delete my-function", False),
    ("gcloud functions call my-function", False),
    # gcloud logging (depth 1)
    ("gcloud logging read 'severity>=ERROR'", True),
    ("gcloud logging logs list", True),
    ("gcloud logging logs list --bucket=my-bucket --location=us-central1", True),
    ("gcloud logging logs list --filter='logName:syslog'", True),
    ("gcloud logging logs list --limit=100", True),
    ("gcloud logging logs list --sort-by='timestamp'", True),
    ("gcloud logging logs list --verbosity=debug", True),
    ("gcloud logging logs delete my-log", False),
    ("gcloud logging write my-log 'message'", False),
    # gcloud dns (depth 2)
    ("gcloud dns managed-zones list", True),
    ("gcloud dns managed-zones describe my-zone", True),
    ("gcloud dns managed-zones create my-zone --dns-name=example.com", False),
    ("gcloud dns managed-zones delete my-zone", False),
    ("gcloud dns record-sets list --zone=my-zone", True),
    ("gcloud dns record-sets describe www --zone=my-zone --type=A", True),
    ("gcloud dns record-sets create www --zone=my-zone --type=A --rrdatas=1.2.3.4", False),
    ("gcloud dns record-sets delete www --zone=my-zone --type=A", False),
    # gcloud storage (depth 2)
    ("gcloud storage buckets list", True),
    ("gcloud storage buckets describe gs://my-bucket", True),
    ("gcloud storage buckets create gs://my-bucket", False),
    ("gcloud storage buckets delete gs://my-bucket", False),
    ("gcloud storage objects list gs://my-bucket", True),
    ("gcloud storage objects describe gs://my-bucket/my-object", True),
    ("gcloud storage cp gs://src/file gs://dst/file", False),
    ("gcloud storage rm gs://my-bucket/my-object", False),
    # gcloud run (depth 2)
    ("gcloud run services list", True),
    ("gcloud run services describe my-service --region=us-central1", True),
    ("gcloud run services update my-service --region=us-central1 --memory=512Mi", False),
    ("gcloud run services delete my-service --region=us-central1", False),
    ("gcloud run deploy my-service --image=gcr.io/my-project/my-image", False),
    ("gcloud run revisions list --service=my-service", True),
    ("gcloud run revisions describe my-revision", True),
    # gcloud artifacts (depth 3)
    ("gcloud artifacts repositories list", True),
    ("gcloud artifacts repositories describe my-repo --location=us-central1", True),
    ("gcloud artifacts repositories create my-repo --location=us-central1", False),
    ("gcloud artifacts repositories delete my-repo --location=us-central1", False),
    ("gcloud artifacts docker images list us-central1-docker.pkg.dev/my-project/my-repo", True),
    ("gcloud artifacts docker tags list us-central1-docker.pkg.dev/my-project/my-repo/my-image", True),
    ("gcloud artifacts docker tags delete us-central1-docker.pkg.dev/my-project/my-repo/my-image:v1", False),
    # gcloud beta (depth 3)
    ("gcloud beta run services list", True),
    ("gcloud beta run services describe my-service", True),
    ("gcloud beta run services update my-service", False),
    ("gcloud beta run services delete my-service", False),
    ("gcloud beta compute instances list", True),
    ("gcloud beta compute instances describe my-instance", True),
    # gcloud certificate-manager (depth 2)
    ("gcloud certificate-manager certificates list", True),
    ("gcloud certificate-manager certificates describe my-cert", True),
    ("gcloud certificate-manager certificates create my-cert", False),
    ("gcloud certificate-manager trust-configs list", True),
    ("gcloud certificate-manager trust-configs describe my-config", True),
    # gcloud network-security (depth 2)
    ("gcloud network-security server-tls-policies list", True),
    ("gcloud network-security server-tls-policies describe my-policy", True),
    ("gcloud network-security server-tls-policies create my-policy", False),
    ("gcloud network-security gateway-security-policies list", True),
    ("gcloud network-security gateway-security-policies describe my-policy", True),
    # gcloud iap (depth 2)
    ("gcloud iap settings get --project=my-project", True),
    ("gcloud iap settings set iap-settings.yaml --project=my-project", False),
    ("gcloud iap web get-iam-policy --resource-type=backend-services --service=my-service", True),
    ("gcloud iap web set-iam-policy policy.json --resource-type=backend-services", False),
    ("gcloud iap tcp tunnels list", True),
    # gcloud sql (depth 2 - default)
    ("gcloud sql instances list", True),
    ("gcloud sql instances describe my-instance", True),
    ("gcloud sql instances create my-instance", False),
    ("gcloud sql instances delete my-instance", False),
    ("gcloud sql databases list --instance=my-instance", True),
    ("gcloud sql databases describe my-db --instance=my-instance", True),
    ("gcloud sql databases create my-db --instance=my-instance", False),
    ("gcloud sql backups list --instance=my-instance", True),
    ("gcloud sql backups describe 12345 --instance=my-instance", True),
    ("gcloud sql backups create --instance=my-instance", False),
    ("gcloud sql export sql my-instance gs://my-bucket/dump.sql", False),
    ("gcloud sql export sql my-instance gs://my-bucket/dump.sql --async", False),
    ("gcloud sql export sql my-instance gs://my-bucket/dump.sql --database=mydb", False),
    ("gcloud sql import sql my-instance gs://my-bucket/dump.sql", False),
    # gcloud kms (depth 2 - default)
    ("gcloud kms keyrings list --location=global", True),
    ("gcloud kms keyrings describe my-keyring --location=global", True),
    ("gcloud kms keyrings create my-keyring --location=global", False),
    ("gcloud kms keys list --keyring=my-keyring --location=global", True),
    ("gcloud kms keys describe my-key --keyring=my-keyring --location=global", True),
    ("gcloud kms keys create my-key --keyring=my-keyring --location=global --purpose=encryption", False),
    ("gcloud kms decrypt --key=my-key --keyring=my-keyring --location=global --ciphertext-file=cipher.enc --plaintext-file=plain.txt", False),
    ("gcloud kms encrypt --key=my-key --keyring=my-keyring --location=global --plaintext-file=plain.txt --ciphertext-file=cipher.enc", False),
    # gcloud pubsub (depth 2 - default)
    ("gcloud pubsub topics list", True),
    ("gcloud pubsub topics describe my-topic", True),
    ("gcloud pubsub topics create my-topic", False),
    ("gcloud pubsub topics delete my-topic", False),
    ("gcloud pubsub topics publish my-topic --message='hello'", False),
    ("gcloud pubsub subscriptions list", True),
    ("gcloud pubsub subscriptions describe my-sub", True),
    ("gcloud pubsub subscriptions create my-sub --topic=my-topic", False),
    ("gcloud pubsub subscriptions pull my-sub", False),
    # gcloud with global flags
    ("gcloud --project=my-project compute instances list", True),
    ("gcloud --format=json compute instances list", True),
    ("gcloud --account=user@example.com compute instances list", True),
    ("gcloud --configuration=my-config compute instances list", True),
    ("gcloud --region=us-central1 compute instances list", True),
    ("gcloud --zone=us-central1-a compute instances list", True),
    ("gcloud --project=my-project --format=json compute instances describe my-instance", True),
    ("gcloud --project=my-project compute instances delete my-instance", False),
    # gcloud help/info/version/init
    ("gcloud help", True),
    ("gcloud help compute", True),
    ("gcloud help compute instances", True),
    ("gcloud info", True),
    ("gcloud info --run-diagnostics", True),
    ("gcloud info --show-log", True),
    ("gcloud version", True),
    ("gcloud version --help", True),
    ("gcloud init", False),
    ("gcloud init --skip-diagnostics", False),
    ("gcloud feedback", False),
    ("gcloud topic configurations", True),  # help topic
    # gcloud - edge cases
    ("gcloud compute instances", False),  # incomplete - no action
    ("gcloud compute", False),  # incomplete - no resource or action
    ("gcloud", False),  # incomplete - no command at all
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
