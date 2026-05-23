package main

# All resources must carry team + env + cost_center tags.
required_tags := {"team", "env", "cost_center"}

deny[msg] {
  resource := input.resource_changes[_]
  tags := object.get(resource.change.after, "tags", {})
  missing := required_tags - {k | tags[k]}
  count(missing) > 0
  msg := sprintf("'%s' missing required tags: %v", [resource.address, missing])
}
