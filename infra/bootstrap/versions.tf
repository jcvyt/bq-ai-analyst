terraform {
  required_version = ">= 1.9"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.8"
    }
  }
}

provider "google" {
  project               = var.bootstrap_project
  region                = var.region
  user_project_override = true
  billing_project       = var.bootstrap_project
}
