"""Argon2id password hashing wrappers.

Routes must use these helpers and never touch the argon2 library directly,
so the hashing algorithm stays in one place.
"""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerificationError, VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a plaintext password with Argon2id.

    Args:
        password: Plaintext password (already length-validated by schema).

    Returns:
        Argon2id hash string starting with "$argon2id$".
    """
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Verify a password against its Argon2id hash using constant-time compare.

    Args:
        password_hash: Stored Argon2id hash.
        password: Candidate plaintext password.

    Returns:
        True when the password matches, False otherwise (wrong password,
        malformed hash, or verification error). Never raises on mismatch.
    """
    try:
        return bool(_hasher.verify(password_hash, password))
    except (VerifyMismatchError, VerificationError, InvalidHash):
        return False
