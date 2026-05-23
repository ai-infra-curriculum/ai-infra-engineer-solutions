resource "aws_security_group" "alb" {
  name = "${var.name}-alb"
  description = "Public ALB"
  vpc_id = aws_vpc.this.id

  ingress {
    from_port = 443; to_port = 443; protocol = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port = 0; to_port = 0; protocol = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "inference" {
  name = "${var.name}-inference"
  description = "Inference pods"
  vpc_id = aws_vpc.this.id

  ingress {
    from_port = 8000; to_port = 8000; protocol = "tcp"
    security_groups = [aws_security_group.alb.id]
  }
  egress {
    from_port = 0; to_port = 0; protocol = "-1"
    cidr_blocks = [var.cidr_block]    # only intra-VPC + Gateway Endpoints
  }
}

resource "aws_security_group" "training" {
  name = "${var.name}-training"
  description = "Training / GPU nodes"
  vpc_id = aws_vpc.this.id

  # No inbound at all
  egress {
    from_port = 0; to_port = 0; protocol = "-1"
    cidr_blocks = ["0.0.0.0/0"]   # NAT for HuggingFace, S3 via Gateway Endpoint
  }
}
