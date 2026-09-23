output "agent_url" {
  description = "The Cloud Run URL of the Endor AURI Agent (A2UI). Register this in Gemini Enterprise."
  value       = google_cloud_run_v2_service.agent.uri
}

output "agent_card_url" {
  description = "The A2A agent card URL to give Gemini Enterprise when adding the agent."
  value       = "${google_cloud_run_v2_service.agent.uri}/.well-known/agent-card.json"
}

output "agent_service_account" {
  description = "The Cloud Run runtime service account."
  value       = google_service_account.agent.email
}

output "region" {
  description = "The region the agent was deployed to."
  value       = var.region
}

# -- Placeholder compute instance ---------------------------------------------
output "instance_self_link" {
  description = "Self-link for the placeholder compute instance."
  value       = google_compute_instance.instance.self_link
}

output "instance_machine_type" {
  description = "Machine type for the placeholder compute instance."
  value       = var.machine_type
}
