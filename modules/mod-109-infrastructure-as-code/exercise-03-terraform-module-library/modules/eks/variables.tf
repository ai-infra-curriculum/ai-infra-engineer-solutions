variable "name"       { type = string }
variable "subnet_ids" { type = list(string) }

variable "k8s_version" {
  type    = string
  default = "1.30"
}

variable "endpoint_public_access" {
  type    = bool
  default = false
}

variable "tags" {
  type    = map(string)
  default = {}
}

variable "node_groups" {
  type = map(object({
    instance_types = list(string)
    desired_size   = number
    min_size       = number
    max_size       = number
    labels         = optional(map(string), {})
    taints = optional(list(object({
      key    = string
      value  = string
      effect = string
    })), [])
  }))
}
