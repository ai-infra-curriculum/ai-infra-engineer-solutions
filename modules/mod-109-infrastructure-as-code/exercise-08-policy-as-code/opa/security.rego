package main

# Deny: S3 bucket without encryption
deny[msg] {
  resource := input.resource_changes[_]
  resource.type == "aws_s3_bucket"
  not encrypted(resource)
  msg := sprintf("S3 bucket '%s' must have server-side encryption", [resource.address])
}

encrypted(resource) {
  encryption := input.resource_changes[_]
  encryption.type == "aws_s3_bucket_server_side_encryption_configuration"
  encryption.change.after.bucket == resource.change.after.bucket
}

# Deny: Security Group with 0.0.0.0/0 on management ports
deny[msg] {
  resource := input.resource_changes[_]
  resource.type == "aws_security_group"
  ingress := resource.change.after.ingress[_]
  ingress.cidr_blocks[_] == "0.0.0.0/0"
  ingress.from_port == 22
  msg := sprintf("SG '%s' opens SSH to the world", [resource.address])
}

# Deny: public RDS
deny[msg] {
  resource := input.resource_changes[_]
  resource.type == "aws_db_instance"
  resource.change.after.publicly_accessible == true
  msg := sprintf("RDS '%s' must not be publicly accessible", [resource.address])
}
