from datetime import UTC, datetime
import json

import boto3
from botocore.client import BaseClient
from botocore.exceptions import ClientError

from worker.app.settings import WorkerSettings


class ObjectStorage:
    def __init__(self, settings: WorkerSettings) -> None:
        self.settings = settings
        self.client: BaseClient = boto3.client(
            "s3",
            endpoint_url=settings.minio_endpoint,
            aws_access_key_id=settings.minio_root_user,
            aws_secret_access_key=settings.minio_root_password,
        )

    def ensure_bucket(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.settings.minio_bucket)
        except ClientError:
            self.client.create_bucket(Bucket=self.settings.minio_bucket)
        self.client.put_bucket_policy(
            Bucket=self.settings.minio_bucket,
            Policy=json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {"AWS": ["*"]},
                            "Action": ["s3:GetObject"],
                            "Resource": [f"arn:aws:s3:::{self.settings.minio_bucket}/*"],
                        }
                    ],
                }
            ),
        )

    def upload_webp(self, key: str, image_bytes: bytes) -> str:
        self.ensure_bucket()
        self.client.put_object(
            Bucket=self.settings.minio_bucket,
            Key=key,
            Body=image_bytes,
            ContentType="image/webp",
        )
        return key


def generation_object_key(job_id: str, filename: str) -> str:
    now = datetime.now(UTC)
    return f"{now:%Y/%m}/{job_id}/{filename}"
