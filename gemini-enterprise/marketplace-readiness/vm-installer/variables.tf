variable "project_id" {
  description = "The customer project ID to deploy into."
  type        = string
}

# Marketplace requires this variable name to be declared.
variable "goog_cm_deployment_name" {
  description = "Deployment name (used to name the VM, service accounts, and Cloud Run service)."
  type        = string
}

variable "region" {
  description = "Region for the Cloud Run service and VM."
  type        = string
  default     = "us-central1"
}

variable "container_image" {
  description = "The published Endor AURI for Developers container image (immutable @sha256 digest)."
  type        = string
  default     = "us-central1-docker.pkg.dev/YOUR_PUBLISHER_PROJECT/endor-agents/oss-a2ui@sha256:REPLACE_WITH_PUBLISHED_DIGEST"
}

# --- Gemini Enterprise registration -----------------------------------------
variable "ge_engine_id" {
  description = "Full Gemini Enterprise engine resource path to register the agent into (projects/<num>/locations/global/collections/default_collection/engines/<engine>). Leave empty to skip auto-registration and register manually."
  type        = string
  default     = ""
}

variable "agent_display_name" {
  description = "Display name for the agent in Gemini Enterprise."
  type        = string
  default     = "Endor AURI for Developers"
}

# --- Endor credential --------------------------------------------------------
variable "endor_api_key_secret_id" {
  description = "Secret Manager secret ID to hold the Endor API key (created by this bundle)."
  type        = string
  default     = "endor-oss-api-key"
}

variable "endor_api_secret_secret_id" {
  description = "Secret Manager secret ID to hold the Endor API secret (created by this bundle)."
  type        = string
  default     = "endor-oss-api-secret"
}

variable "endor_api_key" {
  description = "Endor API key value to seed. Leave as the placeholder to add the real key AFTER deploy/registration."
  type        = string
  default     = "REPLACE_ME"
  sensitive   = true
}

variable "endor_api_secret" {
  description = "Endor API secret value to seed. Leave as the placeholder to add the real value AFTER deploy/registration."
  type        = string
  default     = "REPLACE_ME"
  sensitive   = true
}

variable "oss_router" {
  description = "Question router: 'rule' (deterministic, no model key) or 'model'."
  type        = string
  default     = "rule"
}

variable "endor_api_base_url" {
  description = "Endor API base URL."
  type        = string
  default     = "https://api.endorlabs.com"
}

# --- Installer VM ------------------------------------------------------------
variable "machine_type" {
  description = "Machine type for the installer VM (small; it only bootstraps)."
  type        = string
  default     = "e2-small"
}

variable "zone" {
  description = "Zone for the installer VM."
  type        = string
  default     = "us-central1-a"
}

variable "boot_disk_size" {
  description = "Boot disk size (GB)."
  type        = number
  default     = 20
}

variable "boot_disk_type" {
  description = "Boot disk type."
  type        = string
  default     = "pd-balanced"
}

variable "source_image" {
  description = "Boot image for the installer VM (Marketplace-licensed VM image)."
  type        = string
  default     = "projects/YOUR_PUBLISHER_PROJECT/global/images/endor-auri-vm-licensed"
}

variable "networks" {
  description = "Network(s) to attach the VM to."
  type        = list(string)
  default     = ["default"]
}
