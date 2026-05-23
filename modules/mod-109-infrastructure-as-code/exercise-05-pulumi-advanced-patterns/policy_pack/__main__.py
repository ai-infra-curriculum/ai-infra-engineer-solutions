"""CrossGuard policy: every namespace must have a `team` label."""
from pulumi_policy import EnforcementLevel, PolicyPack, ResourceValidationArgs, ResourceValidationPolicy


def require_team_label(args: ResourceValidationArgs, report):
    if args.resource_type == "kubernetes:core/v1:Namespace":
        labels = args.props.get("metadata", {}).get("labels", {})
        if not labels.get("team"):
            report(f"Namespace {args.name} missing 'team' label")


PolicyPack(
    "ml-platform-policies",
    enforcement_level=EnforcementLevel.MANDATORY,
    policies=[
        ResourceValidationPolicy(
            name="require-team-label",
            description="All namespaces must carry a team label",
            validate=require_team_label,
        ),
    ],
)
