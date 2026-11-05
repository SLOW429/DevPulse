from app.core.agent_security import (
    create_agent_credential,
    hash_agent_credential,
    verify_agent_credential,
)


def test_agent_credentials_are_random_and_stored_as_digests() -> None:
    first, first_prefix, first_digest = create_agent_credential()
    second, second_prefix, second_digest = create_agent_credential()

    assert first.startswith(f"dp_{first_prefix}_")
    assert first_digest == hash_agent_credential(first)
    assert first_digest != first
    assert first != second
    assert first_prefix != second_prefix
    assert first_digest != second_digest
    assert verify_agent_credential(first, first_digest)
    assert not verify_agent_credential(second, first_digest)
