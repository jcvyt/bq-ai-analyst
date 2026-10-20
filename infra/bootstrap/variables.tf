variable "org_id" { type = string }
variable "folder_id" { type = string }
variable "billing_account" { type = string }
variable "bootstrap_project" { type = string }
variable "workload_project" { type = string }
variable "domain" { type = string }
variable "github_repo" {
  type        = string
  description = "owner/repo, e.g. you/bq-ai-analyst"
}
variable "region" {
  type    = string
  default = "us-east4"
}
