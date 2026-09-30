# SAT-SA on AWS (single EC2, ap-south-1)

```
internet ──80/443──> Elastic IP ─> EC2 (Amazon Linux 2023, no SSH)
                                   ├─ caddy  :80/:443  (Let's Encrypt, security headers)
                                   ├─ web    (Next.js, server-side API client)
                                   ├─ api    (FastAPI, private)
                                   ├─ worker (queue, LangGraph, TRUST-SAT, MLOps jobs)
                                   └─ /data  = separate encrypted EBS volume
                                        └─ satsa/  ledger, ML-DSA-65 key, identity ledger
EC2 ──5432 (TLS verify-full)──> RDS PostgreSQL 17, private subnets, encrypted
EC2 ──S3 gateway endpoint────> S3 bucket (private, versioned, SSE-KMS)
```

Everything is defined in `satsa.cfn.yaml` (one CloudFormation stack). The
application runs the same `deploy/compose.production.yml` as every other
environment, with `compose.aws.yml` swapping the database for RDS, storage for
S3 via the instance role, `/data` for the EBS mount, images for ECR and logs
for CloudWatch.

Not in this design (future work, not needed for one instance): ALB, ECS,
Fargate, EFS, CloudFront, WAF, Multi-AZ RDS, KMS/HSM signing.

## What is where

| Concern | Where |
|---|---|
| Database password | Generated and rotated by RDS in Secrets Manager (`ManageMasterUserPassword`); read at deploy time by the instance role |
| Bootstrap admin credential | Secrets Manager `satsa/<env>/admin-credential`, written once by `deploy.sh bootstrap-admin`, never printed |
| S3 access | Instance role only; no access keys anywhere |
| Runtime env file | `/etc/satsa/production.env` on the instance, `0600`, rendered by `deploy.sh`; never committed |
| TRUST-SAT signing key | `/data/satsa/keys/satsa_trust_key.json` on the EBS volume, owner UID 10001, mode 0700 directory; never in an image or Git |
| Container images | ECR `satsa-<env>/backend` and `satsa-<env>/web`, immutable tags = first 12 characters of the Git commit |
| Deployed version | `/etc/satsa/deployed.json` (commit, tags, time) |
| Logs | CloudWatch Logs group `/satsa/<env>` (one stream per container) |

## First deployment

Prerequisites: AWS CLI v2 signed in to the target account with permission to
create the stack (VPC, EC2, RDS, S3, ECR, IAM, Secrets Manager, CloudWatch),
Docker with buildx, Git with a clean checkout of the commit to deploy.

```bash
aws cloudformation deploy --region ap-south-1 --stack-name satsa-prod \
  --template-file deploy/aws/satsa.cfn.yaml --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides EnvironmentName=prod \
    GitHubRepository=PrathamKapoor/SAT-SA-with-PQC CreateGitHubOidcProvider=true
# (optional) SiteAddress=satsa.example.org AlarmEmail=ops@example.org

deploy/aws/publish.sh --stack satsa-prod      # build, push, bundle, deploy via SSM
aws ssm send-command --instance-ids <InstanceId> --document-name AWS-RunShellScript \
  --parameters 'commands=["bash /opt/satsa/current/deploy/aws/deploy.sh bootstrap-admin"]'
```

The site is at the stack output `SiteAddress`. Without a domain it is
`<elastic-ip-with-dashes>.sslip.io`, a public DNS name that resolves to the
Elastic IP, so Caddy obtains a real certificate. To use a domain: create an A
record for it pointing to `PublicIp`, update the stack with
`SiteAddress=<domain>`, and run `publish.sh` again.

The administrator credential: `aws secretsmanager get-secret-value --secret-id
satsa/prod/admin-credential`. Sign in with it and invite members from the
workbench.

## Deploying a new version

`deploy/aws/publish.sh` from a clean checkout, or the **Deploy to AWS**
workflow (manual, `main` only, GitHub OIDC; set the repository variable
`AWS_DEPLOY_ROLE_ARN` to the stack output `DeployRoleArn` and protect the
`aws-prod` environment with a required reviewer).

`deploy.sh deploy <commit>` on the instance: mounts and checks `/data`,
verifies the release bundle checksum, renders the env file from Secrets
Manager, refuses to continue if an initialized volume lost its signing key,
pulls the commit's images, runs migrations (fails if RDS is unreachable),
initializes the TRUST-SAT key only on a new volume, starts the services, and
waits until API, worker and web are healthy and the public HTTPS URL answers.
Any failed step stops the deployment.

## Administration (Session Manager, no SSH)

Port 22 is closed. The instance role has `AmazonSSMManagedInstanceCore`, and
Amazon Linux 2023 ships the SSM agent.

```bash
aws ssm start-session --target <InstanceId>            # interactive shell
sudo bash /opt/satsa/current/deploy/aws/deploy.sh status
sudo docker compose -p satsa ... logs api               # or CloudWatch Logs
```

Emergency: if the agent is unreachable, use the EC2 serial console (enable it
for the account first) or stop the instance and attach its volumes to a rescue
instance. Never open port 22 on the security group.

## Backup and restore

* RDS automated backups: 7 days of point-in-time recovery (stack parameter).
* S3: versioning; noncurrent versions expire after 90 days.
* `/data`: EBS snapshots.

`deploy.sh snapshot` takes a coordinated pair: it stops the API and worker (no
application writes), creates the RDS snapshot and the EBS snapshot, waits for
the RDS snapshot, restarts, and records both identifiers in
`/etc/satsa/snapshots.jsonl`. The two snapshots are not one atomic operation;
what makes them consistent is that nothing writes between them.

Restore order: (1) restore the RDS snapshot to a new instance and point the
stack at it (or restore in place under the same identifier); (2) create a
volume from the EBS snapshot and attach it at `/dev/sdf` in place of the data
volume; (3) restore S3 objects to the matching versions if they were deleted;
(4) `deploy.sh deploy <commit>` of the version that wrote the backup; (5)
verify a finalized run with TRUST-SAT. Restoring only one of the pair breaks
the ledger/database correspondence; restore both from the same snapshot pair.

This is not tested disaster recovery in another region: the stack is single
region and single instance.

## Rollback

Deploy the previous commit: `publish.sh` from that commit (its images are
already in ECR) or `deploy.sh deploy <previous-commit>` on the instance.
Migrations are forward-only; rolling back across a schema migration needs the
coordinated snapshot taken before the upgrade.

## Monitoring

CloudWatch: container logs, alarms for EC2 status checks, `/data` above 80 %
(CloudWatch agent, namespace `SATSA/Host`), RDS CPU above 80 % for 15 minutes,
RDS free storage below 2 GiB, and worker failures (log metric filter). Alarm
notifications go to the stack's SNS topic (`AlarmEmail`).

## Limitations

* One instance, one availability zone: an instance or AZ failure stops the
  service until it is replaced; data survives in RDS, EBS snapshots and S3.
* The signing key lives on the EBS volume, protected by file permissions and
  EBS encryption; there is no KMS or HSM signing.
* No claim of NCIIPC or government-cloud approval is made.
