"""Integer ASERT target calculation (aserti3-2d specification).

Activation and anchor selection belong to the chain's registered rules.
No wall clock, floating point, peer count, or candidate timestamp is used.
"""

from .primitives import encode_compact, require_int, valid_target

HALF_LIFE = 172800
TARGET_SPACING = 600


def next_bits(anchor_bits, time_delta, height_delta, pow_limit, *,
              spacing=TARGET_SPACING, half_life=HALF_LIFE):
    target = valid_target(anchor_bits, pow_limit)
    require_int(height_delta, 0, (1 << 32) - 1)
    require_int(time_delta, -(1 << 63), (1 << 63) - 1)
    require_int(spacing, 1, (1 << 32) - 1)
    require_int(half_life, 1, (1 << 32) - 1)
    numerator = (time_delta - spacing * (height_delta + 1)) * 65536
    # C++ signed division truncates toward zero; Python // does not.
    exponent = (abs(numerator) // half_life) * (-1 if numerator < 0 else 1)
    shifts, fraction = divmod(exponent, 65536)
    factor = 65536 + ((195766423245049 * fraction
                      + 971821376 * fraction**2
                      + 5127 * fraction**3 + (1 << 47)) >> 48)
    value = target * factor
    # Bound shifts before allocating a potentially enormous Python integer.
    if shifts >= 256:
        return encode_compact(pow_limit)
    if shifts <= -512:
        return encode_compact(1)
    value = (value << shifts) if shifts >= 0 else (value >> -shifts)
    value >>= 16
    return encode_compact(max(1, min(value, pow_limit)))
