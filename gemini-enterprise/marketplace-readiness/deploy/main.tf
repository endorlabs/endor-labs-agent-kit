terraform {
  required_providers {
    google   = { source = "hashicorp/google" }
    external = { source = "hashicorp/external" }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ---------------------------------------------------------------------------
# 1. Endor AURI Agent on Vertex AI Agent Engine
#    (the actual, managed workload; autoscaled by Agent Engine)
# ---------------------------------------------------------------------------
module "agent_engine" {
  # Vendored locally to relax the Terraform version constraint to >= 1.5.7,
  # matching the Marketplace deployment runtime. Upstream:
  # github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/agent-engine
  source     = "./modules/agent-engine"
  name       = var.agent_engine_name
  project_id = var.project_id
  region     = var.region

  agent_engine_config = {
    agent_framework = "google-adk"

    # Non-secret configuration. Models serve from the `global` endpoint, so the
    # agent uses GOOGLE_CLOUD_LOCATION=global regardless of the Agent Engine region.
    environment_variables = {
      GOOGLE_GENAI_USE_VERTEXAI = "1"
      GOOGLE_CLOUD_LOCATION     = "global"
      OSS_CLIENT                = "rest"
      OSS_ROUTER                = var.oss_router
      ENDOR_API_BASE_URL        = var.endor_api_base_url
    }

    # The Endor API credential is injected from the customer's Secret Manager at
    # runtime (SecretRef), never stored in plain config or Terraform state. The
    # agent reads these env vars via its normal credential loader.
    secret_environment_variables = {
      ENDOR_API_CREDENTIALS_KEY = {
        secret_id = var.endor_api_key_secret_id
        version   = "latest"
      }
      ENDOR_API_CREDENTIALS_SECRET = {
        secret_id = var.endor_api_secret_secret_id
        version   = "latest"
      }
    }
  }

  # The agent engine runs as a dedicated service account with least-privilege
  # roles, including read access to the Endor credential secrets.
  service_account_config = {
    create = true
    roles = [
      "roles/aiplatform.user",
      "roles/serviceusage.serviceUsageConsumer",
      "roles/cloudtrace.agent",
      "roles/secretmanager.secretAccessor",
    ]
  }

  deployment_files = {
    source_config = {
      source_path       = "assets/source.tar.gz"
      entrypoint_module = "${var.agent_package_name}.app"
      entrypoint_object = "agent"
      requirements_path = "${var.agent_package_name}/requirements.txt"
    }
  }
}

# ---------------------------------------------------------------------------
# 2. Placeholder compute instance
#    Google's current Marketplace VM-listing validation requires a compute
#    instance in the deployment. The Endor AURI Agent does NOT run here (it runs
#    on Agent Engine above); this is a minimal, idle placeholder. Keep it small.
# ---------------------------------------------------------------------------
locals {
  network_interfaces = [for i, n in var.networks : {
    network     = n
    subnetwork  = length(var.sub_networks) > i ? element(var.sub_networks, i) : null
    external_ip = length(var.external_ips) > i ? element(var.external_ips, i) : "NONE"
  }]

  metadata = {
    google-logging-enable    = "0"
    google-monitoring-enable = "0"
  }
}

resource "google_compute_instance" "instance" {
  name         = "${var.goog_cm_deployment_name}-vm"
  machine_type = var.machine_type
  zone         = var.zone

  tags = ["${var.goog_cm_deployment_name}-deployment"]

  boot_disk {
    device_name = "autogen-vm-tmpl-boot-disk"
    initialize_params {
      size  = var.boot_disk_size
      type  = var.boot_disk_type
      image = var.source_image
    }
  }

  metadata = local.metadata

  dynamic "network_interface" {
    for_each = local.network_interfaces
    content {
      network    = network_interface.value.network
      subnetwork = network_interface.value.subnetwork

      dynamic "access_config" {
        for_each = network_interface.value.external_ip == "NONE" ? [] : [1]
        content {
          nat_ip = network_interface.value.external_ip == "EPHEMERAL" ? null : network_interface.value.external_ip
        }
      }
    }
  }

  service_account {
    email = "default"
    scopes = compact([
      "https://www.googleapis.com/auth/cloud.useraccounts.readonly",
      "https://www.googleapis.com/auth/devstorage.read_only",
      "https://www.googleapis.com/auth/logging.write",
      "https://www.googleapis.com/auth/monitoring.write",
      var.enable_cloud_api == true ? "https://www.googleapis.com/auth/cloud-platform" : null
    ])
  }
}
