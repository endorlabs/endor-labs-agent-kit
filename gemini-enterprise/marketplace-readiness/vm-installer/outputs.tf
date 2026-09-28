output "installer_vm" {
  description = "The bootstrap VM that deploys the agent + registers it in GE."
  value       = google_compute_instance.installer.self_link
}

output "cloud_run_service_name" {
  description = "Name of the Cloud Run service the installer creates (find its HTTPS URL in the console or via: gcloud run services describe <name> --region <region>)."
  value       = local.service_name
}

output "installer_log_hint" {
  description = "Watch the install progress on the VM."
  value       = "gcloud compute ssh ${google_compute_instance.installer.name} --zone ${var.zone} --command 'sudo tail -f /var/log/endor-auri-install.log'  (or read the serial console)"
}
