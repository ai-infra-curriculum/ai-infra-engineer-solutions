package main

# Resources must follow `${team}-${env}-${component}` naming.
naming_regex := `^[a-z][a-z0-9]+-[a-z0-9]+-[a-z0-9-]+$`

deny[msg] {
  resource := input.resource_changes[_]
  name := resource.change.after.name
  name != null
  not regex.match(naming_regex, name)
  msg := sprintf("'%s' name '%s' does not match team-env-component pattern",
                  [resource.address, name])
}
