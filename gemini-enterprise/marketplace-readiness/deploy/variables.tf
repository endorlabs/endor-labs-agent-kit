variable "project_id" {
  description = "The customer project ID in which to deploy the Endor AURI Agent."
  type        = string
}

# Marketplace requires this variable name to be declared.
variable "goog_cm_deployment_name" {
  description = "The name of the Marketplace deployment."
  type        = string
}

variable "agent_engine_name" {
  description = "The name of the Agent Engine application."
  type        = string
  default     = "endor-auri-agent"
}

variable "region" {
  description = "The GCP region for the Agent Engine deployment."
  type        = string
  default     = "us-central1"
}

variable "agent_package_name" {
  description = "The name of the Python package inside assets/source.tar.gz (set by package_agent.py)."
  type        = string
  default     = "endor_oss"
}

# -- Endor credential (injected via Secret Manager, never stored in state) -----
variable "endor_api_key_secret_id" {
  description = "Secret Manager secret ID (in the deployment project) holding the Endor API key."
  type        = string
}

variable "endor_api_secret_secret_id" {
  description = "Secret Manager secret ID (in the deployment project) holding the Endor API secret."
  type        = string
}

variable "endor_api_base_url" {
  description = "Endor API base URL."
  type        = string
  default     = "https://api.endorlabs.com"
}

variable "oss_router" {
  description = "Question router: 'rule' (deterministic, no model key) or 'model' (Gemini tool-calling)."
  type        = string
  default     = "model"
}

# -- Placeholder compute instance (Marketplace validation requirement) ---------
# The agent runs on Agent Engine, not here. Keep this small; it is idle.
variable "machine_type" {
  description = "Machine type for the placeholder compute instance. The agent does not run on it, so a small type is sufficient (e.g. e2-standard-2 = 2 vCPU / 8 GB). Use e2-standard-4 (4 vCPU / 16 GB) or e2-custom-4-8192 (4 vCPU / 8 GB) only if a larger placeholder is required."
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
