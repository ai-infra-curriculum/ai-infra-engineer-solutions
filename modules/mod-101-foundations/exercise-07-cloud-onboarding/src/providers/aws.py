"""AWS provider: bucket + IAM principal + access key per user."""
from __future__ import annotations

import json
import logging
import time

import boto3

from .base import Provider, Provisioned


log = logging.getLogger(__name__)


def _bucket_name(user: str) -> str:
    sts = boto3.client("sts")
    acct = sts.get_caller_identity()["Account"]
    return f"ml-sandbox-{user}-{acct}"


def _user_name(user: str) -> str:
    return f"ml-onboard-{user}"


def _policy(user: str, bucket: str) -> str:
    return json.dumps({
        "Version": "2012-10-17",
        "Statement": [
            {"Effect": "Allow", "Action": "s3:*",
             "Resource": [f"arn:aws:s3:::{bucket}", f"arn:aws:s3:::{bucket}/*"]},
            {"Effect": "Allow", "Action": ["s3:ListBucket", "s3:GetObject"],
             "Resource": ["arn:aws:s3:::team-data", "arn:aws:s3:::team-data/*"]},
        ],
    })


class AWSProvider(Provider):
    def __init__(self, region: str = "us-west-2") -> None:
        self.region = region
        self.s3 = boto3.client("s3", region_name=region)
        self.iam = boto3.client("iam")

    def init(self, user: str, region: str) -> Provisioned:
        self.region = region
        bucket = _bucket_name(user)
        principal = _user_name(user)

        # Bucket
        try:
            if self.region == "us-east-1":
                self.s3.create_bucket(Bucket=bucket)
            else:
                self.s3.create_bucket(
                    Bucket=bucket,
                    CreateBucketConfiguration={"LocationConstraint": self.region},
                )
            self.s3.put_bucket_tagging(Bucket=bucket, Tagging={"TagSet": [
                {"Key": "Owner", "Value": user},
                {"Key": "Project", "Value": "ml-onboard"},
            ]})
            self.s3.put_bucket_versioning(Bucket=bucket, VersioningConfiguration={"Status": "Enabled"})
        except self.s3.exceptions.BucketAlreadyOwnedByYou:
            log.info("bucket exists: %s", bucket)

        # IAM user
        try:
            self.iam.create_user(UserName=principal, Tags=[{"Key": "Owner", "Value": user}])
        except self.iam.exceptions.EntityAlreadyExistsException:
            log.info("iam user exists: %s", principal)

        # Inline policy
        self.iam.put_user_policy(UserName=principal, PolicyName="scoped",
                                  PolicyDocument=_policy(user, bucket))

        # Wait for IAM eventual consistency
        time.sleep(5)

        # Access key
        keys = self.iam.list_access_keys(UserName=principal).get("AccessKeyMetadata", [])
        for k in keys:
            self.iam.delete_access_key(UserName=principal, AccessKeyId=k["AccessKeyId"])
        key = self.iam.create_access_key(UserName=principal)["AccessKey"]

        return Provisioned(
            bucket=f"s3://{bucket}",
            iam_principal=f"arn:aws:iam::{boto3.client('sts').get_caller_identity()['Account']}:user/{principal}",
            creds={
                "AWS_ACCESS_KEY_ID": key["AccessKeyId"],
                "AWS_SECRET_ACCESS_KEY": key["SecretAccessKey"],
                "AWS_REGION": region,
                "ML_ARTIFACT_BUCKET": f"s3://{bucket}",
            },
        )

    def status(self, user: str) -> dict:
        principal = _user_name(user)
        try:
            self.iam.get_user(UserName=principal)
        except self.iam.exceptions.NoSuchEntityException:
            return {"user": user, "status": "not_provisioned"}
        keys = self.iam.list_access_keys(UserName=principal).get("AccessKeyMetadata", [])
        return {
            "user": user,
            "iam_principal": principal,
            "bucket": f"s3://{_bucket_name(user)}",
            "key_age_days": ((time.time() - k["CreateDate"].timestamp()) / 86400 for k in keys),
            "keys": [{"id": k["AccessKeyId"], "created": k["CreateDate"].isoformat()} for k in keys],
        }

    def rotate_key(self, user: str) -> dict[str, str]:
        principal = _user_name(user)
        keys = self.iam.list_access_keys(UserName=principal).get("AccessKeyMetadata", [])
        for k in keys:
            self.iam.delete_access_key(UserName=principal, AccessKeyId=k["AccessKeyId"])
        new = self.iam.create_access_key(UserName=principal)["AccessKey"]
        return {"AWS_ACCESS_KEY_ID": new["AccessKeyId"], "AWS_SECRET_ACCESS_KEY": new["SecretAccessKey"]}

    def destroy(self, user: str) -> None:
        principal = _user_name(user)
        bucket = _bucket_name(user)

        try:
            keys = self.iam.list_access_keys(UserName=principal).get("AccessKeyMetadata", [])
            for k in keys:
                self.iam.delete_access_key(UserName=principal, AccessKeyId=k["AccessKeyId"])
            self.iam.delete_user_policy(UserName=principal, PolicyName="scoped")
            self.iam.delete_user(UserName=principal)
        except self.iam.exceptions.NoSuchEntityException:
            pass

        try:
            objs = self.s3.list_objects_v2(Bucket=bucket).get("Contents", [])
            for o in objs:
                self.s3.delete_object(Bucket=bucket, Key=o["Key"])
            versions = self.s3.list_object_versions(Bucket=bucket).get("Versions", [])
            for v in versions:
                self.s3.delete_object(Bucket=bucket, Key=v["Key"], VersionId=v["VersionId"])
            self.s3.delete_bucket(Bucket=bucket)
        except self.s3.exceptions.NoSuchBucket:
            pass
