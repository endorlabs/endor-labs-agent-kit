#!/usr/bin/env bash
# Build and publish the Endor AURI Agent container image that the
# Marketplace Terraform (main.tf, var.container_image) deploys to Cloud Run.
#
# Run once per release from a machine with gcloud + access to the publishing
# project. The image must be readable by the customer projects that deploy it
# (publish to a public Artifact Registry, or the Marketplace container path).
#
#   PROJECT=endor-labs-marketplace-public REGION=us-central1 TAG=v1 ./build_and_push_image.sh
#
set -euo pipefail

PROJECT="${PROJECT:?set PROJECT to the publishing GCP project}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-endor-agents}"
TAG="${TAG:-v1}"

HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$(cd "$HERE/../.." && pwd)"   # gemini-enterprise/ (has the Dockerfile)
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/oss-a2ui:${TAG}"

echo "Building A2A/A2UI image from: $SRC"
echo "Target image:                $IMAGE"

gcloud artifacts repositories create "$REPO" \
  --repository-format=docker --location="$REGION" --project="$PROJECT" \
  --description="Endor Gemini Enterprise agents" 2>/dev/null || true

gcloud builds submit "$SRC" --tag "$IMAGE" --project="$PROJECT"

echo "Published: $IMAGE"
echo "Set var.container_image to this value (or update the default in variables.tf)."
