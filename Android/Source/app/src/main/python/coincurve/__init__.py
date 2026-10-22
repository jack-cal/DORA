"""Fresh ABI adapter for official libsecp256k1; PC042's required coincurve surface."""
import ctypes as C
import hashlib
import secrets
import threading

lib = C.CDLL('libsecp256k1.so')
def api(name, args, result=C.c_int):
    fn=getattr(lib,'secp256k1_'+name); fn.argtypes=args; fn.restype=result; return fn
ptr=C.c_void_p; size=C.c_size_t
context=api('context_create',[C.c_uint],ptr)(1)
if not context: raise RuntimeError('libsecp256k1 context allocation failed')
randomize=api('context_randomize',[ptr,ptr])
if randomize(context,secrets.token_bytes(32)) != 1: raise RuntimeError('Context randomization failed')
validate=api('ec_seckey_verify',[ptr,ptr])
create=api('ec_pubkey_create',[ptr,ptr,ptr])
parse=api('ec_pubkey_parse',[ptr,ptr,ptr,size])
serialize=api('ec_pubkey_serialize',[ptr,ptr,C.POINTER(size),ptr,C.c_uint])
sign=api('ecdsa_sign',[ptr,ptr,ptr,ptr,ptr,ptr])
verify=api('ecdsa_verify',[ptr,ptr,ptr,ptr])
parse_der=api('ecdsa_signature_parse_der',[ptr,ptr,ptr,size])
serialize_der=api('ecdsa_signature_serialize_der',[ptr,ptr,C.POINTER(size),ptr])
normalize=api('ecdsa_signature_normalize',[ptr,ptr,ptr])
privadd=api('ec_seckey_tweak_add',[ptr,ptr,ptr])
pubadd=api('ec_pubkey_tweak_add',[ptr,ptr,ptr])
lock=threading.RLock()
def buf(data): return C.create_string_buffer(data,len(data))
def scalar(data):
    if type(data)!=bytes or len(data)!=32 or validate(context,data)!=1: raise ValueError('Invalid private key')
    return data
def digest(data,hasher):
    data=hasher(data).digest() if hasher else data
    if type(data)!=bytes or len(data)!=32: raise ValueError('Digest must be32bytes')
    return data
def sig_to_der(raw):
    out=C.create_string_buffer(72); length=size(72)
    if serialize_der(context,out,C.byref(length),raw)!=1: raise ValueError('Invalid signature')
    return out.raw[:length.value]

class PublicKey:
    def __init__(self,data):
        if type(data)!=bytes or len(data) not in (33,65): raise ValueError('Invalid public key')
        self.raw=C.create_string_buffer(64)
        if parse(context,self.raw,data,len(data))!=1: raise ValueError('Invalid public key')
    def format(self,compressed=True):
        out=C.create_string_buffer(65); length=size(65)
        if serialize(context,out,C.byref(length),self.raw,258 if compressed else 2)!=1: raise ValueError('Serialization failed')
        return out.raw[:length.value]
    def verify(self,signature,message,hasher=hashlib.sha256):
        raw=C.create_string_buffer(64)
        if type(signature)!=bytes or parse_der(context,raw,signature,len(signature))!=1: return False
        return verify(context,raw,digest(message,hasher),self.raw)==1
    def add(self,tweak,update=False):
        if type(tweak)!=bytes or len(tweak)!=32: raise ValueError('Invalid tweak')
        result=PublicKey(self.format())
        if pubadd(context,result.raw,tweak)!=1: raise ValueError('Invalid derived key')
        if update: self.raw=result.raw; return self
        return result

class PrivateKey:
    def __init__(self,secret=None):
        if secret is None:
            while True:
                secret=secrets.token_bytes(32)
                if validate(context,secret)==1: break
        self.secret=scalar(secret)
    @property
    def public_key(self):
        raw=C.create_string_buffer(64)
        if create(context,raw,self.secret)!=1: raise ValueError('Invalid private key')
        out=C.create_string_buffer(33); length=size(33)
        if serialize(context,out,C.byref(length),raw,258)!=1: raise ValueError('Public key failure')
        return PublicKey(out.raw)
    def sign(self,message,hasher=hashlib.sha256):
        raw=C.create_string_buffer(64)
        with lock:
            if sign(context,raw,digest(message,hasher),self.secret,None,None)!=1: raise ValueError('Signature failed')
        return sig_to_der(raw)
    def add(self,tweak,update=False):
        if type(tweak)!=bytes or len(tweak)!=32: raise ValueError('Invalid tweak')
        value=buf(self.secret)
        if privadd(context,value,tweak)!=1: raise ValueError('Invalid derived key')
        if update: self.secret=value.raw; return self
        return PrivateKey(value.raw)

from . import ecdsa
