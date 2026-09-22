output "agent_engine_id" {
  description = "The resource ID of the deployed Endor AURI Agent (Agent Engine)."
  value       = module.agent_engine.id
}

output "agent_name" {
  description = "The name of the deployed agent."
  value       = var.agent_engine_name
}

output "region" {
  description = "The region the agent was deployed to."
  value       = var.region
}

# -- Placeholder compute instance ---------------------------------------------
locals {
  network_interface = google_compute_instance.instance.network_interface[0]
  instance_nat_ip   = length(local.network_interface.access_config) > 0 ? local.network_interface.access_config[0].nat_ip : null
}

output "instance_self_link" {
  description = "Self-link for the placeholder compute instance."
  value       = google_compute_instance.instance.self_link
}

output "instance_zone" {
  description = "Zone for the placeholder compute instance."
  value       = var.zone
}

output "instance_machine_type" {
  description = "Machine type for the placeholder compute instance."
  value       = var.machine_type
}
