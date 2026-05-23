locals {
  tags = { Project = var.name, ManagedBy = "Terraform" }
}

resource "aws_vpc" "this" {
  cidr_block           = var.cidr_block
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = merge(local.tags, { Name = var.name })
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
  tags   = local.tags
}

# Public subnets: ALBs + NAT
resource "aws_subnet" "public" {
  count = length(var.azs)
  vpc_id = aws_vpc.this.id
  cidr_block = cidrsubnet(var.cidr_block, 8, count.index)             # /24
  availability_zone = var.azs[count.index]
  map_public_ip_on_launch = true
  tags = merge(local.tags, { Tier = "public", Name = "${var.name}-public-${var.azs[count.index]}" })
}

# Private-app subnets: inference, control plane
resource "aws_subnet" "private_app" {
  count = length(var.azs)
  vpc_id = aws_vpc.this.id
  cidr_block = cidrsubnet(var.cidr_block, 8, count.index + 10)
  availability_zone = var.azs[count.index]
  tags = merge(local.tags, { Tier = "private-app", Name = "${var.name}-app-${var.azs[count.index]}" })
}

# Private-data subnets: training nodes, GPU
resource "aws_subnet" "private_data" {
  count = length(var.azs)
  vpc_id = aws_vpc.this.id
  cidr_block = cidrsubnet(var.cidr_block, 8, count.index + 20)
  availability_zone = var.azs[count.index]
  tags = merge(local.tags, { Tier = "private-data", Name = "${var.name}-data-${var.azs[count.index]}" })
}

resource "aws_eip" "nat" {
  count = var.single_nat ? 1 : length(var.azs)
  domain = "vpc"
  tags = local.tags
}

resource "aws_nat_gateway" "this" {
  count = var.single_nat ? 1 : length(var.azs)
  allocation_id = aws_eip.nat[count.index].id
  subnet_id = aws_subnet.public[count.index].id
}

# Route tables
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this.id
  }
  tags = local.tags
}

resource "aws_route_table_association" "public" {
  count = length(var.azs)
  subnet_id = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table" "private" {
  count = length(var.azs)
  vpc_id = aws_vpc.this.id
  route {
    cidr_block = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.this[var.single_nat ? 0 : count.index].id
  }
  tags = local.tags
}

resource "aws_route_table_association" "private_app" {
  count = length(var.azs)
  subnet_id = aws_subnet.private_app[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}

resource "aws_route_table_association" "private_data" {
  count = length(var.azs)
  subnet_id = aws_subnet.private_data[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}

# Flow Logs
resource "aws_cloudwatch_log_group" "flow_logs" {
  count = var.enable_flow_logs ? 1 : 0
  name = "/aws/vpc/${var.name}"
  retention_in_days = 30
}

resource "aws_iam_role" "flow_logs" {
  count = var.enable_flow_logs ? 1 : 0
  name = "${var.name}-flowlogs"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "vpc-flow-logs.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy" "flow_logs" {
  count = var.enable_flow_logs ? 1 : 0
  name = "flow-logs"
  role = aws_iam_role.flow_logs[0].id
  policy = jsonencode({
    Statement = [{ Effect = "Allow", Action = ["logs:*"], Resource = "*" }]
  })
}

resource "aws_flow_log" "vpc" {
  count = var.enable_flow_logs ? 1 : 0
  log_destination = aws_cloudwatch_log_group.flow_logs[0].arn
  iam_role_arn    = aws_iam_role.flow_logs[0].arn
  traffic_type    = "ALL"
  vpc_id          = aws_vpc.this.id
}
