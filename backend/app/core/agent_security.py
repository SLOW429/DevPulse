import hashlib
import secrets


def create_agent_credential() -> tuple[str, str, str]:
    """Return a one-time credential, its indexed prefix, and its stored digest."""
    prefix = secrets.token_hex(8)
    credential = f"dp_{prefix}_{secrets.token_urlsafe(32)}"
    digest = hash_agent_credential(credential)
    return credential, prefix, digest


def hash_agent_credential(credential: str) -> str:
    return hashlib.sha256(credential.encode("utf-8")).hexdigest()


def verify_agent_credential(credential: str, expected_digest: str) -> bool:
    return secrets.compare_digest(
        hash_agent_credential(credential),
        expected_digest,
    )
