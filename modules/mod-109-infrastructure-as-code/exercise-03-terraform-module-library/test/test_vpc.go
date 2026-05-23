// Terratest for the VPC module. Real test — needs AWS creds.
package test

import (
    "testing"

    "github.com/gruntwork-io/terratest/modules/terraform"
    "github.com/stretchr/testify/assert"
)

func TestVPCCreates(t *testing.T) {
    t.Parallel()
    opts := terraform.WithDefaultRetryableErrors(t, &terraform.Options{
        TerraformDir: "../examples/vpc",
    })
    defer terraform.Destroy(t, opts)
    terraform.InitAndApply(t, opts)
    vpcId := terraform.Output(t, opts, "vpc_id")
    assert.NotEmpty(t, vpcId)
}
