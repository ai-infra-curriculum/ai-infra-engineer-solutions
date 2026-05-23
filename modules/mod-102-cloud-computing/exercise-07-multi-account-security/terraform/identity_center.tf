# Assumes IAM Identity Center is already enabled in the management account.

data "aws_ssoadmin_instances" "this" {}

resource "aws_ssoadmin_permission_set" "data_scientist" {
  name             = "DataScientist"
  instance_arn     = data.aws_ssoadmin_instances.this.arns[0]
  session_duration = "PT8H"
}

resource "aws_ssoadmin_managed_policy_attachment" "ds_readonly" {
  instance_arn       = data.aws_ssoadmin_instances.this.arns[0]
  managed_policy_arn = "arn:aws:iam::aws:policy/ReadOnlyAccess"
  permission_set_arn = aws_ssoadmin_permission_set.data_scientist.arn
}

resource "aws_ssoadmin_permission_set" "ml_engineer" {
  name             = "MLEngineer"
  instance_arn     = data.aws_ssoadmin_instances.this.arns[0]
  session_duration = "PT8H"
}

resource "aws_ssoadmin_managed_policy_attachment" "mle_poweruser" {
  instance_arn       = data.aws_ssoadmin_instances.this.arns[0]
  managed_policy_arn = "arn:aws:iam::aws:policy/PowerUserAccess"
  permission_set_arn = aws_ssoadmin_permission_set.ml_engineer.arn
}

resource "aws_ssoadmin_permission_set" "operator" {
  name             = "Operator"
  instance_arn     = data.aws_ssoadmin_instances.this.arns[0]
  session_duration = "PT12H"
}

resource "aws_ssoadmin_managed_policy_attachment" "op_admin" {
  instance_arn       = data.aws_ssoadmin_instances.this.arns[0]
  managed_policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
  permission_set_arn = aws_ssoadmin_permission_set.operator.arn
}
