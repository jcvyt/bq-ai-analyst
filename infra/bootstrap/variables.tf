variable "org_id" {
  type = string
  validation {
    condition     = can(regex("^[0-9]+$", var.org_id))
    error_message = "org_id must be numeric."
  }
}
variable "folder_id" {
  type = string
  validation {
    condition     = can(regex("^[0-9]+$", var.folder_id))
    error_message = "folder_id must be numeric."
  }
}
variable "billing_account" {
  type = string
  validation {
    condition     = can(regex("^[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}$", var.billing_account))
    error_message = "billing_account must look like XXXXXX-XXXXXX-XXXXXX (uppercase hex)."
  }
}
variable "bootstrap_project" { type = string }
variable "workload_project" { type = string }
variable "domain" {
  type = string
  validation {
    condition     = can(regex("^[a-z0-9-]+(\\.[a-z0-9-]+)+$", var.domain))
    error_message = "domain must be bare, e.g. example.com (no @, spaces or comments)."
  }
}
variable "github_repo" {
  type        = string
  description = "owner/repo, e.g. you/bq-ai-analyst"
}
variable "region" {
  type    = string
  default = "us-east4"
}
variable "customer_id" {
  type = string
  validation {
    condition     = can(regex("^C0[0-9a-zA-Z]+$", var.customer_id))
    error_message = "customer_id must be a Cloud Identity customer ID (C0...)."
  }
}