terraform {
  # Copy required_version + google provider constraint EXACTLY from infra/bootstrap/versions.tf
  required_version = ">= 1.9"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.0" # <-- match bootstrap
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 7.0" # <-- same constraint as google
    }
  }
  backend "gcs" {
    bucket = "hanuman-0002-tfstate"
    prefix = "envs/dev"
  }
}
