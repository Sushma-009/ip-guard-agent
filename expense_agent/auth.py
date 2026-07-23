import os
import bcrypt
import jwt
from datetime import datetime, timedelta, timezone

# Fail loudly on module import/app startup if JWT_SECRET is missing or empty
if not os.environ.get("JWT_SECRET") or not os.environ.get("JWT_SECRET").strip():
    raise RuntimeError("JWT_SECRET environment variable is missing or empty.")

def get_secret() -> str:
    secret = os.environ.get("JWT_SECRET")
    if not secret or not secret.strip():
        raise RuntimeError("JWT_SECRET environment variable is missing or empty.")
    return secret

def hash_password(password: str) -> str:
    """Hashes a password using bcrypt with a cost factor of 12."""
    pw_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt(12)
    hashed = bcrypt.hashpw(pw_bytes, salt)
    return hashed.decode('utf-8')

def verify_password(password: str, hashed_password: str) -> bool:
    """Verifies a password against a bcrypt hash."""
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_access_token(data: dict) -> str:
    """Creates a JWT access token expiring in 1 hour."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=1)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, get_secret(), algorithm="HS256")

def decode_access_token(token: str) -> dict:
    """Decodes and validates a JWT access token.
    
    Raises:
        jwt.ExpiredSignatureError: if the token is expired
        jwt.InvalidTokenError: if the signature is invalid or token is malformed
    """
    return jwt.decode(token, get_secret(), algorithms=["HS256"])
