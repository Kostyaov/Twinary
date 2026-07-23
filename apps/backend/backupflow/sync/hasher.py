from __future__ import annotations

from pathlib import Path
from typing import Callable

MASK64 = 0xFFFFFFFFFFFFFFFF
PRIME64_1 = 11400714785074694791
PRIME64_2 = 14029467366897019727
PRIME64_3 = 1609587929392839161
PRIME64_4 = 9650029242287828579
PRIME64_5 = 2870177450012600261
HASH_READ_CHUNK_BYTES = 8 * 1024 * 1024


def xxhash64(path: Path, seed: int = 0, should_cancel: Callable[[], bool] | None = None) -> str:
    chunks = bytearray()
    with path.open("rb") as handle:
        while True:
            if should_cancel is not None and should_cancel():
                raise InterruptedError("Operation cancelled.")
            chunk = handle.read(HASH_READ_CHUNK_BYTES)
            if not chunk:
                break
            chunks.extend(chunk)
    data = bytes(chunks)
    return f"{xxhash64_bytes(data, seed):016x}"


def xxhash64_bytes(data: bytes, seed: int = 0) -> int:
    length = len(data)
    index = 0

    if length >= 32:
        v1 = (seed + PRIME64_1 + PRIME64_2) & MASK64
        v2 = (seed + PRIME64_2) & MASK64
        v3 = seed & MASK64
        v4 = (seed - PRIME64_1) & MASK64

        limit = length - 32
        while index <= limit:
            v1 = _round(v1, _read64(data, index))
            index += 8
            v2 = _round(v2, _read64(data, index))
            index += 8
            v3 = _round(v3, _read64(data, index))
            index += 8
            v4 = _round(v4, _read64(data, index))
            index += 8

        hash_value = (
            _rotl(v1, 1)
            + _rotl(v2, 7)
            + _rotl(v3, 12)
            + _rotl(v4, 18)
        ) & MASK64
        hash_value = _merge_round(hash_value, v1)
        hash_value = _merge_round(hash_value, v2)
        hash_value = _merge_round(hash_value, v3)
        hash_value = _merge_round(hash_value, v4)
    else:
        hash_value = (seed + PRIME64_5) & MASK64

    hash_value = (hash_value + length) & MASK64

    while index + 8 <= length:
        lane = _round(0, _read64(data, index))
        hash_value ^= lane
        hash_value = ((_rotl(hash_value, 27) * PRIME64_1) + PRIME64_4) & MASK64
        index += 8

    while index + 4 <= length:
        hash_value ^= (_read32(data, index) * PRIME64_1) & MASK64
        hash_value = ((_rotl(hash_value, 23) * PRIME64_2) + PRIME64_3) & MASK64
        index += 4

    while index < length:
        hash_value ^= (data[index] * PRIME64_5) & MASK64
        hash_value = (_rotl(hash_value, 11) * PRIME64_1) & MASK64
        index += 1

    return _avalanche(hash_value)


def _round(accumulator: int, lane: int) -> int:
    accumulator = (accumulator + lane * PRIME64_2) & MASK64
    accumulator = _rotl(accumulator, 31)
    accumulator = (accumulator * PRIME64_1) & MASK64
    return accumulator


def _merge_round(hash_value: int, value: int) -> int:
    hash_value ^= _round(0, value)
    hash_value = ((hash_value * PRIME64_1) + PRIME64_4) & MASK64
    return hash_value


def _avalanche(hash_value: int) -> int:
    hash_value ^= hash_value >> 33
    hash_value = (hash_value * PRIME64_2) & MASK64
    hash_value ^= hash_value >> 29
    hash_value = (hash_value * PRIME64_3) & MASK64
    hash_value ^= hash_value >> 32
    return hash_value & MASK64


def _rotl(value: int, bits: int) -> int:
    return ((value << bits) | (value >> (64 - bits))) & MASK64


def _read64(data: bytes, index: int) -> int:
    return int.from_bytes(data[index : index + 8], "little")


def _read32(data: bytes, index: int) -> int:
    return int.from_bytes(data[index : index + 4], "little")
