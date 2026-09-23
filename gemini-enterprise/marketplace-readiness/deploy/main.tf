terraform {
  required_providers {
    google = { source = "hashicorp/google" }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ---------------------------------------------------------------------------
# 1. Endor AURI for Developers on Cloud Run
#    The A2A endpoint Gemini Enterprise talks to. It emits the A2UI v0.9
#    interactive surface (upgrade-choice cards). GE reaches it over HTTPS and
#    renders the cards; a click returns the select_upgrade event.
# ---------------------------------------------------------------------------
resource "google_service_account" "agent" {
  account_id   = "endor-auri-a2ui"
  display_name = "Endor AURI for Developers runtime"
}

# The runtime SA reads the Endor credential from Secret Manager (least privilege).
resource "google_secret_manager_secret_iam_member" "key" {
  secret_id = var.endor_api_key_secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.agent.email}"
}

resource "google_secret_manager_secret_iam_member" "secret" {
  secret_id = var.endor_api_secret_secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.agent.email}"
}

resource "google_cloud_run_v2_service" "agent" {
  name                = "${var.goog_cm_deployment_name}-a2ui"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false # allow `terraform destroy` to undeploy cleanly

  template {
    service_account = google_service_account.agent.email

    containers {
      image = var.container_image
      ports { container_port = 8080 }

      env {
        name  = "OSS_ROUTER"
        value = var.oss_router
      }
      env {
        name  = "OSS_CLIENT"
        value = "rest"
      }
      env {
        name  = "OSS_UI_PROTOCOL"
        value = "a2ui"
      }
      env {
        name  = "ENDOR_API_BASE_URL"
        value = var.endor_api_base_url
      }
      # Endor credential from Secret Manager (never in plain config/state).
      env {
        name = "ENDOR_API_CREDENTIALS_KEY"
        value_source {
          secret_key_ref {
            secret  = var.endor_api_key_secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "ENDOR_API_CREDENTIALS_SECRET"
        value_source {
          secret_key_ref {
            secret  = var.endor_api_secret_secret_id
            version = "latest"
          }
        }
      }
      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
    }
  }

  depends_on = [
    google_secret_manager_secret_iam_member.key,
    google_secret_manager_secret_iam_member.secret,
  ]
}

# Public invoker so Gemini Enterprise can reach the A2A endpoint. If the
# customer's org policy forbids allUsers, replace with GE's service identity.
resource "google_cloud_run_v2_service_iam_member" "invoker" {
  name     = google_cloud_run_v2_service.agent.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ---------------------------------------------------------------------------
# 2. Placeholder compute instance
#    Required only by the Marketplace VM-listing validation. The agent runs on
#    Cloud Run above, NOT here. Keep it small and idle.
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

  # Allow in-place updates (the default network auto-populates a subnetwork,
  # which otherwise trips "requires stopping it" on re-apply).
  allow_stopping_for_update = true

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
