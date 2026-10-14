# __generated__ by Terraform
# Please review these resources and move them into your main configuration files.

# __generated__ by Terraform from "organizations/361767570892/policies/iam.managed.disableServiceAccountKeyCreation"
resource "google_org_policy_policy" "managed_disable_sa_key_creation" {
  deletion_policy = "DELETE"
  name            = "iam.managed.disableServiceAccountKeyCreation"
  parent          = "organizations/361767570892"
  spec {
    inherit_from_parent = false
    reset               = false
    rules {
      allow_all  = null
      deny_all   = null
      enforce    = "TRUE"
      parameters = null
    }
  }
}

# __generated__ by Terraform from "organizations/361767570892/policies/iam.automaticIamGrantsForDefaultServiceAccounts"
resource "google_org_policy_policy" "no_auto_iam_grants_default_sa" {
  deletion_policy = "DELETE"
  name            = "iam.automaticIamGrantsForDefaultServiceAccounts"
  parent          = "organizations/361767570892"
  spec {
    inherit_from_parent = false
    reset               = false
    rules {
      allow_all  = null
      deny_all   = null
      enforce    = "TRUE"
      parameters = null
    }
  }
}

# __generated__ by Terraform from "organizations/361767570892/policies/essentialcontacts.managed.allowedContactDomains"
resource "google_org_policy_policy" "managed_allowed_contact_domains" {
  deletion_policy = "DELETE"
  name            = "essentialcontacts.managed.allowedContactDomains"
  parent          = "organizations/361767570892"
  spec {
    inherit_from_parent = false
    reset               = false
    rules {
      allow_all = null
      deny_all  = null
      enforce   = "TRUE"
      parameters = jsonencode({
        allowedDomains = ["@sanjayglobalconnect.com"]
      })
    }
  }
}

# __generated__ by Terraform from "organizations/361767570892/policies/compute.managed.restrictProtocolForwardingCreationForTypes"
resource "google_org_policy_policy" "managed_restrict_protocol_forwarding" {
  deletion_policy = "DELETE"
  name            = "compute.managed.restrictProtocolForwardingCreationForTypes"
  parent          = "organizations/361767570892"
  spec {
    inherit_from_parent = false
    reset               = false
    rules {
      allow_all = null
      deny_all  = null
      enforce   = "TRUE"
      parameters = jsonencode({
        allowedSchemes = ["INTERNAL"]
      })
    }
  }
}

# __generated__ by Terraform from "organizations/361767570892/policies/storage.uniformBucketLevelAccess"
resource "google_org_policy_policy" "uniform_bucket_level_access" {
  deletion_policy = "DELETE"
  name            = "storage.uniformBucketLevelAccess"
  parent          = "organizations/361767570892"
  spec {
    inherit_from_parent = false
    reset               = false
    rules {
      allow_all  = null
      deny_all   = null
      enforce    = "TRUE"
      parameters = null
    }
  }
}

# __generated__ by Terraform from "organizations/361767570892/policies/iam.allowedPolicyMemberDomains"
resource "google_org_policy_policy" "allowed_policy_member_domains" {
  deletion_policy = "DELETE"
  name            = "iam.allowedPolicyMemberDomains"
  parent          = "organizations/361767570892"
  spec {
    inherit_from_parent = false
    reset               = false
    rules {
      allow_all  = null
      deny_all   = null
      enforce    = null
      parameters = null
      values {
        allowed_values = ["C03uqeclg"]
        denied_values  = []
      }
    }
  }
}

# __generated__ by Terraform from "organizations/361767570892/policies/iam.disableServiceAccountKeyUpload"
resource "google_org_policy_policy" "disable_sa_key_upload" {
  deletion_policy = "DELETE"
  name            = "iam.disableServiceAccountKeyUpload"
  parent          = "organizations/361767570892"
  spec {
    inherit_from_parent = false
    reset               = false
    rules {
      allow_all  = null
      deny_all   = null
      enforce    = "TRUE"
      parameters = null
    }
  }
}
