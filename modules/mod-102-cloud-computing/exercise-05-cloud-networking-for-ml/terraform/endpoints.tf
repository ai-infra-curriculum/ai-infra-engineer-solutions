# Gateway endpoints (free): S3, DynamoDB
resource "aws_vpc_endpoint" "s3" {
  vpc_id       = aws_vpc.this.id
  service_name = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids = concat([aws_route_table.public.id], aws_route_table.private[*].id)
  tags = local.tags
}

resource "aws_vpc_endpoint" "dynamodb" {
  vpc_id       = aws_vpc.this.id
  service_name = "com.amazonaws.${var.region}.dynamodb"
  vpc_endpoint_type = "Gateway"
  route_table_ids = aws_route_table.private[*].id
  tags = local.tags
}

# Interface endpoints (paid; one per AZ): ECR + CloudWatch + SSM + Secrets Manager
locals {
  interface_endpoints = [
    "ecr.api", "ecr.dkr", "logs", "monitoring", "ssm", "ssmmessages", "ec2messages",
    "secretsmanager",
  ]
}

resource "aws_security_group" "vpce" {
  name        = "${var.name}-vpce"
  description = "VPC Endpoint access"
  vpc_id      = aws_vpc.this.id
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [var.cidr_block]
  }
  egress {
    from_port = 0
    to_port = 0
    protocol = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = local.tags
}

resource "aws_vpc_endpoint" "interface" {
  for_each = toset(local.interface_endpoints)
  vpc_id   = aws_vpc.this.id
  service_name = "com.amazonaws.${var.region}.${each.key}"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.private_app[*].id
  security_group_ids  = [aws_security_group.vpce.id]
  private_dns_enabled = true
  tags = merge(local.tags, { Name = "${var.name}-vpce-${each.key}" })
}
