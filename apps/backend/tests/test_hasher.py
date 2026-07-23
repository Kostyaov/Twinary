from __future__ import annotations

from backupflow.sync.hasher import xxhash64_bytes


def test_xxhash64_known_empty_vector() -> None:
    assert f"{xxhash64_bytes(b''):016x}" == "ef46db3751d8e999"


def test_xxhash64_known_text_vector() -> None:
    assert f"{xxhash64_bytes(b'hello'):016x}" == "26c7827d889f6da3"

