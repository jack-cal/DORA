"""Integer DGW v3 target calculation; branch selection is the caller's job.

Matches Dash's 24-target weighted calculation and its 23 timestamp gaps.
The final target remains bounded by SUMUWW's existing proof-of-work limit.
"""
from .primitives import encode_compact, require_int, valid_target

WINDOW = 24
SPACING = 600

def next_bits(history, pow_limit, *, spacing=SPACING):
    """Calculate from exactly 24 (timestamp, nBits) pairs, newest first."""
    require_int(spacing, 1, 0xFFFFFFFF)
    if len(history) != WINDOW:
        raise ValueError('DGW requires 24 parent-branch headers')
    average = None
    for count, (timestamp, bits) in enumerate(history, 1):
        require_int(timestamp, 0, 0xFFFFFFFF)
        target = valid_target(bits, pow_limit)
        average = target if count == 1 else (average*count + target)//(count+1)
    intended = WINDOW*spacing
    elapsed = max(intended//3, min(history[0][0]-history[-1][0], intended*3))
    return encode_compact(max(1, min(average*elapsed//intended, pow_limit)))
