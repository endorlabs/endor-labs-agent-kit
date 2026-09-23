variable "project_id" {
  description = "The customer project ID in which to deploy the Endor AURI Agent."
  type        = string
}

# Marketplace requires this variable name to be declared.
variable "goog_cm_deployment_name" {
  description = "The name of the Marketplace deployment (used to name the Cloud Run service + VM)."
  type        = string
}

variable "region" {
  description = "The GCP region for the Cloud Run service."
  type        = string
  default     = "us-central1"
}

variable "container_image" {
  description = "The published Endor AURI Agent (A2UI) container image to run on Cloud Run."
  type        = string
  default     = "us-central1-docker.pkg.dev/endor-labs-marketplace-public/endor-agents/oss-a2ui:v1"
}

variable "oss_router" {
  description = "Question router: 'rule' (deterministic, no model key) or 'model' (Gemini tool-calling)."
  type        = string
  default     = "rule"
}

# -- Endor credential (from the customer's Secret Manager; never in state) ------
variable "endor_api_key_secret_id" {
  description = "Secret Manager secret ID (in this project) holding the Endor API key."
  type        = string
}

variable "endor_api_secret_secret_id" {
  description = "Secret Manager secret ID (in this project) holding the Endor API secret."
  type        = string
}

variable "endor_api_base_url" {
  description = "Endor API base URL."
  type        = string
  default     = "https://api.endorlabs.com"
}

# -- Placeholder compute instance (Marketplace validation requirement) ---------
# The agent runs on Cloud Run, not here. Keep this small; it is idle.
variable "machine_type" {
  description = "Machine type for the placeholder compute instance (the agent does not run on it)."
  type        = string
  default     = "e2-standard-2"
}

variable "zone" {
  description = "The GCP zone for the placeholder compute instance."
  type        = string
  default     = "us-central1-a"
}

variable "boot_disk_size" {
  description = "Size of the boot disk (GB)."
  type        = number
  default     = 10
}

variable "boot_disk_type" {
  description = "Type of the boot disk."
  type        = string
  default     = "pd-balanced"
}

variable "source_image" {
  description = "Source image for the boot disk."
  type        = string
  default     = "projects/debian-cloud/global/images/family/debian-12"
}

variable "networks" {
  description = "List of networks to attach to."
  type        = list(string)
  default     = ["default"]
}

variable "sub_networks" {
  description = "List of sub-networks to attach to."
  type        = list(string)
  default     = []
}

variable "external_ips" {
  description = "List of external IPs (or 'NONE'/'EPHEMERAL')."
  type        = list(string)
  default     = ["NONE"]
}

variable "enable_cloud_api" {
  description = "Enable the cloud-platform API scope on the placeholder instance."
  type        = bool
  default     = false
}
