import time
import hmac
import hashlib
import struct
import base64
import secrets

def get_hotp_token(secret: str, intervals_no: int) -> int:
    """Generates an HOTP token for a given base32 secret and interval count."""
    secret = secret.strip().upper()
    missing_padding = len(secret) % 8
    if missing_padding:
        secret += '=' * (8 - missing_padding)

    key = base64.b32decode(secret, casefold=True)
    msg = struct.pack(">Q", intervals_no)
    h = hmac.new(key, msg, hashlib.sha1).digest()
    o = h[19] & 15
    token = (struct.unpack(">I", h[o:o+4])[0] & 0x7fffffff) % 1000000
    return token

def verify_totp(secret: str, token: str, window: int = 2) -> bool:
    """Verifies a TOTP token with a given drift window (default 2 steps = 60 seconds)."""
    if not secret or not token:
        return False

    try:
        token_val = int(token.strip())
    except ValueError:
        return False

    current_step = int(time.time() / 30)
    for i in range(-window, window + 1):
        if get_hotp_token(secret, current_step + i) == token_val:
            return True
    return False

def generate_totp_secret() -> str:
    """Generates a secure random 32-character base32 secret."""
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
    return "".join(secrets.choice(alphabet) for _ in range(32))
