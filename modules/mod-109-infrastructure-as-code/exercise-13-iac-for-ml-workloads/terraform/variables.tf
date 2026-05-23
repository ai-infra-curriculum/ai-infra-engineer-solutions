variable "environment" {
  type    = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be dev | staging | prod"
  }
}

variable "region" {
  type    = string
  default = "us-east-1"
}
