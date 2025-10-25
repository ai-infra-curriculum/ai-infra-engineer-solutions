"""Storage utilities for S3/MinIO interactions."""

import boto3
from botocore.exceptions import ClientError
from typing import Optional, List
import io

from .config import config
from .logger import get_logger

logger = get_logger(__name__)


class StorageClient:
    """Client for interacting with S3/MinIO storage."""

    def __init__(self):
        """Initialize storage client."""
        self.s3_client = boto3.client(
            's3',
            endpoint_url=config.AWS_ENDPOINT_URL,
            aws_access_key_id=config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY,
        )
        self.bucket = config.S3_BUCKET
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        """Ensure the S3 bucket exists."""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket)
            logger.info(f"Bucket '{self.bucket}' exists")
        except ClientError:
            logger.info(f"Creating bucket '{self.bucket}'")
            try:
                self.s3_client.create_bucket(Bucket=self.bucket)
                logger.info(f"Bucket '{self.bucket}' created successfully")
            except ClientError as e:
                logger.error(f"Failed to create bucket: {e}")
                raise

    def upload_file(self, file_path: str, object_name: Optional[str] = None) -> bool:
        """
        Upload a file to S3.

        Args:
            file_path: Path to file to upload
            object_name: S3 object name (defaults to file_path)

        Returns:
            True if successful, False otherwise
        """
        if object_name is None:
            object_name = file_path

        try:
            self.s3_client.upload_file(file_path, self.bucket, object_name)
            logger.info(f"Uploaded {file_path} to s3://{self.bucket}/{object_name}")
            return True
        except ClientError as e:
            logger.error(f"Failed to upload file: {e}")
            return False

    def download_file(self, object_name: str, file_path: str) -> bool:
        """
        Download a file from S3.

        Args:
            object_name: S3 object name
            file_path: Local path to save file

        Returns:
            True if successful, False otherwise
        """
        try:
            self.s3_client.download_file(self.bucket, object_name, file_path)
            logger.info(f"Downloaded s3://{self.bucket}/{object_name} to {file_path}")
            return True
        except ClientError as e:
            logger.error(f"Failed to download file: {e}")
            return False

    def upload_fileobj(self, file_obj: io.BytesIO, object_name: str) -> bool:
        """
        Upload a file-like object to S3.

        Args:
            file_obj: File-like object
            object_name: S3 object name

        Returns:
            True if successful, False otherwise
        """
        try:
            self.s3_client.upload_fileobj(file_obj, self.bucket, object_name)
            logger.info(f"Uploaded file object to s3://{self.bucket}/{object_name}")
            return True
        except ClientError as e:
            logger.error(f"Failed to upload file object: {e}")
            return False

    def list_objects(self, prefix: str = '') -> List[str]:
        """
        List objects in S3 bucket.

        Args:
            prefix: Prefix to filter objects

        Returns:
            List of object keys
        """
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket,
                Prefix=prefix
            )
            if 'Contents' in response:
                return [obj['Key'] for obj in response['Contents']]
            return []
        except ClientError as e:
            logger.error(f"Failed to list objects: {e}")
            return []

    def delete_object(self, object_name: str) -> bool:
        """
        Delete an object from S3.

        Args:
            object_name: S3 object name

        Returns:
            True if successful, False otherwise
        """
        try:
            self.s3_client.delete_object(Bucket=self.bucket, Key=object_name)
            logger.info(f"Deleted s3://{self.bucket}/{object_name}")
            return True
        except ClientError as e:
            logger.error(f"Failed to delete object: {e}")
            return False

    def object_exists(self, object_name: str) -> bool:
        """
        Check if an object exists in S3.

        Args:
            object_name: S3 object name

        Returns:
            True if exists, False otherwise
        """
        try:
            self.s3_client.head_object(Bucket=self.bucket, Key=object_name)
            return True
        except ClientError:
            return False
