# Sample values for testing the Marketplace deployment parameters.
# Provide your own project, image, and Secret Manager secret IDs.
goog_cm_deployment_name    = "endor-auri-test"
project_id                 = "REPLACE_WITH_YOUR_PROJECT_ID"
region                     = "us-central1"
container_image            = "us-central1-docker.pkg.dev/REPLACE_WITH_YOUR_PROJECT_ID/endor-agents/oss-a2ui:v1"
endor_api_key_secret_id    = "endor-oss-api-key"
endor_api_secret_secret_id = "endor-oss-api-secret"
oss_router                 = "rule"
machine_type               = "e2-standard-2"
