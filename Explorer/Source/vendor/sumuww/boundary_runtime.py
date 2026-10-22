"""Boundary discovery/signing over the application's actual peer sessions."""
import asyncio
from collections import OrderedDict
import json
from pathlib import Path
import secrets
import struct
import time
from .block import Block,MAX_BLOCK_WEIGHT
from .random_boundary import POLICY
from .boundary_crypto import NodeKeys,canonical,digest,rawhex
from .boundary import (authenticated,query_context,response,snapshot,
    draw_input,canonical_ip,replay,member,candidate_message,certificate,next_start,verify_start,verify_ready,require,exact)

BOUNDARY_PROTOCOL_VERSION=5
CONTROL_LIMIT=1024*1024

class BoundaryPolicyMismatch(Exception):
    """An authenticated older signing policy needs native transport fallback."""

def decode_json(payload,limit=CONTROL_LIMIT):
    require(limit is None or len(payload)<=limit,'Boundary message size')
    def pairs(values):
        result={}
        for key,value in values:
            require(key not in result,'Duplicate boundary JSON field'); result[key]=value
        return result
    value=json.loads(payload,object_pairs_hook=pairs)
    canonical(value)
    return value

def encode_block(block,envelope):
    proof=canonical(envelope)
    require(len(proof)<=0xffffffff,'Boundary proof length field overflow')
    return struct.pack('<I',len(proof))+proof+block.serialize()

def decode_block(payload):
    require(len(payload)>=5,'Boundary block frame truncated')
    length=struct.unpack('<I',payload[:4])[0]
    require(0<length and 81<=len(payload)-4-length<=MAX_BLOCK_WEIGHT,'Boundary block frame size')
    envelope=decode_json(payload[4:4+length],None)
    return payload[4+length:],envelope

# v9000 replaces the old proof-gated mining runtime.
from .link_runtime import LinkRuntime as BoundaryRuntime
