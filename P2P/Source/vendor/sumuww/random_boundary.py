"""Consensus selection of BLS/trace blocks, independent of candidate nonce.

One public draw per parent/height: no local re-roll, fixed interval, committee
change or peer-count limit. Ten percent is a probability, not a deadline.
"""
from hashlib import sha256
from .boundary_crypto import canonical,rawhex

POLICY='sumuww-random-boundary-block-10pct-v1'
NUMERATOR=1
DENOMINATOR=10

def selected(network,height,parent_hash):
    rawhex(network,32);rawhex(parent_hash,32)
    if type(height) is not int or not 1<=height<2**53:raise ValueError('Random boundary height')
    message={'domain':POLICY,'network':network,'height':height,'parentHash':parent_hash}
    draw=int.from_bytes(sha256(canonical(message)).digest(),'big')
    return draw<((1<<256)*NUMERATOR//DENOMINATOR)
