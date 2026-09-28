terraform {
  required_providers {
    google = { source = "hashicorp/google" }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  service_name = "${var.goog_cm_deployment_name}-a2ui"

  install_script = templatefile("${path.module}/install.sh", {
    service_name               = "${var.goog_cm_deployment_name}-a2ui"
    container_image            = var.container_image
    region                     = var.region
    runtime_sa_email           = google_service_account.runtime.email
    oss_router                 = var.oss_router
    endor_api_base_url         = var.endor_api_base_url
    endor_api_key_secret_id    = var.endor_api_key_secret_id
    endor_api_secret_secret_id = var.endor_api_secret_secret_id
    ge_engine_id               = var.ge_engine_id
    agent_display_name         = var.agent_display_name
  })

  metadata = {
    google-logging-enable    = "0"
    google-monitoring-enable = "0"
    startup-script           = local.install_script
  }
}

# --- Service accounts --------------------------------------------------------
# Installer SA: the VM runs as this; it deploys Cloud Run and registers in GE.
resource "google_service_account" "installer" {
  account_id   = "${var.goog_cm_deployment_name}-inst"
  display_name = "Endor AURI installer (VM bootstrap)"
}

# Runtime SA: the Cloud Run service runs as this (least privilege: only reads secrets).
resource "google_service_account" "runtime" {
  account_id   = "${var.goog_cm_deployment_name}-run"
  display_name = "Endor AURI for Developers runtime (Cloud Run)"
}

# Installer SA needs to deploy Cloud Run, register in GE, and act as the runtime SA.
resource "google_project_iam_member" "installer_run" {
  project = var.project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${google_service_account.installer.email}"
}

resource "google_project_iam_member" "installer_discoveryengine" {
  project = var.project_id
  role    = "roles/discoveryengine.admin"
  member  = "serviceAccount:${google_service_account.installer.email}"
}

resource "google_service_account_iam_member" "installer_actas_runtime" {
  service_account_id = google_service_account.runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.installer.email}"
}

# --- Endor credential secrets ------------------------------------------------
# Created with a placeholder so the Cloud Run deploy + registration succeed even
# before a real key exists. Replace the value after registration (see README).
resource "google_secret_manager_secret" "key" {
  secret_id = var.endor_api_key_secret_id
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "secret" {
  secret_id = var.endor_api_secret_secret_id
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "key" {
  secret      = google_secret_manager_secret.key.id
  secret_data = var.endor_api_key # default is a placeholder; override to seed a real key
}

resource "google_secret_manager_secret_version" "secret" {
  secret      = google_secret_manager_secret.secret.id
  secret_data = var.endor_api_secret
}

# Runtime SA can read the two secrets.
resource "google_secret_manager_secret_iam_member" "key" {
  secret_id = google_secret_manager_secret.key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_secret_manager_secret_iam_member" "secret" {
  secret_id = google_secret_manager_secret.secret.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime.email}"
}

# --- The installer VM --------------------------------------------------------
resource "google_compute_instance" "installer" {
  name                      = "${var.goog_cm_deployment_name}-vm"
  machine_type              = var.machine_type
  zone                      = var.zone
  allow_stopping_for_update = true
  tags                      = ["${var.goog_cm_deployment_name}-deployment"]

  boot_disk {
    device_name = "autogen-vm-tmpl-boot-disk"
    initialize_params {
      size  = var.boot_disk_size
      type  = var.boot_disk_type
      image = var.source_image
    }
  }

  metadata = local.metadata

  network_interface {
    network = element(var.networks, 0)
    access_config {} # ephemeral egress IP so the installer can reach Google APIs
  }

  service_account {
    email  = google_service_account.installer.email
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
  }

  depends_on = [
    google_project_iam_member.installer_run,
    google_project_iam_member.installer_discoveryengine,
    google_service_account_iam_member.installer_actas_runtime,
    google_secret_manager_secret_iam_member.key,
    google_secret_manager_secret_iam_member.secret,
  ]
}
