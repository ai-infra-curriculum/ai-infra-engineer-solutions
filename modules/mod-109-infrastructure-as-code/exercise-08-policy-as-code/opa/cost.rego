package main

# Warn on instance types that aren't approved
deny[msg] {
  resource := input.resource_changes[_]
  resource.type == "aws_instance"
  not approved_instance(resource.change.after.instance_type)
  msg := sprintf("Instance '%s' uses non-approved type '%s'",
                  [resource.address, resource.change.after.instance_type])
}

approved_instance(t) {
  approved := {"t3.micro", "t3.small", "t3.medium", "m5.large", "m5.xlarge"}
  approved[t]
}

# Cap RDS storage
deny[msg] {
  resource := input.resource_changes[_]
  resource.type == "aws_db_instance"
  resource.change.after.allocated_storage > 500
  msg := sprintf("RDS '%s' requests %dGB > 500GB; needs cost review",
                  [resource.address, resource.change.after.allocated_storage])
}
