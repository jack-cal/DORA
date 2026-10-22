"""Bitcoin SPV header verification. No checkpoints replace proof-of-work checks.

References: Bitcoin Core src/pow.cpp, src/kernel/chainparams.cpp, BIP34/65/66.
This verifies headers, not every transaction or all Bitcoin consensus rules.
"""
import hashlib
import os
import struct
import time
from pathlib import Path


def sha256d(value):
    return hashlib.sha256(hashlib.sha256(value).digest()).digest()


GENESIS_PREFIX = ('01000000' + '00' * 32 +
                  '3ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a')
GENESIS = {
    'mainnet': bytes.fromhex(GENESIS_PREFIX + '29ab5f49ffff001d1dac2b7c'),
    'test': bytes.fromhex(GENESIS_PREFIX + 'dae5494dffff7f2002000000'),
}


def target(bits):
    exponent, mantissa = bits >> 24, bits & 0x7fffff
    if bits & 0x800000 or not mantissa or exponent > 34:
        raise ValueError('Invalid Bitcoin difficulty target.')
    value = mantissa >> (8 * (3 - exponent)) if exponent <= 3 else mantissa << (8 * (exponent - 3))
    if not 0 < value < 1 << 256:
        raise ValueError('Invalid Bitcoin difficulty target.')
    return value


def compact(value):
    size = (value.bit_length() + 7) // 8
    word = value << (8 * (3 - size)) if size <= 3 else value >> (8 * (size - 3))
    if word & 0x800000:
        word >>= 8
        size += 1
    return (size << 24) | word


class HeaderChain:
    """80 bytes per persisted header; chainwork is recomputed at startup."""
    def __init__(self, path, network='mainnet', progress=None):
        if network not in GENESIS:
            raise ValueError('Unsupported light-client network.')
        self.path = Path(path)
        self.network = network
        self.progress = progress or (lambda *_: None)
        self.data = bytearray()
        self.work = []
        self.limit_bits = 0x1d00ffff if network == 'mainnet' else 0x207fffff
        self.limit = target(self.limit_bits)
        self.append(GENESIS[network])
        if self.path.exists():
            size = self.path.stat().st_size
            if not 80 <= size <= 800_000_000 or size % 80:
                raise ValueError('Bitcoin header cache is damaged; keep the wallet and rebuild its header cache.')
            with self.path.open('rb') as stream:
                if stream.read(80) != GENESIS[network]:
                    raise ValueError('Wrong cached Bitcoin genesis.')
                while raw := stream.read(80 * 2016):
                    self.extend(raw)
                    self.progress(self.height, (size // 80) - 1)

    @property
    def height(self):
        return len(self.work) - 1

    def header(self, height):
        if type(height) is not int or not 0 <= height <= self.height:
            raise ValueError('Header height is outside the verified chain.')
        return bytes(self.data[height * 80:(height + 1) * 80])

    def digest(self, height):
        return sha256d(self.header(height))[::-1].hex()

    def expected_bits(self):
        height = self.height + 1
        if height == 0:
            return self.limit_bits
        previous = self.header(height - 1)
        bits = struct.unpack_from('<I', previous, 72)[0]
        if self.network == 'test' or height % 2016:
            return bits
        start = struct.unpack_from('<I', self.header(height - 2016), 68)[0]
        end = struct.unpack_from('<I', previous, 68)[0]
        span = max(1209600 // 4, min(end - start, 1209600 * 4))
        return compact(min(self.limit, target(bits) * span // 1209600))

    def append(self, raw):
        if len(raw) != 80:
            raise ValueError('Invalid Bitcoin header length.')
        height = self.height + 1
        if height == 0 and raw != GENESIS[self.network]:
            raise ValueError('Wrong Bitcoin genesis.')
        version = struct.unpack_from('<i', raw)[0]
        timestamp, bits = struct.unpack_from('<II', raw, 68)
        threshold = target(bits)
        if bits != self.expected_bits() or threshold > self.limit:
            raise ValueError('Bitcoin difficulty rule failed.')
        digest = sha256d(raw)
        if int.from_bytes(digest, 'little') > threshold:
            raise ValueError('Bitcoin proof of work failed.')
        if height:
            if raw[4:36] != sha256d(self.header(height - 1)):
                raise ValueError('Bitcoin header does not extend its parent.')
            times = sorted(struct.unpack_from('<I', self.header(h), 68)[0]
                           for h in range(max(0, height - 11), height))
            if timestamp <= times[len(times) // 2]:
                raise ValueError('Bitcoin median-time rule failed.')
        if timestamp > time.time() + 7200:
            raise ValueError('Bitcoin header time is too far in the future.')
        if self.network == 'mainnet':
            for activation, minimum in ((227931, 2), (363725, 3), (388381, 4)):
                if height >= activation and version < minimum:
                    raise ValueError('Obsolete Bitcoin block version.')
        self.data.extend(raw)
        self.work.append((self.work[-1] if self.work else 0) + (1 << 256) // (threshold + 1))

    def extend(self, raw):
        if not raw or len(raw) % 80:
            raise ValueError('Invalid Bitcoin header batch.')
        for offset in range(0, len(raw), 80):
            self.append(raw[offset:offset + 80])

    def fork(self, height):
        self.header(height)
        branch = object.__new__(HeaderChain)
        branch.__dict__ = self.__dict__.copy()
        branch.data = self.data[:(height + 1) * 80]
        branch.work = self.work[:height + 1]
        return branch

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix('.tmp')
        with temporary.open('wb') as stream:
            stream.write(self.data)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(self.path)

    def update(self, peer, tip):
        height = tip.get('height')
        if type(height) is not int or not 0 <= height < 10_000_000:
            raise ValueError('Invalid remote Bitcoin height.')
        advertised = bytes.fromhex(tip['hex'])
        if len(advertised) != 80:
            raise ValueError('Invalid advertised Bitcoin header.')
        if height <= self.height and self.header(height) == advertised:
            return
        high = min(height, self.height)
        if bytes.fromhex(peer.call('blockchain.block.header', 0)) != GENESIS[self.network]:
            raise ValueError('Wrong remote Bitcoin genesis.')
        if bytes.fromhex(peer.call('blockchain.block.header', high)) == self.header(high):
            common = high
        else:
            low = 0
            while low + 1 < high:
                mid = (low + high) // 2
                if bytes.fromhex(peer.call('blockchain.block.header', mid)) == self.header(mid):
                    low = mid
                else:
                    high = mid
            common = low
        branch = self.fork(common)
        old_height = self.height
        batches = 0
        while branch.height < height:
            count = min(2016, height - branch.height)
            reply = peer.call('blockchain.block.headers', branch.height + 1, count)
            raw = bytes.fromhex(reply['hex'])
            if type(reply.get('count')) is not int or not 0 < reply['count'] <= count or len(raw) != 80 * reply['count']:
                raise ValueError('Incomplete Bitcoin header response.')
            branch.extend(raw)
            self.progress(branch.height, height)
            batches += 1
            # Verified straight extensions can resume after an interrupted download.
            # Reorganizations remain staged until the whole competing branch is valid.
            if common == old_height and batches % 32 == 0:
                self.data = branch.data.copy()
                self.work = branch.work.copy()
                self.save()
        if branch.header(height) != advertised:
            raise ValueError('Bitcoin tip changed during synchronization; retry.')
        if branch.work[-1] > self.work[-1]:
            self.data, self.work = branch.data, branch.work
            self.save()

    def verify_merkle(self, digest, height, proof):
        if not isinstance(proof,dict):raise ValueError('Invalid Bitcoin inclusion proof object.')
        if type(proof.get('block_height')) is not int or proof.get('block_height') != height or type(proof.get('pos')) is not int:
            raise ValueError('Wrong Bitcoin proof height or position.')
        branch, index = proof.get('merkle'), proof['pos']
        if not isinstance(branch, list) or len(branch) > 32 or not 0 <= index < 1 << len(branch):
            raise ValueError('Invalid Bitcoin Merkle branch.')
        value = bytes.fromhex(digest)[::-1]
        if len(value) != 32:
            raise ValueError('Invalid Bitcoin transaction ID.')
        for sibling in branch:
            other = bytes.fromhex(sibling)[::-1]
            if len(other) != 32:
                raise ValueError('Invalid Bitcoin Merkle hash.')
            value = sha256d(other + value if index & 1 else value + other)
            index >>= 1
        if value != self.header(height)[36:68]:
            raise ValueError('Bitcoin transaction inclusion proof failed.')
