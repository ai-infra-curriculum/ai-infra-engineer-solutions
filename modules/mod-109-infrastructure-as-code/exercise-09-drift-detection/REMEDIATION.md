# Drift Remediation Playbook

## Cosmetic drift (tags, descriptions, etc.)
- Default action: **adopt** (re-apply Terraform to reset)
- Risk: low; no functional impact
- Process: comment on Slack thread "adopting", run `terraform apply`

## Material drift (config changes, attribute updates)
- Default action: **investigate**
- Risk: medium; someone modified out-of-band for a reason
- Process:
  1. Identify the manual change (CloudTrail / audit log)
  2. Talk to whoever made it
  3. Decide: codify into Terraform (preferred) OR revert (if unauthorized)
  4. Document in decision log

## Critical drift (resource deleted, replaced, recreated)
- Default action: **STOP, page on-call**
- Risk: high; could be unauthorized destruction or in-progress incident response
- Process:
  1. DO NOT terraform apply
  2. Page primary on-call
  3. Identify cause (incident? attacker? accidental?)
  4. Coordinate restore (from backup / state file rollback / manual recreate)
  5. Postmortem within 1 week

## Common false-positives

| Pattern | Cause | Action |
|---|---|---|
| Tag drift on resources with auto-tagging policy | aws config rules adding compliance tags | exclude these tags via `lifecycle.ignore_changes` |
| Auto-rotated keys in IAM | external key rotation | use `lifecycle.ignore_changes = [secret_value]` |
| Engine version bumps in managed services | RDS / EKS minor version auto-upgrade | pin `engine_version` to floor + ignore upgrades |
