variable "project_id" { type = string }
variable "region" { type = string }
variable "admins_group" {
  type        = string
  description = "Bare group email, no prefix or comments"
  validation {
    condition     = can(regex("^[a-z0-9._-]+@[a-z0-9.-]+\\.[a-z]{2,}$", var.admins_group))
    error_message = "admins_group must be a bare group email (e.g. gcp-admins@example.com)."
  }
}

variable "developers_group" {
  type        = string
  description = "Bare group email, no prefix or comments"
  validation {
    condition     = can(regex("^[a-z0-9._-]+@[a-z0-9.-]+\\.[a-z]{2,}$", var.developers_group))
    error_message = "developers_group must be a bare group email (e.g. gcp-developers@example.com)."
  }
}