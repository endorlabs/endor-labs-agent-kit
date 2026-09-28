# Sample values for testing the Marketplace deployment parameters.
# Provide your own project, image, and Secret Manager secret IDs.
goog_cm_deployment_name    = "endor-auri-test"
project_id                 = "REPLACE_WITH_YOUR_PROJECT_ID"
region                     = "us-central1"
ENDOR_OSS_VM               = "us-central1-docker.pkg.dev/YOUR_PUBLISHER_PROJECT/endor-agents/oss-a2ui@sha256:REPLACE_WITH_PUBLISHED_DIGEST"
endor_api_key_secret_id    = "endor-oss-api-key"
endor_api_secret_secret_id = "endor-oss-api-secret"
oss_router                 = "rule"
machine_type               = "e2-standard-2"
