import hmac
import hashlib
import base64
import logging

logger = logging.getLogger(__name__)

# Max payload size cap (5MB) to protect against memory exhaustion attacks
MAX_PAYLOAD_SIZE = 5 * 1024 * 1024

def validate_signature(event: dict, secret: bytes, github_signature: str) -> dict:
    """Validate incoming GitHub webhook HMAC-SHA256 signature payloads securely.
    
    Args:
        event: Lambda proxy integration event dict containing body payload.
        secret: Raw bytes of the configured webhook secret.
        github_signature: Signature header string starting with 'sha256='.
    """
    if not event or not isinstance(event, dict) or 'body' not in event:
        logger.error("Missing or malformed Lambda webhook payload body.")
        return {'statusCode': 400, 'body': 'Bad Request'}

    body_content = event['body']
    
    # Enforce strict size validation limits
    if len(body_content) > MAX_PAYLOAD_SIZE:
        logger.warning(f"Payload size exceeded limits ({len(body_content)} bytes). Blocking request.")
        return {'statusCode': 413, 'body': 'Payload Too Large'}

    try:
        # Resolve body encoding safely
        if event.get('isBase64Encoded', False):
            body_bytes = base64.b64decode(body_content)
        else:
            body_bytes = body_content.encode('utf-8')

        # Clean signature validation format
        if not github_signature or not github_signature.startswith('sha256='):
            logger.warning("Header missing valid sha256 prefix.")
            return {'statusCode': 401, 'body': 'Unauthorized'}
            
        raw_signature = github_signature.partition('sha256=')[2]
        
        # Calculate expected HMAC-SHA256 signature
        expected = hmac.new(secret, body_bytes, hashlib.sha256).hexdigest()
        
        # Secure, constant-time comparison to completely eliminate side-channel timing attacks
        if not hmac.compare_digest(expected, raw_signature):
            logger.warning("Webhook HMAC signature validation failed (Signature mismatch).")
            return {'statusCode': 401, 'body': 'Unauthorized'}
            
        logger.info("GitHub webhook HMAC signature successfully validated.")
        return {'statusCode': 200, 'body': 'OK'}
    except Exception as e:
        logger.error(f"Webhook signature authentication crashed: {e}", exc_info=True)
        return {'statusCode': 500, 'body': 'Internal Server Error'}
