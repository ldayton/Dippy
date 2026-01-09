"""Test cases for google cloud cli (gcloud)."""

import pytest

from conftest import is_approved, needs_confirmation

#
# ==========================================================================
# Google Cloud CLI (gcloud)
# ==========================================================================
#
TESTS = [
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
    (
        "gcloud iam list-grantable-roles //cloudresourcemanager.googleapis.com/projects/my-project",
        True,
    ),
    # gcloud iam - service accounts
    ("gcloud iam service-accounts list", True),
    ("gcloud iam service-accounts describe sa@project.iam.gserviceaccount.com", True),
    ("gcloud iam service-accounts create my-sa", False),
    ("gcloud iam service-accounts delete sa@project.iam.gserviceaccount.com", False),
    (
        "gcloud iam service-accounts add-iam-policy-binding sa@project.iam.gserviceaccount.com --member=user:foo --role=roles/iam.serviceAccountUser",
        False,
    ),
    (
        "gcloud iam service-accounts set-iam-policy sa@project.iam.gserviceaccount.com policy.json",
        False,
    ),
    (
        "gcloud iam service-accounts keys list --iam-account=sa@project.iam.gserviceaccount.com",
        True,
    ),
    (
        "gcloud iam service-accounts keys create key.json --iam-account=sa@project.iam.gserviceaccount.com",
        False,
    ),
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
    (
        "gcloud secrets versions access 1 --secret=my-secret",
        False,
    ),  # accessing secret data
    ("gcloud secrets versions destroy 1 --secret=my-secret", False),
    (
        "gcloud secrets add-iam-policy-binding my-secret --member=user:foo --role=roles/secretmanager.secretAccessor",
        False,
    ),
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
    (
        "gcloud dns record-sets create www --zone=my-zone --type=A --rrdatas=1.2.3.4",
        False,
    ),
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
    (
        "gcloud run services update my-service --region=us-central1 --memory=512Mi",
        False,
    ),
    ("gcloud run services delete my-service --region=us-central1", False),
    ("gcloud run deploy my-service --image=gcr.io/my-project/my-image", False),
    ("gcloud run revisions list --service=my-service", True),
    ("gcloud run revisions describe my-revision", True),
    # gcloud artifacts (depth 3)
    ("gcloud artifacts repositories list", True),
    ("gcloud artifacts repositories describe my-repo --location=us-central1", True),
    ("gcloud artifacts repositories create my-repo --location=us-central1", False),
    ("gcloud artifacts repositories delete my-repo --location=us-central1", False),
    (
        "gcloud artifacts docker images list us-central1-docker.pkg.dev/my-project/my-repo",
        True,
    ),
    (
        "gcloud artifacts docker tags list us-central1-docker.pkg.dev/my-project/my-repo/my-image",
        True,
    ),
    (
        "gcloud artifacts docker tags delete us-central1-docker.pkg.dev/my-project/my-repo/my-image:v1",
        False,
    ),
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
    (
        "gcloud iap web get-iam-policy --resource-type=backend-services --service=my-service",
        True,
    ),
    (
        "gcloud iap web set-iam-policy policy.json --resource-type=backend-services",
        False,
    ),
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
    (
        "gcloud sql export sql my-instance gs://my-bucket/dump.sql --database=mydb",
        False,
    ),
    ("gcloud sql import sql my-instance gs://my-bucket/dump.sql", False),
    # gcloud kms (depth 2 - default)
    ("gcloud kms keyrings list --location=global", True),
    ("gcloud kms keyrings describe my-keyring --location=global", True),
    ("gcloud kms keyrings create my-keyring --location=global", False),
    ("gcloud kms keys list --keyring=my-keyring --location=global", True),
    ("gcloud kms keys describe my-key --keyring=my-keyring --location=global", True),
    (
        "gcloud kms keys create my-key --keyring=my-keyring --location=global --purpose=encryption",
        False,
    ),
    (
        "gcloud kms decrypt --key=my-key --keyring=my-keyring --location=global --ciphertext-file=cipher.enc --plaintext-file=plain.txt",
        False,
    ),
    (
        "gcloud kms encrypt --key=my-key --keyring=my-keyring --location=global --plaintext-file=plain.txt --ciphertext-file=cipher.enc",
        False,
    ),
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
    (
        "gcloud --project=my-project --format=json compute instances describe my-instance",
        True,
    ),
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
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_gcloud(check, command: str, expected: bool) -> None:
    """Test command safety."""
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approved for: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirmation for: {command}"
