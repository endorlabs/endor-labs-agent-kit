#!/usr/bin/env bash
# Build and publish the Endor AURI for Developers container image that the
# Marketplace Terraform (main.tf, var.container_image) deploys to Cloud Run.
#
# The image is built from a COMMITTED git ref (default HEAD), not the working
# tree, so the published artifact is reproducible and no uncommitted work-in-
# progress can leak in. After publishing, the script resolves and prints the
# image's immutable @sha256 digest — pin that in variables.tf (var.container_image).
#
# Run once per release from a machine with gcloud + access to the publishing
# project. The image must be readable by the customer projects that deploy it
# (publish to a public Artifact Registry, or the Marketplace container path).
#
#   PROJECT=endor-labs-marketplace-public GIT_REF=agents-v2.3.0 TAG=v1 ./build_and_push_image.sh
#
set -euo pipefail

PROJECT="${PROJECT:?set PROJECT to the publishing GCP project}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-endor-agents}"
TAG="${TAG:-v1}"
GIT_REF="${GIT_REF:-HEAD}"   # a tag/branch/commit to build from (must be committed)

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(git -C "$HERE" rev-parse --show-toplevel)"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/oss-a2ui:${TAG}"

# Resolve the ref to a concrete commit and export ONLY the committed
# gemini-enterprise/ subtree (which holds the Dockerfile) to a temp context.
# `git archive` never includes uncommitted or untracked files, so the build is
# reproducible from $COMMIT regardless of the local working-tree state.
COMMIT="$(git -C "$REPO_ROOT" rev-parse --short "$GIT_REF")"
if ! git -C "$REPO_ROOT" diff --quiet || ! git -C "$REPO_ROOT" diff --cached --quiet; then
  echo "note: working tree has uncommitted changes — they are EXCLUDED (building from committed $GIT_REF / $COMMIT)." >&2
fi
CTX="$(mktemp -d)"
trap 'rm -rf "$CTX"' EXIT
git -C "$REPO_ROOT" archive "$GIT_REF" gemini-enterprise | tar -x -C "$CTX"
BUILD_CTX="$CTX/gemini-enterprise"

echo "Building A2A/A2UI image"
echo "  from committed ref: $GIT_REF ($COMMIT)"
echo "  build context:      $BUILD_CTX"
echo "  target tag:         $IMAGE"

gcloud artifacts repositories create "$REPO" \
  --repository-format=docker --location="$REGION" --project="$PROJECT" \
  --description="Endor Gemini Enterprise agents" 2>/dev/null || true

gcloud builds submit "$BUILD_CTX" --tag "$IMAGE" --project="$PROJECT"

# Resolve the immutable digest so the Terraform can pin by content, not by a
# mutable tag. Customers then always pull the exact validated bits.
DIGEST="$(gcloud artifacts docker images describe "$IMAGE" \
  --project="$PROJECT" --format='value(image_summary.digest)')"
PINNED="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/oss-a2ui@${DIGEST}"

echo
echo "Published:"
echo "  tag:    $IMAGE"
echo "  digest: $PINNED"
echo
echo "Pin the DIGEST as var.container_image (edit the default in variables.tf):"
echo "  default = \"$PINNED\""
