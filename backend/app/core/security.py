import bcrypt


def hash_password(password: str) -> str:
    """Return a bcrypt hash for a plaintext password."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
