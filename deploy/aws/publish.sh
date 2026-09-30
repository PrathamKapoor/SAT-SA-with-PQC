#!/usr/bin/env bash
# Publish the current Git commit to the SAT-SA AWS stack and deploy it.
#
#   deploy/aws/publish.sh [--stack satsa-prod] [--no-deploy]
#
# Needs: git (clean tree), docker (buildx), aws CLI authenticated for the
# account (an SSO/IAM session locally, or the OIDC deploy role in CI).
# Identity of a deployment = the Git commit: images are tagged with its first
# 12 characters (ECR tags are immutable), and the deployment bundle is
# `git archive` of deploy/ at that commit, so nothing uncommitted can ship.
set -euo pipefail

STACK=satsa-prod
DEPLOY=1
while [ $# -gt 0 ]; do
  case "$1" in
    --stack) STACK=$2; shift 2 ;;
    --no-deploy) DEPLOY=0; shift ;;
    *) echo "unknown argument $1" >&2; exit 2 ;;
  esac
done

die() { echo "publish: FAILED: $*" >&2; exit 1; }
ROOT=$(git rev-parse --show-toplevel)
cd "$ROOT"
[ -z "$(git status --porcelain --untracked-files=no)" ] || die "working tree has uncommitted changes"
COMMIT=$(git rev-parse HEAD)
TAG=${COMMIT:0:12}

output() {
  aws cloudformation describe-stacks --stack-name "$STACK" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}
BACKEND=$(output BackendRepositoryUri); WEB=$(output WebRepositoryUri)
BUCKET=$(output BucketName); INSTANCE=$(output InstanceId); SITE=$(output SiteAddress)
[ -n "$BACKEND" ] && [ -n "$INSTANCE" ] || die "stack $STACK outputs not found"
REGION=$(aws configure get region || true)
REGION=${AWS_REGION:-${REGION:-ap-south-1}}

aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "${BACKEND%%/*}" >/dev/null

# Build from an exact export of the commit (LF endings, nothing uncommitted),
# never from the working tree.
SRC=$(mktemp -d)
trap 'rm -rf "$SRC"' EXIT
git -c core.autocrlf=false archive --format=tar "$COMMIT" | tar -xf - -C "$SRC"

push_image() {  # repo context dockerfile-dir
  local repo=$1 context=$2
  if aws ecr describe-images --repository-name "${repo#*/}" --image-ids imageTag="$TAG" --region "$REGION" >/dev/null 2>&1; then
    echo "publish: $repo:$TAG already in ECR"
    return
  fi
  docker build --pull --platform linux/amd64 \
    --build-arg "SATSA_RELEASE=$COMMIT" \
    --label "org.opencontainers.image.revision=$COMMIT" -t "$repo:$TAG" "$context"
  docker push --quiet "$repo:$TAG"
}
push_image "$BACKEND" "$SRC"
push_image "$WEB" "$SRC/web"

bundle=$(mktemp -d)
git -c core.autocrlf=false archive --format=tar.gz -o "$bundle/deploy.tgz" "$COMMIT"   deploy web/e2e web/playwright.config.ts docs/demo/submissions
(cd "$bundle" && sha256sum deploy.tgz > deploy.tgz.sha256)
aws s3 cp --only-show-errors "$bundle/deploy.tgz" "s3://$BUCKET/releases/$COMMIT/deploy.tgz"
aws s3 cp --only-show-errors "$bundle/deploy.tgz.sha256" "s3://$BUCKET/releases/$COMMIT/deploy.tgz.sha256"
rm -rf "$bundle"
echo "publish: $COMMIT published (images $TAG, bundle s3://$BUCKET/releases/$COMMIT/)"

[ "$DEPLOY" = 1 ] || exit 0
remote="set -euo pipefail; d=/opt/satsa/releases/$COMMIT; mkdir -p \$d; cd \$d;"
remote+=" aws s3 cp --only-show-errors s3://$BUCKET/releases/$COMMIT/deploy.tgz deploy.tgz;"
remote+=" aws s3 cp --only-show-errors s3://$BUCKET/releases/$COMMIT/deploy.tgz.sha256 deploy.tgz.sha256;"
remote+=" sha256sum -c --quiet deploy.tgz.sha256; tar -xzf deploy.tgz;"
remote+=" bash deploy/aws/deploy.sh deploy $COMMIT"
params=$(python3 -c 'import json,sys; print(json.dumps({"commands":[sys.argv[1]],"executionTimeout":["1800"]}))' "$remote")
cid=$(aws ssm send-command --region "$REGION" --instance-ids "$INSTANCE" \
  --document-name AWS-RunShellScript --comment "SAT-SA deploy $TAG" \
  --parameters "$params" --query Command.CommandId --output text)
echo "publish: deploying through SSM (command $cid)"
while :; do
  status=$(aws ssm get-command-invocation --region "$REGION" --command-id "$cid" --instance-id "$INSTANCE" \
    --query Status --output text 2>/dev/null || echo Pending)
  case "$status" in Pending|InProgress|Delayed) sleep 10 ;; *) break ;; esac
done
aws ssm get-command-invocation --region "$REGION" --command-id "$cid" --instance-id "$INSTANCE" \
  --query '[StandardOutputContent,StandardErrorContent]' --output text | tail -n 60
[ "$status" = Success ] || die "deployment on $INSTANCE ended $status"
echo "publish: deployed $COMMIT to https://$SITE"
