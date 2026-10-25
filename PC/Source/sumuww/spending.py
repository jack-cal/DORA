"""Bounded native P2WSH multisig and lock templates, with BIP143 SIGHASH_ALL.

No general VM, key storage or signing is exposed here. Activation is separate
from parsing and construction. Public activation must be coordinated with the
network; it is deliberately not enabled by installing this library alone.
"""
from dataclasses import dataclass
from hashlib import sha256

from coincurve import PublicKey, ecdsa
from .htlc import digest
from .wallet import is_strict_der

KINDS = ('none', 'height', 'time', 'relative_height', 'relative_time')


def number(value):
    if 1 <= value <= 16:
        return bytes([0x50 + value])
    raw = value.to_bytes(max(1, (value.bit_length()+7)//8), 'little')
    if raw[-1] & 128: raw += b'\0'
    return bytes([len(raw)]) + raw


@dataclass(frozen=True)
class SpendingTemplate:
    required: int
    pubkeys: tuple
    lock_kind: str = 'none'
    lock_value: int = 0

    def __post_init__(self):
        if type(self.pubkeys) is not tuple or not 1 <= len(self.pubkeys) <= 16:
            raise ValueError('Expected one to sixteen public keys')
        if type(self.required) is not int or not 1 <= self.required <= len(self.pubkeys):
            raise ValueError('Invalid signature threshold')
        if len(set(self.pubkeys)) != len(self.pubkeys): raise ValueError('Duplicate public key')
        for key in self.pubkeys:
            if type(key) is not bytes or len(key) != 33 or PublicKey(key).format() != key:
                raise ValueError('Compressed secp256k1 public key required')
        if self.lock_kind not in KINDS or type(self.lock_value) is not int:
            raise ValueError('Invalid output lock')
        value = self.lock_value
        valid = {'none': value == 0, 'height': 1 <= value < 500_000_000,
                 'time': 500_000_000 <= value <= 0xFFFFFFFF,
                 'relative_height': 1 <= value <= 65535,
                 'relative_time': 512 <= value <= 65535*512 and value % 512 == 0}
        if not valid[self.lock_kind]: raise ValueError('Output lock outside range')

    @property
    def script(self):
        prefix = b''
        if self.lock_kind != 'none':
            value = self.lock_value
            if self.lock_kind == 'relative_time': value = (value//512) | (1 << 22)
            prefix = number(value) + (b'\xb2' if self.lock_kind.startswith('relative_') else b'\xb1') + b'\x75'
        keys = b''.join(b'\x21' + key for key in self.pubkeys)
        if len(self.pubkeys) == 1: return prefix + keys + b'\xac'
        return prefix + number(self.required) + keys + number(len(self.pubkeys)) + b'\xae'

    @property
    def script_pubkey(self):
        return b'\x00\x20' + sha256(self.script).digest()

    @classmethod
    def parse(cls, raw):
        if type(raw) is not bytes or not 35 <= len(raw) <= 600:
            raise ValueError('Unsupported spending template')
        pos = 0
        kind, value = 'none', 0
        def read_number():
            nonlocal pos
            if pos >= len(raw): raise ValueError('Truncated number')
            opcode = raw[pos]; pos += 1
            if 0x51 <= opcode <= 0x60: return opcode - 0x50
            if not 1 <= opcode <= 5 or pos+opcode > len(raw): raise ValueError('Invalid script number')
            data = raw[pos:pos+opcode]; pos += opcode
            if data[-1] & 128: raise ValueError('Negative script number')
            return int.from_bytes(data, 'little')
        # An initial number followed by CLTV/CSV and DROP is the only prefix.
        if raw[0] != 0x21:
            candidate = read_number()
            if raw[pos:pos+2] in (b'\xb1\x75', b'\xb2\x75'):
                opcode = raw[pos]; pos += 2
                if opcode == 0xb1:
                    kind, value = ('height' if candidate < 500_000_000 else 'time'), candidate
                elif candidate & (1 << 22):
                    if candidate & ~((1 << 22) | 65535): raise ValueError('Invalid relative lock flags')
                    kind, value = 'relative_time', (candidate & 65535)*512
                else:
                    kind, value = 'relative_height', candidate
            else:
                pos = 0
        required = 1
        if raw[pos:pos+1] != b'\x21': required = read_number()
        keys = []
        while raw[pos:pos+1] == b'\x21':
            pos += 1
            keys.append(raw[pos:pos+33]); pos += 33
        if len(keys) == 1:
            if required != 1 or raw[pos:] != b'\xac': raise ValueError('Invalid single-key template')
        elif len(keys) >= 2:
            if read_number() != len(keys) or raw[pos:] != b'\xae': raise ValueError('Invalid multisig template')
        else:
            raise ValueError('Missing public keys')
        result = cls(required, tuple(keys), kind, value)
        if result.script != raw: raise ValueError('Noncanonical spending template')
        return result

    def info(self):
        return {'template': 'sumuww-witness-v1', 'required_signatures': self.required,
                'public_keys': [key.hex() for key in self.pubkeys],
                'lock_kind': self.lock_kind, 'lock_value': self.lock_value,
                'witness_script': self.script.hex(), 'script_pubkey': self.script_pubkey.hex()}


def verify_spend(tx, index, spent_output):
    item = tx.inputs[index]
    if item.script_sig or not item.witness: return False
    raw = item.witness[-1]
    if spent_output.script_pubkey != b'\x00\x20' + sha256(raw).digest(): return False
    try: template = SpendingTemplate.parse(raw)
    except (ValueError, TypeError, IndexError): return False
    if template.lock_kind in ('height', 'time'):
        if ((tx.lock_time < 500_000_000) != (template.lock_kind == 'height')
                or tx.lock_time < template.lock_value or item.sequence == 0xFFFFFFFF): return False
    elif template.lock_kind.startswith('relative_'):
        wanted = template.lock_value
        sequence = item.sequence
        if tx.version < 2 or sequence & (1 << 31): return False
        if bool(sequence & (1 << 22)) != (template.lock_kind == 'relative_time'): return False
        if template.lock_kind == 'relative_time': wanted //= 512
        if sequence & 65535 < wanted: return False
    signatures = item.witness[:-1]
    if len(template.pubkeys) > 1:
        if not signatures or signatures[0] != b'': return False
        signatures = signatures[1:]
    if len(signatures) != template.required: return False
    message = digest(tx, index, spent_output, raw)
    next_key = 0
    for signature in signatures:
        if not is_strict_der(signature) or signature[-1] != 1: return False
        try:
            _, normalized = ecdsa.signature_normalize(ecdsa.der_to_cdata(signature[:-1]))
            der = ecdsa.cdata_to_der(normalized)
            matched = False
            while next_key < len(template.pubkeys):
                key = template.pubkeys[next_key]; next_key += 1
                if PublicKey(key).verify(der, message, hasher=None):
                    matched = True; break
            if not matched: return False
        except ValueError:
            return False
    return True
