# infra/envs/dev/services.tf
import {
  to = google_project_service.cloudasset
  id = "hanuman-0001/cloudasset.googleapis.com"
}

resource "google_project_service" "cloudasset" {
  project            = var.project_id
  service            = "cloudasset.googleapis.com"
  disable_on_destroy = false
}