"""ComponentResource: ML team namespace bundle (namespace + RBAC + quota)."""
from __future__ import annotations

import pulumi
import pulumi_kubernetes as k8s


class MlNamespace(pulumi.ComponentResource):
    def __init__(self, name: str, team: str, owner_emails: list[str],
                 gpu_quota: int = 0, opts: pulumi.ResourceOptions | None = None):
        super().__init__("ml:k8s:MlNamespace", name, {}, opts)
        child_opts = pulumi.ResourceOptions(parent=self)

        ns = k8s.core.v1.Namespace(
            f"{name}-ns",
            metadata={"name": f"team-{team}", "labels": {"team": team, "tier": "ml"}},
            opts=child_opts,
        )

        k8s.rbac.v1.RoleBinding(
            f"{name}-owners",
            metadata={"namespace": ns.metadata["name"]},
            role_ref={"api_group": "rbac.authorization.k8s.io",
                      "kind": "ClusterRole", "name": "admin"},
            subjects=[{"kind": "User", "name": e} for e in owner_emails],
            opts=child_opts,
        )

        if gpu_quota > 0:
            k8s.core.v1.ResourceQuota(
                f"{name}-quota",
                metadata={"namespace": ns.metadata["name"]},
                spec={"hard": {"requests.nvidia.com/gpu": str(gpu_quota)}},
                opts=child_opts,
            )

        self.namespace = ns
        self.register_outputs({"namespace": ns.metadata["name"]})
