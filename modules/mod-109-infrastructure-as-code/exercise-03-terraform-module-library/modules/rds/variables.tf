variable "name"                    { type = string }
variable "vpc_id"                  { type = string }
variable "subnet_ids"              { type = list(string) }
variable "allowed_security_groups" { type = list(string) }
variable "db_name"                 { type = string }

variable "engine_version" {
  type    = string
  default = "16.3"
}

variable "instance_class" {
  type    = string
  default = "db.t3.medium"
}

variable "allocated_storage" {
  type    = number
  default = 50
}

variable "master_username" {
  type    = string
  default = "ml"
}

variable "backup_retention_days" {
  type    = number
  default = 7
}

variable "multi_az" {
  type    = bool
  default = false
}

variable "deletion_protection" {
  type    = bool
  default = true
}

variable "tags" {
  type    = map(string)
  default = {}
}
