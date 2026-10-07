import hmac
import hashlib
import base64
import logging

logger = logging.getLogger(__name__)
MAX_PAYLOAD_SIZE = 5 * 1024 * 1024

def validate_signature(event: dict, secret: bytes, github_signature: str) -> dict:
    """Validate incoming GitHub webhook HMAC-SHA256 signature payloads securely."""
    if not event or not isinstance(event, dict) or 'body' not in event:
        return {'statusCode': 400, 'body': 'Bad Request'}
    if len(event['body']) > MAX_PAYLOAD_SIZE:
        return {'statusCode': 413, 'body': 'Payload Too Large'}

    try:
        if event.get('isBase64Encoded', False):
            body_bytes = base64.b64decode(event['body'])
        else:
            body_bytes = event['body'].encode('utf-8')

        if not github_signature or not github_signature.startswith('sha256='):
            return {'statusCode': 401, 'body': 'Unauthorized'}
        raw_signature = github_signature.partition('sha256=')[2]

        expected = hmac.new(secret, body_bytes, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, raw_signature):
            return {'statusCode': 401, 'body': 'Unauthorized'}

        return {'statusCode': 200, 'body': 'OK'}
    except Exception as e:
        logger.error(f"Webhook signature authentication crashed: {e}", exc_info=True)
        return {'statusCode': 500, 'body': 'Internal Server Error'}
