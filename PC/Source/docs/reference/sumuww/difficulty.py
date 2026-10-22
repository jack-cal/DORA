"""Branch-aware difficulty calculation for the basic SUMUWW design.

The caller supplies a height from its validated block index, an internal-order
parent hash, and a lookup of that index's headers.  This module does not accept
blocks, choose a public genesis, or turn on public-network retargeting.  The
existing easy development chain continues to use ``no_retarget=True``.

The mainnet-style rule is independently implemented against Bitcoin Core
v29.0 commit f490f5562d4b20857ef8d042c050763795fd43da/src/pow.cpp: an adjustment
uses the last block and the first block of the immediately preceding interval.
There are no Bitcoin testnet delay exceptions or Testnet4-specific rules.
"""

from collections.abc import Callable

from .primitives import (
    Header, RETARGET_INTERVAL, TARGET_TIMESPAN, UINT256_MAX,
    encode_compact, require_int, valid_target,
)

UINT32_MAX = (1 << 32) - 1
INT64_MAX = (1 << 63) - 1


def validate_profile(pow_limit: int, initial_bits: int, *,
                     no_retarget: bool = False,
                     interval: int = RETARGET_INTERVAL,
                     target_timespan: int = TARGET_TIMESPAN) -> None:
    """Reject malformed profiles and 256-bit multiplication overflow.

    Initial difficulty must have one canonical positive compact encoding.  The
    easy regtest limit is permitted only when retargeting is disabled.  Public
    retargeting parameters must keep even the largest clamped product inside a
    uint256; this also makes the unbounded Python calculation below agree with
    the bounded arithmetic used by the comparison implementation.
    """
    if type(no_retarget) is not bool:
        raise TypeError('no_retarget must be bool')
    require_int(interval, 2, UINT32_MAX)
    require_int(target_timespan, 4, INT64_MAX // 4)
    target = valid_target(initial_bits, pow_limit)
    if encode_compact(target) != initial_bits:
        raise ValueError('Initial difficulty must use canonical compact bits')
    if not no_retarget and pow_limit * (target_timespan * 4) > UINT256_MAX:
        raise ValueError('Retarget profile can overflow uint256 multiplication')


def expected_bits(parent_height: int, parent_hash: bytes,
                  lookup_header: Callable[[bytes], Header | None],
                  pow_limit: int, initial_bits: int, *,
                  no_retarget: bool = False,
                  interval: int = RETARGET_INTERVAL,
                  target_timespan: int = TARGET_TIMESPAN) -> int:
    """Return the required bits for the child of an indexed parent.

    ``parent_height`` is trusted index metadata, never a peer-supplied height.
    The callback returns ``Header`` or ``None`` using internal-order hash bytes.
    Every retrieved header must hash to the requested identifier.  At a boundary
    the lookup walks actual parent links to height ``next_height - interval``;
    it never reads the active chain's block at the same height as a side branch.

    Header times and compact targets are range-checked.  No proof-of-work or
    median-time validation is performed here: the parent index must already be
    validated, and the resulting candidate still needs the normal PoW checks.
    Configuration is trusted local data; custom intervals determine walk cost.
    """
    require_int(parent_height, 0, UINT32_MAX - 1)
    if not isinstance(parent_hash, bytes) or len(parent_hash) != 32:
        raise ValueError('Parent hash must contain exactly 32 bytes')
    if not callable(lookup_header):
        raise TypeError('Header lookup must be callable')
    validate_profile(pow_limit, initial_bits, no_retarget=no_retarget,
                     interval=interval, target_timespan=target_timespan)

    def load(digest: bytes) -> Header:
        header = lookup_header(digest)
        if header is None:
            raise ValueError('Missing difficulty ancestor header')
        if not isinstance(header, Header):
            raise TypeError('Header lookup must return Header or None')
        # serialize() checks all binary header field types and bounds.
        header.serialize()
        if header.digest() != digest:
            raise ValueError('Difficulty ancestor does not match its hash')
        valid_target(header.bits, pow_limit)
        return header

    parent = load(parent_hash)
    if parent_height == 0:
        if parent.previous_hash != bytes(32) or parent.bits != initial_bits:
            raise ValueError('Height-zero header does not match profile difficulty')
    next_height = parent_height + 1
    if no_retarget or next_height % interval:
        return parent.bits

    first = parent
    for _ in range(interval - 1):
        first = load(first.previous_hash)
    if next_height == interval:
        if first.previous_hash != bytes(32) or first.bits != initial_bits:
            raise ValueError('First adjustment does not reach the profile genesis')

    elapsed = parent.timestamp - first.timestamp
    elapsed = max(target_timespan // 4, min(elapsed, target_timespan * 4))
    target = valid_target(parent.bits, pow_limit) * elapsed // target_timespan
    return encode_compact(min(target, pow_limit))
