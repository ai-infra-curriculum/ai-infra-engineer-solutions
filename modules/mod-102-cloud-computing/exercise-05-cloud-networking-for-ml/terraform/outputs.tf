output "vpc_id"             { value = aws_vpc.this.id }
output "public_subnet_ids"  { value = aws_subnet.public[*].id }
output "private_app_ids"    { value = aws_subnet.private_app[*].id }
output "private_data_ids"   { value = aws_subnet.private_data[*].id }
output "alb_sg_id"          { value = aws_security_group.alb.id }
output "inference_sg_id"    { value = aws_security_group.inference.id }
output "training_sg_id"     { value = aws_security_group.training.id }
output "s3_endpoint_id"     { value = aws_vpc_endpoint.s3.id }
