variable "name"       { type = string }
variable "cidr_block" { type = string, default = "10.0.0.0/16" }
variable "az_count"   { type = number, default = 3 }
variable "tags"       { type = map(string), default = {} }
