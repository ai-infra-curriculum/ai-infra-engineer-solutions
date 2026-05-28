variable "name" { type = string }

variable "region" {
  type    = string
  default = "us-west-2"
}

variable "cidr_block" {
  type    = string
  default = "10.20.0.0/16"
}

variable "azs" {
  type    = list(string)
  default = ["us-west-2a", "us-west-2b", "us-west-2c"]
}

variable "single_nat" {
  type    = bool
  default = false
}

variable "enable_flow_logs" {
  type    = bool
  default = true
}
