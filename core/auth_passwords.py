"""
core/auth_passwords.py — Low-level password hashing and verification.

Extracted from auth.py to avoid circular imports between auth.py and users.py.
Supports: bcrypt ($2y$/$2b$/$2a$), SHA1 ({SHA}...), APR1-MD5 ($apr1$...), plain text.
"""
import base64
import hashlib
import logging

import bcrypt

logger = logging.getLogger(__name__)


def verify_password(password: str, hashed: str) -> bool:
    """Dispatch password verification based on hash format."""
    if hashed.startswith(("$2y$", "$2b$", "$2a$")):
        return _verify_bcrypt(password, hashed)
    elif hashed.startswith("{SHA}"):
        return _verify_sha1(password, hashed)
    elif hashed.startswith("$apr1$"):
        return _verify_md5_apr1(password, hashed)
    else:
        logger.warning("Plain-text password comparison — use hashed passwords in production!")
        return password == hashed


def _verify_bcrypt(password: str, hashed: str) -> bool:
    try:
        normalized = hashed.replace("$2y$", "$2b$")
        return bcrypt.checkpw(password.encode(), normalized.encode())
    except Exception:
        return False


def _verify_sha1(password: str, hashed: str) -> bool:
    expected = base64.b64encode(hashlib.sha1(password.encode()).digest()).decode()
    stored = hashed[len("{SHA}"):]
    return expected == stored


def _verify_md5_apr1(password: str, hashed: str) -> bool:
    try:
        import crypt
        return crypt.crypt(password, hashed) == hashed
    except ImportError:
        try:
            from passlib.hash import apr_md5_crypt
            return apr_md5_crypt.verify(password, hashed)
        except ImportError:
            logger.warning("Cannot verify APR1-MD5: install passlib or use Linux.")
            return False


def hash_password_bcrypt(password: str) -> str:
    """Generate a bcrypt hash. Uses $2y$ prefix for Apache .htpasswd compatibility."""
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12))
    return hashed.decode().replace("$2b$", "$2y$")
