import ctypes as C
from . import context, parse_der, normalize, sig_to_der, api, ptr
parse_compact=api('ecdsa_signature_parse_compact',[ptr,ptr,ptr])
write_compact=api('ecdsa_signature_serialize_compact',[ptr,ptr,ptr])
def der_to_cdata(value):
    raw=C.create_string_buffer(64)
    if type(value)!=bytes or parse_der(context,raw,value,len(value))!=1: raise ValueError('Invalid DER signature')
    return raw
def signature_normalize(value):
    result=C.create_string_buffer(64)
    changed=normalize(context,result,value)
    return bool(changed),result
def cdata_to_der(value): return sig_to_der(value)
def serialize_compact(value):
    out=C.create_string_buffer(64)
    if write_compact(context,out,value)!=1: raise ValueError('Invalid signature')
    return out.raw
def deserialize_compact(value):
    out=C.create_string_buffer(64)
    if type(value)!=bytes or len(value)!=64 or parse_compact(context,out,value)!=1: raise ValueError('Invalid signature')
    return out
