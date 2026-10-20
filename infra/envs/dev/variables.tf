variable "project_id" { type = string }
variable "region" { type = string }
variable "admins_group" {
  type        = string
  description = "Email of gcp-admins group"
}
variable "developers_group" {
  type        = string
  description = "Email of gcp-developers group"
}