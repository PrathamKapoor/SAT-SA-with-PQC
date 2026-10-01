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

## Custom domain

1. At the domain's DNS provider, create `A <hostname> -> <ElasticIp>` (stack
   output) and wait until it resolves publicly.
2. `aws cloudformation update-stack --stack-name satsa-prod --use-previous-template
   --capabilities CAPABILITY_NAMED_IAM --parameters ParameterKey=SiteAddress,ParameterValue=<hostname>`
   (with `UsePreviousValue=true` for every other parameter). This only updates
   the SSM parameter `/satsa/<environment>/site-address`; the instance is not
   touched.
3. `deploy.sh deploy <current commit>`: Caddy serves the hostname as the
   primary address and obtains its Let's Encrypt certificate; the sslip.io
   name keeps working as an alias.

## Which version is running

The release is the Git commit. `publish.sh` builds both images with
`SATSA_RELEASE=<commit>` and tags them with its first 12 characters;
`deploy.sh deploy` records the commit in `/etc/satsa/deployed.json`. The API
reports it at `GET /health/live` (`"release"`), and the workbench shows the API
and interface releases on **Admin > System**. `deploy.sh status` prints all
three; after a deployment they are the same commit. There is no separate
semantic version.

## Administration (Session Manager, no SSH)

Port 22 is closed. The instance role has `AmazonSSMManagedInstanceCore`, and
Amazon Linux 2023 ships the SSM agent.

```bash
aws ssm start-session --target <InstanceId>             # interactive shell
D="sudo bash /opt/satsa/current/deploy/aws/deploy.sh"
$D status                  # deployed commit, container health, running releases
$D logs worker 300         # last 300 lines of one service
$D restart                 # restart api, worker, web and caddy; waits for health
$D restart worker          # one service
```

Container logs also go to CloudWatch Logs, log group `/satsa/<environment>`,
one stream per container. API lines carry `request_id`, `organization_id`,
`route` and `status_code`; worker lines carry `run_id` (and the job or model
job identifiers), so a failed request can be followed to the run it created.

### Recovering a failed worker

Docker restarts a worker that exits (`restart: unless-stopped`). Work it had
claimed is leased: when the lease lapses the next poll claims it again, and a
LangGraph run resumes from its last checkpoint in PostgreSQL. Check with
`$D logs worker` and `$D status`; if it stays unhealthy, `$D restart worker`.
A run that failed stays failed (its record is kept); start a new run on the
same submission version from the workbench.

### Rotating secrets

* Administrator credential: sign in as the administrator, add a new
  administrator member from **Members**, store its credential with
  `aws secretsmanager put-secret-value --secret-id satsa/prod/admin-credential`
  (same JSON shape: `organization_id`, `credential`), sign in with it, then
  revoke the old administrator member. Revoking the membership only removes
  the old identity from that one organization; it stays an administrator of
  every organization it created (demo organizations), so also revoke the old
  credential itself with `DELETE /api/v1/session` sent with the raw old
  credential as Bearer (this also ends its sessions), and confirm it now gets
  401. Replace the `admin` field of `/root/satsa-e2e/credentials.json`, which
  keeps its own copy. The new administrator is not a member of the earlier
  demo organizations; their records stay, unreachable through the UI.
  Credentials live only in Secrets Manager (and the root-only files on the
  instance named in this runbook); never commit, paste or log one. If a
  credential is ever shown anywhere, rotate it this way, and rerun `$D demo`
  (which revokes the previous demo members) before any public demo.
* RDS master password: managed by RDS in Secrets Manager
  (`ManageMasterUserPassword`); after a rotation run `$D deploy <current
  commit>`, which renders the new password into the env file.
* Model providers: update `satsa/prod/llm-providers` (docs/LLM.md), then
  `$D deploy <current commit>` so the worker's `/etc/satsa/llm.env` is
  rendered again. Keys reach only the worker, never the browser or the API.

### Demo organization

`$D demo` creates a new organization named "SAT-SA demo (synthetic data)
<time>", adds an analyst, supervisor, auditor and viewer, loads the five
synthetic CSE submissions in `docs/demo/submissions` through the API, lets the
worker analyse them, records one supervisory decision and verifies its
TRUST-SAT receipt. The members' credentials are written to
`/root/satsa-demo/state.json` (root only). Running it again is the reset: the
previous demo members are revoked and a new demo organization is created. No
record is deleted, and demo data never enters another organization.

Emergency: if the agent is unreachable, use the EC2 serial console (enable it
for the account first) or stop the instance and attach its volumes to a rescue
instance. Never open port 22 on the security group.

## Backup and restore

* RDS automated backups: point-in-time recovery for `DbBackupRetentionDays`
  (1 day on the AWS Free plan, which caps it; raise it on a paid plan).
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
region and single instance. The drill actually exercised is recorded in
docs/backup-restore.md.

### Instance failure

Data is not on the instance's root disk: it is in RDS, S3 and the `/data`
EBS volume. If the instance is lost, let the stack create a new instance
(update or recreate the instance resource), attach the same `/data` volume or
one made from the latest EBS snapshot, and run `$D deploy <commit>` with the
commit of the last deployment (the newest `releases/` prefix in the bucket).

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
