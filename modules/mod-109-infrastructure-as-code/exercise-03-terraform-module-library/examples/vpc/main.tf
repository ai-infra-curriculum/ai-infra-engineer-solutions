module "vpc" {
  source     = "../../modules/vpc"
  name       = "example"
  cidr_block = "10.20.0.0/16"
  az_count   = 3
  tags = { Environment = "example", ManagedBy = "terraform" }
}

output "vpc_id" { value = module.vpc.vpc_id }
