"""HTTPS WORM collector forwarder. The receiving service must enforce immutable retention."""
import hashlib, hmac, json
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

class ExternalAuditUnavailable(RuntimeError): pass
class ExternalAuditSink:
    def __init__(self, endpoint: str, bearer_token: str, opener=urlopen):
        if not endpoint.startswith("https://"):
            raise ValueError("external audit endpoint must use HTTPS")
        if len(bearer_token) < 32: raise ValueError("audit bearer token too short")
        self.endpoint, self.token, self.opener = endpoint, bearer_token, opener
    def append(self, row: dict):
        canonical = json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        digest = hashlib.sha256(canonical).hexdigest()
        req = Request(self.endpoint, data=canonical, headers={"Authorization": "Bearer " + self.token, "Content-Type": "application/json", "Idempotency-Key": digest}, method="POST")
        try:
            with self.opener(req, timeout=3) as response:
                if response.status not in (200, 201, 202, 204): raise ExternalAuditUnavailable("audit sink rejected event")
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise ExternalAuditUnavailable("external audit sink unavailable") from exc
        return digest

class S3ObjectLockAuditSink:
    """Append-only S3 Object Lock writer. Bucket versioning/Object Lock must be enabled by an operator."""
    def __init__(self, client, bucket, retention_days=365):
        if not bucket or not 1 <= int(retention_days) <= 36500:
            raise ValueError("invalid Object Lock bucket or retention")
        self.client, self.bucket, self.retention_days = client, bucket, int(retention_days)
    def append(self, row):
        from datetime import datetime, timedelta, timezone
        import uuid
        canonical=json.dumps(row,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
        digest=hashlib.sha256(canonical).hexdigest()
        self.client.put_object(Bucket=self.bucket,Key=f"cri-audit/{digest}-{uuid.uuid4().hex}.json",Body=canonical,ContentType="application/json",ObjectLockMode="COMPLIANCE",ObjectLockRetainUntilDate=datetime.now(timezone.utc)+timedelta(days=self.retention_days),Metadata={"sha256":digest})
        return digest

    @classmethod
    def from_env(cls):
        import os
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("boto3 is required for S3 Object Lock") from exc
        bucket=os.getenv("CRI_AUDIT_S3_BUCKET", "")
        if not bucket: raise ValueError("CRI_AUDIT_S3_BUCKET is required")
        client=boto3.client("s3", region_name=os.getenv("AWS_REGION"))
        return cls(client,bucket,int(os.getenv("CRI_AUDIT_S3_RETENTION_DAYS","365")))
