"""Single-host development chain, branch validation and atomic SQLite state.

The validator preserves P2WPKH and adds exact P2WSH HTLC at height 9100 on the public profile. Unsupported
features have their own error category. This is not a general Bitcoin script VM.
Side branches are fully replayed for validation: suitable for local tests only.
"""

from dataclasses import dataclass
from collections.abc import Sequence
from contextlib import contextmanager
from pathlib import Path
import json
import heapq
import sqlite3
import time

from .block import Block, MAX_BLOCK_WEIGHT, build_coinbase, has_witness, mine_header, witness_commitment
from .difficulty import expected_bits as contextual_expected_bits
from .errors import (InvalidTransaction, InvalidBlock, TransientValidationError,
                     MiningExhausted, MempoolFull, StorageError, UnsupportedFeature, ValidationError)
from .primitives import Header, MAX_MONEY, block_work, check_pow, checked_amount_sum, coinbase_is_mature, encode_compact_size, hash_to_display, merkle_root, require_int, sha256d, subsidy
from .profiles import get_network
from .transaction import Transaction, TxOutput, coinbase_height_prefix
from .wallet import verify_p2wpkh


MAX_MEMPOOL_TRANSACTIONS = 1000
MAX_MEMPOOL_BYTES = MAX_BLOCK_WEIGHT
MAX_VALIDATED_BRANCHES = 4
MAX_VALIDATED_COINS = 32_768
MAX_VALIDATED_PATH_ITEMS = 32_768
MAX_VALIDATED_BODY_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True)
class _PathPrefix(Sequence):
    """Immutable range over a validated path without copying each prefix."""
    items: tuple
    start: int
    stop: int

    def __len__(self):
        return max(0, self.stop - self.start)

    def __getitem__(self, index):
        selected = range(self.start, self.stop)[index]
        if isinstance(selected, range):
            if selected.step == 1:
                return _PathPrefix(self.items, selected.start, selected.stop)
            return tuple(self.items[position] for position in selected)
        return self.items[selected]


@dataclass(frozen=True)
class Coin:
    output: TxOutput
    height: int
    coinbase: bool


class _CoinState(dict):
    """UTXOs with exact counts of transaction ids that still own live outputs."""
    def __init__(self, *args, **kwargs):
        super().__init__()
        self._txids = {}
        self.update(*args, **kwargs)

    def __setitem__(self, key, value):
        if key not in self:
            self._txids[key[0]] = self._txids.get(key[0], 0) + 1
        super().__setitem__(key, value)

    def _forget(self, key):
        remaining = self._txids[key[0]] - 1
        if remaining:
            self._txids[key[0]] = remaining
        else:
            del self._txids[key[0]]

    def __delitem__(self, key):
        super().__delitem__(key)
        self._forget(key)

    def clear(self):
        super().clear()
        self._txids.clear()

    def pop(self, key, *default):
        if len(default) > 1:
            raise TypeError('pop expected at most 2 arguments')
        if key not in self:
            return super().pop(key, *default)
        value = self[key]
        del self[key]
        return value

    def popitem(self):
        key, value = super().popitem()
        self._forget(key)
        return key, value

    def setdefault(self, key, default=None):
        if key not in self:
            self[key] = default
        return self[key]

    def update(self, *args, **kwargs):
        for key, value in dict(*args, **kwargs).items():
            self[key] = value

    def __ior__(self, other):
        self.update(other)
        return self

    def copy(self):
        result = type(self)()
        dict.update(result, self)
        result._txids = self._txids.copy()
        return result

    @classmethod
    def fromkeys(cls, keys, value=None):
        return cls((key, value) for key in keys)


def _sum(values) -> int:
    try:
        return checked_amount_sum(values)
    except (TypeError, ValueError) as exc:
        raise InvalidTransaction(str(exc)) from exc


def _legacy_sigops(script: bytes) -> int:
    count = 0
    position = 0
    while position < len(script):
        opcode = script[position]
        position += 1
        if opcode <= 0x4E:
            if opcode <= 0x4B:
                length = opcode
            else:
                field = {0x4C: 1, 0x4D: 2, 0x4E: 4}[opcode]
                if position + field > len(script):
                    break
                length = int.from_bytes(script[position:position + field], 'little')
                position += field
            if position + length > len(script):
                break
            position += length
        elif opcode in (0xAC, 0xAD):
            count += 1
        elif opcode in (0xAE, 0xAF):
            count += 20
    return count


class Chain:
    def __init__(self, database: str | Path, *, clock=None, fault_hook=None, network='regtest', boundary_activation=None, htlc_activation=None, mempool_policy=None, spending_activation=None):
        self.network = get_network(network)
        from .mempool_policy import MempoolPolicy
        self.mempool_policy = mempool_policy or MempoolPolicy(minimum_rate=0 if self.network.name == 'regtest' else 1000)
        from .htlc_policy import activation_for
        self.htlc_activation = activation_for(self.network, htlc_activation)
        self.database = Path(database)
        self._preflight_database()
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self.clock = clock or (lambda: int(time.time()))
        self.fault_hook = fault_hook
        # Cache only an indexed path at a precise SQLite snapshot. Direct SQL
        # writes on this connection and commits by other writers invalidate it.
        self._indexed_path_cache = None
        self._summary_difficulty_cache = None
        self.connection = sqlite3.connect(str(self.database), isolation_level=None, timeout=10)
        try:
            self.connection.execute('PRAGMA journal_mode=WAL')
            self.connection.execute('PRAGMA synchronous=FULL')
            self.connection.execute('PRAGMA foreign_keys=ON')
            self._initialize()
            self.connection.execute('CREATE TABLE IF NOT EXISTS block_reward_fees (blockhash BLOB PRIMARY KEY, fees INTEGER NOT NULL)')
            self.connection.execute('CREATE TABLE IF NOT EXISTS mempool_replacements (old_txid BLOB PRIMARY KEY, new_txid BLOB NOT NULL, reason TEXT NOT NULL, seen INTEGER NOT NULL)')
            self.connection.execute('CREATE TABLE IF NOT EXISTS mempool_replacement_effects (old_txid BLOB PRIMARY KEY, effects BLOB NOT NULL)')
            from .link_state import LinkState as BoundaryState
            if self.network.name == 'dora':
                if boundary_activation not in (None, 9000): raise StorageError('Public boundary activation is fixed at 9000')
                boundary_activation=9000
            elif boundary_activation is not None and (type(boundary_activation) is not int or boundary_activation<1):
                raise StorageError('Invalid isolated boundary activation')
            self.boundary=BoundaryState(self,boundary_activation)
            from .htlc_policy import HtlcPolicy
            self.htlc_policy=HtlcPolicy(self,self.htlc_activation)
            from .spending_policy import SpendingPolicy
            self.spending_policy = SpendingPolicy(self, spending_activation)
            self.verify_persisted_state()
            self.boundary.verify_storage()
            self.connection.execute('BEGIN IMMEDIATE')
            try:
                verified_branches = dict(self._branch_entries())
                # Rebuild derived reward data only after the existing chain passed replay.
                self.connection.executemany('INSERT OR REPLACE INTO block_reward_fees VALUES (?,?)', self._verified_reward_fees.items())
                self._verified_reward_fees = {}
                # The mempool is recoverable local policy state, not consensus state.
                self._rebuild_mempool()
                cache_token = self._path_cache_token()
                self.connection.execute('COMMIT')
                self._publish_branches(cache_token, verified_branches, ())
            except BaseException:
                self.connection.execute('ROLLBACK')
                raise
        except BaseException:
            self.connection.close()
            raise

    def _preflight_database(self):
        """Check existing network identity before opening a writable connection.

        A checkpointed file is inspected immutably, without creating SQLite
        sidecars or changing its journal mode. An outstanding WAL requires a
        read-only SQLite snapshot so pending metadata is visible. SQLite may
        create shared-memory bookkeeping in that latter crash-recovery case.
        The normal initialization transaction checks the identity again.
        """
        if not self.database.is_file() or self.database.stat().st_size == 0:
            return
        wal = Path(str(self.database) + '-wal')
        pending_wal = wal.is_file() and wal.stat().st_size > 32
        uri = self.database.resolve().as_uri() + ('?mode=ro' if pending_wal else '?mode=ro&immutable=1')
        connection = sqlite3.connect(uri, uri=True, isolation_level=None, timeout=10)
        try:
            connection.execute('BEGIN')
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
            if 'metadata' not in tables:
                if tables:
                    raise StorageError('Existing database lacks network metadata')
                return
            values = dict(connection.execute("SELECT name,value FROM metadata WHERE name IN ('profile','schema','genesis')"))
            if (values.get('profile') != self.network.profile_id or
                    values.get('schema') != '1' or
                    values.get('genesis') != self.network.genesis.block_hash()):
                raise StorageError('Database network/profile/schema mismatch')
        finally:
            connection.close()

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _stage(self, name):
        if self.fault_hook:
            self.fault_hook(name)

    @contextmanager
    def read_snapshot(self):
        """Keep related reads at one committed SQLite revision.

        A Chain connection belongs to one thread/asyncio actor. Independent
        CLI processes use independent connections. Nested queries reuse an
        existing read or write transaction without committing its owner's work.
        """
        owns_transaction = not self.connection.in_transaction
        if owns_transaction:
            self.connection.execute('BEGIN')
        try:
            yield
        except BaseException:
            if owns_transaction and self.connection.in_transaction:
                self.connection.execute('ROLLBACK')
            raise
        else:
            if owns_transaction:
                self.connection.execute('COMMIT')

    @staticmethod
    def _require_hash(raw_hash):
        if not isinstance(raw_hash, bytes) or len(raw_hash) != 32:
            raise ValidationError('Expected exactly 32 raw hash bytes')
        return raw_hash

    def _initialize(self):
        c = self.connection
        c.execute('BEGIN IMMEDIATE')
        try:
            c.execute('CREATE TABLE IF NOT EXISTS metadata (name TEXT PRIMARY KEY, value BLOB NOT NULL)')
            c.execute('CREATE TABLE IF NOT EXISTS blocks (hash BLOB PRIMARY KEY, parent BLOB NOT NULL, height INTEGER NOT NULL, work TEXT NOT NULL, raw BLOB NOT NULL)')
            c.execute('CREATE TABLE IF NOT EXISTS utxos (txid BLOB NOT NULL, idx INTEGER NOT NULL, value INTEGER NOT NULL, script BLOB NOT NULL, height INTEGER NOT NULL, coinbase INTEGER NOT NULL, PRIMARY KEY(txid,idx))')
            c.execute('CREATE TABLE IF NOT EXISTS mempool (id INTEGER PRIMARY KEY AUTOINCREMENT, txid BLOB NOT NULL UNIQUE, raw BLOB NOT NULL)')
            profile = c.execute("SELECT value FROM metadata WHERE name='profile'").fetchone()
            genesis = self.network.genesis
            if profile is None:
                if c.execute('SELECT COUNT(*) FROM blocks').fetchone()[0]:
                    raise StorageError('Existing blocks lack network metadata')
                c.execute('INSERT INTO blocks VALUES (?,?,?,?,?)', (genesis.block_hash(), bytes(32), 0, str(block_work(self.network.initial_bits, self.network.pow_limit)), genesis.serialize()))
                for key, value in [('profile', self.network.profile_id), ('schema', '1'), ('genesis', genesis.block_hash()), ('tip', genesis.block_hash())]:
                    c.execute('INSERT INTO metadata VALUES (?,?)', (key, value))
            else:
                if profile[0] != self.network.profile_id or self._meta('schema') != '1' or self._meta('genesis') != genesis.block_hash():
                    raise StorageError('Database network/profile/schema mismatch')
            c.execute('COMMIT')
        except BaseException:
            c.execute('ROLLBACK')
            c.close()
            raise

    def _meta(self, name):
        row = self.connection.execute('SELECT value FROM metadata WHERE name=?', (name,)).fetchone()
        if row is None:
            raise StorageError(f'Missing database metadata: {name}')
        return row[0]

    @property
    def tip_hash(self):
        return self._meta('tip')

    def _row(self, block_hash):
        row = self.connection.execute('SELECT hash,parent,height,work,raw FROM blocks WHERE hash=?', (block_hash,)).fetchone()
        if row is None:
            raise ValidationError('Unknown parent or block')
        return row

    def has_block(self, raw_hash: bytes) -> bool:
        self._require_hash(raw_hash)
        with self.read_snapshot():
            return self.connection.execute('SELECT 1 FROM blocks WHERE hash=?', (raw_hash,)).fetchone() is not None

    def get_block(self, raw_hash: bytes) -> Block:
        self._require_hash(raw_hash)
        with self.read_snapshot():
            row = self._row(raw_hash)
            block = Block.deserialize(row[4])
            if block.block_hash() != row[0] or block.header.previous_hash != row[1]:
                raise StorageError('Block bytes/index mismatch')
            return block

    def has_mempool_transaction(self, txid: bytes) -> bool:
        self._require_hash(txid)
        with self.read_snapshot():
            return self.connection.execute('SELECT 1 FROM mempool WHERE txid=?', (txid,)).fetchone() is not None

    def get_mempool_transaction(self, txid: bytes) -> Transaction | None:
        self._require_hash(txid)
        with self.read_snapshot():
            row = self.connection.execute('SELECT raw FROM mempool WHERE txid=?', (txid,)).fetchone()
            if row is None:
                return None
            transaction = Transaction.deserialize(row[0])
            if transaction.txid() != txid:
                raise StorageError('Mempool bytes/index mismatch')
            return transaction

    def block_locator(self, tip_hash: bytes | None = None) -> tuple[bytes, ...]:
        if tip_hash is not None:
            self._require_hash(tip_hash)
        with self.read_snapshot():
            path, headers = self._query_ancestry(self.tip_hash if tip_hash is None else tip_hash)
            result = []
            position = len(path) - 1
            step = 1
            # Reserve the final slot for genesis, even for a very long branch.
            while position > 0 and len(result) < 31:
                row = path[position]
                self._query_header(row[0], headers)
                result.append(row[0])
                if len(result) > 10:
                    step *= 2
                position = max(position - step, 0)
            result.append(path[0][0])
            return tuple(result)

    def headers_after(self, locator: tuple[bytes, ...] | list[bytes],
                      stop: bytes = bytes(32), limit: int = 128) -> tuple[Header, ...]:
        if not isinstance(locator, (tuple, list)) or not 1 <= len(locator) <= 32:
            raise ValidationError('Locator must contain between 1 and 32 hashes')
        for raw_hash in locator:
            self._require_hash(raw_hash)
        self._require_hash(stop)
        if type(limit) is not int or not 1 <= limit <= 128:
            raise ValidationError('Header query limit must be between 1 and 128')
        with self.read_snapshot():
            path, headers = self._query_ancestry(self.tip_hash)
            heights = {row[0]: row[2] for row in path}
            common_height = next((heights[digest] for digest in locator if digest in heights), 0)
            result = []
            for row in path[common_height + 1:]:
                result.append(self._query_header(row[0], headers))
                if row[0] == stop or len(result) == limit:
                    break
            return tuple(result)

    def _query_ancestry(self, block_hash):
        """Read P2P hint ancestry from the already validated block index.

        Recursive SQL follows actual branch links using only hash/parent/height.
        Strictly decreasing heights bound malformed links and cycles. Selected
        hints read 80-byte headers, never all transaction bodies since genesis.
        This does not replace the complete paths used for startup, validation,
        difficulty, mining templates or block acceptance.
        """
        tip = self._summary_row(block_hash)
        if type(tip[2]) is not int or tip[2] < 0:
            raise StorageError('Height/index mismatch')
        headers = {block_hash: self._summary_header(tip)}
        path = tuple(self.connection.execute('''
            WITH RECURSIVE ancestry(hash,parent,height) AS (
                SELECT hash,parent,height FROM blocks WHERE hash=?
                UNION ALL
                SELECT block.hash,block.parent,block.height
                FROM blocks AS block JOIN ancestry AS child
                  ON block.hash=child.parent AND block.height=child.height-1
                WHERE child.height>0
            )
            SELECT hash,parent,height FROM ancestry ORDER BY height
        ''', (block_hash,)))
        if (len(path) != tip[2] + 1 or not path or path[0][2] != 0
                or path[0][0] != self._meta('genesis')
                or path[0][0] != self.network.genesis.block_hash()):
            raise StorageError('Disconnected or inconsistent block index')
        self._query_header(path[0][0], headers)
        return path, headers

    def _query_header(self, block_hash, headers):
        if block_hash not in headers:
            headers[block_hash] = self._summary_header(self._summary_row(block_hash))
        return headers[block_hash]

    def _path(self, block_hash):
        with self.read_snapshot():
            token = self._path_cache_token()
            cached = self._indexed_path_cache
            if cached is not None and cached[0] == token and cached[1][-1][0][0] == block_hash:
                return cached[1]
            branch = self._branch_entries(token).get(block_hash)
            if branch is not None:
                return branch[1]
            if cached is not None and cached[0] == token:
                # Proof jobs revisit many old parents. Their exact ancestry is
                # already validated in this immutable, same-snapshot path.
                # Match the hash as well as height; a fork must never borrow
                # another branch's prefix. SQL edits invalidate the token.
                height = self._row(block_hash)[2]
                if 0 <= height < len(cached[1]) and cached[1][height][0][0] == block_hash:
                    return cached[1][:height + 1]
            path = self._read_index_path(block_hash)
            if block_hash == self.tip_hash:
                self._indexed_path_cache = (token, path)
            return path

    def _path_cache_token(self):
        # data_version belongs to this connection and remains tied to its read
        # snapshot in WAL mode; total_changes also sees same-connection writes.
        return (self.connection.execute('PRAGMA data_version').fetchone()[0],
                self.connection.total_changes)

    def _read_index_path(self, block_hash):
        path = []
        seen = set()
        while True:
            if block_hash in seen:
                raise StorageError('Cycle in block index')
            seen.add(block_hash)
            row = self._row(block_hash)
            block = Block.deserialize(row[4])
            if block.block_hash() != row[0] or block.header.previous_hash != row[1]:
                raise StorageError('Block bytes/index mismatch')
            path.append((row, block))
            if row[2] == 0:
                if row[0] != self._meta('genesis') or block.serialize() != self.network.genesis.serialize():
                    raise StorageError('Unexpected genesis in block index')
                break
            block_hash = row[1]
        path.reverse()
        running_work = 0
        for height, (row, block) in enumerate(path):
            running_work += block_work(block.header.bits, self.network.pow_limit)
            if row[2] != height or int(row[3]) != running_work:
                raise StorageError('Height/chainwork index mismatch')
        return tuple(path)

    @staticmethod
    def _mtp(path):
        times = sorted(block.header.timestamp for _, block in path[-11:])
        return times[len(times) // 2]

    def _load_utxos(self):
        return _CoinState({(r[0], r[1]): Coin(TxOutput(r[2], r[3]), r[4], bool(r[5])) for r in self.connection.execute('SELECT txid,idx,value,script,height,coinbase FROM utxos')})

    @staticmethod
    def _has_live_outputs(state, txid):
        return txid in state._txids if isinstance(state, _CoinState) else any(key[0] == txid for key in state)

    def _replace_utxos(self, state):
        self.connection.execute('DELETE FROM utxos')
        self.connection.executemany('INSERT INTO utxos VALUES (?,?,?,?,?,?)', [(key[0], key[1], coin.output.value, coin.output.script_pubkey, coin.height, int(coin.coinbase)) for key, coin in state.items()])

    def _extend_utxos(self, block, state):
        """Apply only a validated active-tip extension's spent/new outpoints.

        Consult final state before inserting: a parent output created and spent
        by its child in this block must not be resurrected. Reorganizations use
        the complete validated replacement instead.
        """
        spent = [(item.prev_txid, item.prev_index)
                 for transaction in block.transactions[1:] for item in transaction.inputs]
        self.connection.executemany('DELETE FROM utxos WHERE txid=? AND idx=?', spent)
        added = []
        for transaction in block.transactions:
            txid = transaction.txid()
            for index in range(len(transaction.outputs)):
                coin = state.get((txid, index))
                if coin is not None:
                    added.append((txid, index, coin.output.value, coin.output.script_pubkey,
                                  coin.height, int(coin.coinbase)))
        self.connection.executemany('INSERT INTO utxos VALUES (?,?,?,?,?,?)', added)

    @staticmethod
    def _basic_transaction(transaction):
        if not transaction.inputs or not transaction.outputs:
            raise InvalidTransaction('Transaction must have inputs and outputs')
        if len(transaction.serialize(False)) * 4 > MAX_BLOCK_WEIGHT:
            raise InvalidTransaction('Base transaction size exceeds block weight')
        _sum(output.value for output in transaction.outputs)
        keys = [(i.prev_txid, i.prev_index) for i in transaction.inputs]
        if len(set(keys)) != len(keys):
            raise InvalidTransaction('Duplicate transaction input')
        if transaction.is_coinbase():
            if not 2 <= len(transaction.inputs[0].script_sig) <= 100:
                raise InvalidTransaction('Coinbase script length')
        elif any(key == (bytes(32), 0xFFFFFFFF) for key in keys):
            raise InvalidTransaction('Null input in normal transaction')

    def _check_finality(self, transaction, height, path):
        parent_mtp = self._mtp(path)
        lock_comparison = height if transaction.lock_time < 500_000_000 else parent_mtp
        if transaction.lock_time and transaction.lock_time >= lock_comparison and any(i.sequence != 0xFFFFFFFF for i in transaction.inputs):
            raise InvalidTransaction('Nonfinal transaction locktime')

    def _apply_transaction(self, transaction, state, height, path):
        self._basic_transaction(transaction)
        if transaction.is_coinbase():
            raise InvalidTransaction('Coinbase is not a normal transaction')
        self._check_finality(transaction, height, path)
        parent_mtp = self._mtp(path)
        coins = []
        for item in transaction.inputs:
            coin = state.get((item.prev_txid, item.prev_index))
            if coin is None:
                raise InvalidTransaction('Missing or already spent input')
            if coin.coinbase and not coinbase_is_mature(coin.height, height):
                raise InvalidTransaction('Immature coinbase input')
            if transaction.version >= 2 and not item.sequence & (1 << 31):
                relative = item.sequence & 0xFFFF
                if item.sequence & (1 << 22):
                    ancestor_height = max(coin.height - 1, 0)
                    coin_mtp = self._mtp(path[:ancestor_height + 1])
                    if parent_mtp < coin_mtp + (relative << 9):
                        raise InvalidTransaction('Relative time lock not satisfied')
                elif height < coin.height + relative:
                    raise InvalidTransaction('Relative height lock not satisfied')
            coins.append(coin)
        fee = _sum(coin.output.value for coin in coins) - _sum(o.value for o in transaction.outputs)
        if fee < 0:
            raise InvalidTransaction('Transaction creates value')
        for index, coin in enumerate(coins):
            template = None
            if self.spending_policy.active(height) and coin.output.script_pubkey[:2] == b'\x00\x20':
                from .spending import SpendingTemplate
                try: template = SpendingTemplate.parse(transaction.inputs[index].witness[-1])
                except (ValueError, TypeError, IndexError): pass
            if template is not None:
                from .spending import verify_spend as verify_template
                authorized = verify_template(transaction, index, coin.output)
            elif self.htlc_policy.active(height):
                from .htlc import verify_spend
                authorized = verify_spend(transaction, index, coin.output)
            else:
                authorized = verify_p2wpkh(transaction, index, coin.output)
            if not authorized:
                raise InvalidTransaction('Invalid spending signature or witness')
        txid = transaction.txid()
        if self._has_live_outputs(state, txid):
            raise InvalidTransaction('Live outputs would be overwritten')
        for item in transaction.inputs:
            del state[(item.prev_txid, item.prev_index)]
        for index, output in enumerate(transaction.outputs):
            if not (output.script_pubkey.startswith(b'\x6a') or len(output.script_pubkey) > 10_000):
                state[(txid, index)] = Coin(output, height, False)
        return fee

    def _validate_block_header(self, block, path, *, check_future=True, check_boundary=True):
        """Reject invalid work before replaying a potentially long fork's UTXOs."""
        parent = path[-1][1]
        if block.header.previous_hash != parent.block_hash() or block.header.bits != self._expected_bits_for_path(path):
            raise InvalidBlock('Unexpected parent or contextual nBits for the selected network')
        if block.header.version < 4:
            raise InvalidBlock('Modern block version required')
        if not check_pow(block.block_hash(), block.header.bits, self.network.pow_limit):
            raise InvalidBlock('Invalid proof of work')
        if block.header.timestamp <= self._mtp(path):
            raise InvalidBlock('Timestamp is not greater than parent MTP')
        if check_future and block.header.timestamp > self.clock() + 7200:
            raise TransientValidationError('Future timestamp; retry later, not permanently invalid')
        if check_boundary:
            self.boundary.validate(block,path)

    def _connect(self, block, state, path, *, check_future=True, check_boundary=True, reward_fees=None):
        self._validate_block_header(block, path, check_future=check_future,check_boundary=check_boundary)
        height = len(path)
        if not block.transactions or not block.transactions[0].is_coinbase() or any(t.is_coinbase() for t in block.transactions[1:]):
            raise ValidationError('Exactly one initial coinbase required')
        if block.weight() > MAX_BLOCK_WEIGHT:
            raise ValidationError('Block weight exceeds maximum')
        ids = [t.txid() for t in block.transactions]
        root, mutated = merkle_root(ids)
        if root != block.header.merkle_root or mutated:
            raise ValidationError('Invalid or mutated transaction Merkle commitment')
        id_set = set(ids)
        if any(self._has_live_outputs(state, txid) for txid in id_set):
            raise ValidationError('BIP30 live-output overwrite')
        coinbase = block.transactions[0]
        self._basic_transaction(coinbase)
        self._check_finality(coinbase, height, path)
        if not coinbase.inputs[0].script_sig.startswith(coinbase_height_prefix(height)):
            raise ValidationError('Coinbase height commitment mismatch')
        commitments = [o.script_pubkey[6:38] for o in coinbase.outputs if len(o.script_pubkey) >= 38 and o.script_pubkey.startswith(b'\x6a\x24\xaa\x21\xa9\xed')]
        if commitments:
            witness = coinbase.inputs[0].witness
            if len(witness) != 1 or len(witness[0]) != 32 or witness_commitment(block.transactions, witness[0]) != commitments[-1]:
                raise ValidationError('Invalid witness commitment')
        elif any(has_witness(t) for t in block.transactions):
            raise ValidationError('Witness data requires a coinbase commitment')
        sigops = 4 * sum(_legacy_sigops(i.script_sig) for t in block.transactions for i in t.inputs)
        sigops += 4 * sum(_legacy_sigops(o.script_pubkey) for t in block.transactions for o in t.outputs)
        fees = 0
        for transaction in block.transactions[1:]:
            fees += self._apply_transaction(transaction, state, height, path)
            sigops += len(transaction.inputs)  # Every supported spend is native P2WPKH.
            _sum((fees,))
        if sigops > 80_000:
            raise ValidationError('Block sigops cost exceeds maximum')
        if _sum(o.value for o in coinbase.outputs) > subsidy(height) + fees:
            raise ValidationError('Coinbase overclaims subsidy and fees')
        if reward_fees is not None:
            reward_fees[block.block_hash()] = fees
        for index, output in enumerate(coinbase.outputs):
            if not (output.script_pubkey.startswith(b'\x6a') or len(output.script_pubkey) > 10_000):
                state[(coinbase.txid(), index)] = Coin(output, height, True)
        return state

    def _replay(self, path, reward_fees=None):
        state = _CoinState()
        for index in range(1, len(path)):
            self._connect(path[index][1], state, _PathPrefix(path, 0, index), check_future=False, reward_fees=reward_fees)
        return state

    def _branch_entries(self, token=None):
        cached = getattr(self, '_validated_branch_cache', None)
        if self.fault_hook is not None or cached is None:
            return {}
        token = self._path_cache_token() if token is None else token
        return cached[1] if cached[0] == token else {}

    def _publish_branches(self, token, entries, additions):
        """Publish owned committed, copied states with aggregate storage caps.

        This helper is called only after successful verification/block commits.
        Arbitrary reads in an uncommitted write transaction never seed entries.
        """
        if self.fault_hook is not None:
            self._validated_branch_cache = None
            return
        entries = dict(entries)
        for digest, state, path in additions:
            entries.pop(digest, None)
            copied = state.copy()
            body_bytes = sum(len(row[4]) for row, _ in path)
            entries[digest] = (copied, path, body_bytes)
            while entries and (len(entries) > MAX_VALIDATED_BRANCHES
                    or sum(len(entry[0]) for entry in entries.values()) > MAX_VALIDATED_COINS
                    or sum(len(entry[1]) for entry in entries.values()) > MAX_VALIDATED_PATH_ITEMS
                    or sum(entry[2] for entry in entries.values()) > MAX_VALIDATED_BODY_BYTES):
                del entries[next(iter(entries))]
        self._validated_branch_cache = (token, entries)

    def _validated_state(self, block_hash, path, reward_fees=None):
        cached = self._branch_entries().get(block_hash)
        if cached is not None:
            return cached[0].copy()
        # Another writer's active extension keeps the existing incremental
        # path: authoritative UTXOs are loaded, not replayed from genesis.
        return self._load_utxos() if block_hash == self.tip_hash else self._replay(path, reward_fees)

    def verify_persisted_state(self):
        # Verification must independently reread every stored block, even if a
        # prior query populated a same-snapshot path cache.
        self._indexed_path_cache = None
        self._validated_branch_cache = None
        self.connection.execute('BEGIN')
        try:
            tip = self.tip_hash
            path = self._path(tip)
            reward_fees = {}
            expected = self._replay(path, reward_fees)
            if expected != self._load_utxos():
                raise StorageError('Stored UTXO does not match verified active-chain replay')
            token = self._path_cache_token()
            self.connection.execute('COMMIT')
            self._verified_reward_fees = reward_fees
            self._publish_branches(token, {}, ((tip, expected, path),))
        except BaseException:
            self._indexed_path_cache = None
            self._validated_branch_cache = None
            self.connection.execute('ROLLBACK')
            self.connection.close()
            raise
        return True

    def _state_for(self, block_hash):
        path = self._path(block_hash)
        state = self._validated_state(block_hash, path)
        return state, path

    def validate_boundary_candidate(self, block: Block):
        """Validate native work/spends before signing, without accepting it."""
        state,path=self._state_for(block.header.previous_hash)
        self._connect(block,state.copy(),path,check_boundary=False)
        self.boundary.assert_registered(block,path)
        if (self.boundary.required(len(path),block.header.previous_hash) and
                int(path[-1][0][3])+block_work(block.header.bits,self.network.pow_limit)
                <=int(self._row(self.tip_hash)[3])):
            raise InvalidBlock('Boundary candidate does not advance current verified work')
        return len(path)

    def accept_block(self, block: Block, *, boundary_envelope=None):
        with self.boundary.submission(block,boundary_envelope):
            activated = self._accept_block_with_boundary(block)
        # Completed attachments can arrive after either block. Native PoW
        # acceptance never depends on a signer or beacon response.
        self.boundary.ingest(boundary_envelope)
        return activated

    def _accept_block_with_boundary(self, block: Block):
        c = self.connection
        c.execute('BEGIN IMMEDIATE')
        try:
            prior_branches = dict(self._branch_entries())
            raw = block.serialize()
            # Parsing enforces the same canonical wire limits used by submitted bytes.
            block = Block.deserialize(raw)
            digest = block.block_hash()
            if c.execute('SELECT 1 FROM blocks WHERE hash=?', (digest,)).fetchone():
                c.execute('ROLLBACK')
                return False
            path = self._path(block.header.previous_hash)
            self._validate_block_header(block, path)
            old_tip = self.tip_hash
            extends_active = block.header.previous_hash == old_tip
            reward_fees = {}
            state = self._validated_state(block.header.previous_hash, path, reward_fees)
            fully_replayed = not extends_active or block.header.previous_hash in prior_branches
            parent_state = state.copy() if fully_replayed else None
            try:
                new_state = self._connect(block, state, path, reward_fees=reward_fees)
            except (TransientValidationError, UnsupportedFeature):
                raise
            except ValidationError as error:
                raise InvalidBlock(str(error)) from error
            parent_row = path[-1][0]
            work = int(parent_row[3]) + block_work(block.header.bits, self.network.pow_limit)
            old_path = path if extends_active else self._path(old_tip)
            if self.boundary.required(len(path),block.header.previous_hash) and work<=int(old_path[-1][0][3]):
                raise InvalidBlock('Boundary candidate does not advance current verified work')
            saved_row = (digest, block.header.previous_hash, len(path), str(work), raw)
            c.execute('INSERT INTO blocks VALUES (?,?,?,?,?)', saved_row)
            c.executemany('INSERT OR REPLACE INTO block_reward_fees VALUES (?,?)', reward_fees.items())
            self.boundary.store(block,len(path))
            new_path = path + ((saved_row, block),)
            # Mempool rebuilding adds pending spends to its supplied dictionary;
            # only the independently validated confirmed state belongs here.
            confirmed_state = new_state.copy() if fully_replayed else None
            self._stage('after_block_saved')
            activated = self.boundary.prefer(new_path, old_path)
            if activated:
                self.boundary.assert_registered(block,path,activating=True)
                if extends_active:
                    self._extend_utxos(block, new_state)
                else:
                    self._replace_utxos(new_state)
                self._stage('after_utxos_saved')
                c.execute("UPDATE metadata SET value=? WHERE name='tip'", (digest,))
                self._stage('after_tip_saved')
                confirmed = {t.txid() for t in block.transactions}
                if extends_active:
                    disconnected = []
                else:
                    new_hashes = {row[0] for row, _ in path} | {digest}
                    disconnected = [t for row, b in old_path if row[0] not in new_hashes for t in b.transactions[1:]]
                    confirmed.update(t.txid() for _, b in path for t in b.transactions)
                self._rebuild_mempool(disconnected, confirmed,
                                      state=new_state, path=new_path)
            # Publish the validated prefix only after commit. Capture the token
            # while this write transaction excludes external commits; a commit
            # racing after ours then changes data_version on the next lookup.
            cached_path = new_path if activated else old_path
            cache_token = self._path_cache_token()
            c.execute('COMMIT')
            self._indexed_path_cache = ((cache_token, cached_path)
                                        if self.fault_hook is None else None)
            self._publish_branches(cache_token, prior_branches,
                ((block.header.previous_hash, parent_state, path),
                 (digest, confirmed_state, new_path)) if fully_replayed else ())
            return activated
        except BaseException:
            self._indexed_path_cache = None
            self._validated_branch_cache = None
            if c.in_transaction:
                c.execute('ROLLBACK')
            raise

    def _rebuild_mempool(self, extra=(), confirmed=frozenset(), *, state=None, path=None):
        candidates = []
        for txid, raw in self.connection.execute('SELECT txid,raw FROM mempool ORDER BY id LIMIT ?', (MAX_MEMPOOL_TRANSACTIONS,)):
            try:
                tx = Transaction.deserialize(raw)
            except (TypeError, ValueError):
                continue
            if tx.txid() == txid:
                candidates.append(tx)
        candidates.extend(extra)
        self.connection.execute('DELETE FROM mempool')
        if not candidates:
            return
        if state is None or path is None:
            state, path = self._state_for(self.tip_hash)
        seen = set()
        size = 0
        # Retry unresolved children after their disconnected parents have entered.
        # A bounded local pool and full state copies suit this prototype only.
        while candidates and len(seen) < MAX_MEMPOOL_TRANSACTIONS:
            pending = []
            accepted = 0
            for tx in candidates:
                if tx.txid() in confirmed or tx.txid() in seen:
                    continue
                raw = tx.serialize()
                if size + len(raw) > MAX_MEMPOOL_BYTES or len(seen) >= MAX_MEMPOOL_TRANSACTIONS:
                    continue
                trial = state.copy()
                try:
                    fee = self._apply_transaction(tx, trial, len(path), path)
                    self.mempool_policy.check_fee(tx, fee)
                except ValidationError:
                    pending.append(tx)
                    continue
                except UnsupportedFeature:
                    continue
                self.connection.execute('INSERT INTO mempool(txid,raw) VALUES (?,?)', (tx.txid(), raw))
                state = trial
                size += len(raw)
                seen.add(tx.txid())
                accepted += 1
            if not accepted:
                break
            candidates = pending

    def submit_transaction(self, transaction, *, before_submit=None, test_only=False, allow_replacement=True):
        from .mempool_policy import replacement, vsize, MAX_REPLACEMENT_EFFECT_BYTES
        self.connection.execute('BEGIN IMMEDIATE')
        try:
            if before_submit is not None:
                before_submit(self)
            digest = transaction.txid()
            if self.connection.execute('SELECT 1 FROM mempool WHERE txid=?', (digest,)).fetchone():
                raise InvalidTransaction('Transaction already in mempool')
            raw = transaction.serialize()
            tip = self.tip_hash
            token = (*self._path_cache_token(), tip)
            cached = getattr(self, '_validated_mempool_cache', None)
            if cached is not None and cached[0] == token:
                _, verified_state, path, count, size = cached
                state = verified_state.copy()
            else:
                entries = list(self.connection.execute('SELECT raw FROM mempool ORDER BY id'))
                count, size = len(entries), sum(len(row[0]) for row in entries)
                state = path = None
            removed = set()
            try:
                if count >= MAX_MEMPOOL_TRANSACTIONS or size + len(raw) > MAX_MEMPOOL_BYTES:
                    raise MempoolFull('Local mempool resource limit')
                if state is None:
                    state, path = self._state_for(tip)
                    for row in entries:
                        self._apply_transaction(Transaction.deserialize(row[0]), state, len(path), path)
                if all((i.prev_txid,i.prev_index) in state for i in transaction.inputs):
                    preliminary_fee = sum(state[(i.prev_txid,i.prev_index)].output.value for i in transaction.inputs) - sum(o.value for o in transaction.outputs)
                    self.mempool_policy.check_fee(transaction, preliminary_fee)
                fee = self._apply_transaction(transaction, state, len(path), path)
                self.mempool_policy.check_fee(transaction, fee)
            except (InvalidTransaction, MempoolFull):
                if not allow_replacement: raise
                pool = tuple(Transaction.deserialize(row[0]) for row in
                             self.connection.execute('SELECT raw FROM mempool ORDER BY id'))
                result = replacement(self, transaction, pool)
                if result is None:
                    raise
                state, path, kept, removed, fee, effects = result
                count, size = len(kept), sum(len(tx.serialize()) for tx in kept)
                if count >= MAX_MEMPOOL_TRANSACTIONS or size + len(raw) > MAX_MEMPOOL_BYTES:
                    raise MempoolFull('Local mempool resource limit')
            if test_only:
                self.connection.execute('ROLLBACK')
                return {'txid': hash_to_display(digest), 'allowed': True,
                        'fee_units': fee, 'vsize': vsize(transaction),
                        'replaces': sorted(hash_to_display(item) for item in removed)}
            if removed:
                points = {i.outpoint() for i in transaction.inputs}
                direct = {tx.txid() for tx in pool if points.intersection(i.outpoint() for i in tx.inputs)}
                self.connection.executemany('INSERT OR REPLACE INTO mempool_replacements VALUES (?,?,?,?)',
                    ((item, digest, 'conflict' if item in direct else 'ancestor_replaced', int(self.clock())) for item in removed))
                self.connection.execute('DELETE FROM mempool_replacements WHERE old_txid NOT IN (SELECT old_txid FROM mempool_replacements ORDER BY seen DESC,rowid DESC LIMIT 1000)')
                self.connection.executemany('INSERT OR REPLACE INTO mempool_replacement_effects VALUES (?,?)', effects.items())
                self.connection.execute('DELETE FROM mempool_replacement_effects WHERE old_txid NOT IN (SELECT old_txid FROM mempool_replacements)')
                retained = 0
                evicted = []
                for old, length in self.connection.execute('''SELECT e.old_txid,length(e.effects) FROM mempool_replacement_effects e
                    JOIN mempool_replacements r ON r.old_txid=e.old_txid ORDER BY r.seen DESC,r.rowid DESC'''):
                    retained += length
                    if retained > MAX_REPLACEMENT_EFFECT_BYTES: evicted.append((old,))
                self.connection.executemany('DELETE FROM mempool_replacement_effects WHERE old_txid=?', evicted)
                self.connection.executemany('DELETE FROM mempool WHERE txid=?', ((item,) for item in removed))
            self.connection.execute('INSERT INTO mempool(txid,raw) VALUES (?,?)', (digest, raw))
            # Capture under the write lock: another connection may commit as
            # soon as COMMIT returns. Never tag an old overlay with its version.
            committed_token = (*self._path_cache_token(), tip)
            self.connection.execute('COMMIT')
            self._validated_mempool_cache = (committed_token, state, path, count + 1, size + len(raw))
            return digest
        except BaseException:
            if self.connection.in_transaction:
                self.connection.execute('ROLLBACK')
            raise

    def test_mempool_accept(self, transaction):
        from .mempool_policy import MempoolPolicyError, vsize
        try:
            return self.submit_transaction(transaction, test_only=True)
        except (ValidationError, UnsupportedFeature) as error:
            category = ('capacity' if isinstance(error, MempoolFull) else
                        'policy' if isinstance(error, MempoolPolicyError) else 'validation')
            return {'txid': hash_to_display(transaction.txid()), 'allowed': False,
                    'vsize': vsize(transaction), 'reject_category': category,
                    'reject_reason': str(error)}

    def mempool_entry(self, digest):
        from .mempool_policy import vsize
        with self.read_snapshot():
            pool = self.mempool_transactions()
            values = {point: coin.output.value for point, coin in self._load_utxos().items()}
            ids = {tx.txid() for tx in pool}
            for tx in pool:
                fee = sum(values[(i.prev_txid, i.prev_index)] for i in tx.inputs) - sum(o.value for o in tx.outputs)
                values.update({(tx.txid(), i): out.value for i, out in enumerate(tx.outputs)})
                if tx.txid() == digest:
                    descendants = {digest}
                    while True:
                        following = {item.txid() for item in pool if any(i.prev_txid in descendants for i in item.inputs)}
                        if following.issubset(descendants): break
                        descendants.update(following)
                    return {'txid': hash_to_display(digest), 'fee_units': fee, 'amount_unit': 'yugeon',
                            'vsize': vsize(tx), 'weight': tx.weight(),
                            'depends': sorted({hash_to_display(i.prev_txid) for i in tx.inputs if i.prev_txid in ids}),
                            'descendant_count': len(descendants) - 1, 'replaceable': True}
            return None

    def transaction_status(self, digest):
        with self.read_snapshot():
            tip = self.tip_hash
            path = self._path(tip)
            result = {'txid': hash_to_display(digest), 'bestblockhash': hash_to_display(tip),
                      'height': len(path) - 1, 'confirmations': 0}
            for height, (_, block) in enumerate(path):
                if any(tx.txid() == digest for tx in block.transactions):
                    return dict(result, status='confirmed', blockhash=hash_to_display(block.block_hash()),
                                block_height=height, confirmations=len(path)-height)
            if self.has_mempool_transaction(digest):
                return dict(result, status='mempool')
            event = self.connection.execute('SELECT new_txid,reason FROM mempool_replacements WHERE old_txid=?', (digest,)).fetchone()
            if event:
                return dict(result, status='replaced', replaced_by=hash_to_display(event[0]), reason=event[1])
            return dict(result, status='unknown')

    def mempool_transactions(self):
        with self.read_snapshot():
            return tuple(Transaction.deserialize(row[0]) for row in self.connection.execute('SELECT raw FROM mempool ORDER BY id'))

    def mempool_info(self):
        with self.read_snapshot():
            count, size = self.connection.execute(
                'SELECT count(*),COALESCE(sum(length(raw)),0) FROM mempool').fetchone()
            return {'size': count, 'bytes': size,
                    'max_transactions': MAX_MEMPOOL_TRANSACTIONS, 'max_bytes': MAX_MEMPOOL_BYTES,
                    'remaining_transactions': max(0, MAX_MEMPOOL_TRANSACTIONS - count),
                    'remaining_bytes': max(0, MAX_MEMPOOL_BYTES - size),
                    'full': count >= MAX_MEMPOOL_TRANSACTIONS or size >= MAX_MEMPOOL_BYTES}

    @staticmethod
    def _transaction_sigops_cost(transaction):
        legacy = sum(_legacy_sigops(i.script_sig) for i in transaction.inputs)
        legacy += sum(_legacy_sigops(o.script_pubkey) for o in transaction.outputs)
        # The caller validates all normal inputs as native P2WPKH first.
        witness_cost = 0
        if not transaction.is_coinbase():
            from .spending import SpendingTemplate
            for item in transaction.inputs:
                try: witness_cost += len(SpendingTemplate.parse(item.witness[-1]).pubkeys)
                except (ValueError, TypeError, IndexError): witness_cost += 1
        return legacy * 4 + witness_cost

    def _select_mempool_transactions(self, pay_script, state, path, extra_nonce):
        """Select by ancestor-package fee/vbyte, with FIFO ties and exact budgets.

        This is local mining policy; zero fees are still valid. Validate the
        bounded pool once in parent-first order, then cache package membership
        and totals. Selecting an ancestor removes its costs from descendant
        packages without repeating signatures. Any subset closed over ancestors
        remains valid: the validated overlay has already excluded conflicts.
        """
        entries = []
        for txid, raw in self.connection.execute('SELECT txid,raw FROM mempool ORDER BY id LIMIT ?', (MAX_MEMPOOL_TRANSACTIONS,)):
            try:
                transaction = Transaction.deserialize(raw)
            except (TypeError, ValueError, UnsupportedFeature):
                continue
            if transaction.txid() == txid:
                entries.append(transaction)
        indexes = {transaction.txid(): index for index, transaction in enumerate(entries)}
        parents = [{indexes[item.prev_txid] for item in transaction.inputs if item.prev_txid in indexes}
                   for transaction in entries]
        children = [set() for _ in entries]
        remaining_parents = [len(items) for items in parents]
        for index, dependencies in enumerate(parents):
            for parent in dependencies:
                children[parent].add(index)
        ready = [index for index, count in enumerate(remaining_parents) if not count]
        heapq.heapify(ready)
        overlay = state.copy()
        order = []
        ancestor_masks = [0] * len(entries)
        # Each member's fee, virtual size, weight, sigops and witness presence.
        costs = [None] * len(entries)
        while ready:
            index = heapq.heappop(ready)
            transaction = entries[index]
            if all(costs[parent] is not None for parent in parents[index]):
                try:
                    fee = self._apply_transaction(transaction, overlay, len(path), path)
                except (ValidationError, UnsupportedFeature):
                    pass
                else:
                    weight = transaction.weight()
                    costs[index] = (fee, (weight + 3) // 4, weight,
                                    self._transaction_sigops_cost(transaction), int(has_witness(transaction)))
                    ancestors = 1 << index
                    for parent in parents[index]:
                        ancestors |= ancestor_masks[parent]
                    ancestor_masks[index] = ancestors
                    order.append(index)
            for child in children[index]:
                remaining_parents[child] -= 1
                if remaining_parents[child] == 0:
                    heapq.heappush(ready, child)

        def members(mask):
            while mask:
                bit = mask & -mask
                yield bit.bit_length() - 1
                mask ^= bit

        descendant_masks = [0] * len(entries)
        for index in reversed(order):
            descendants = 1 << index
            for child in children[index]:
                descendants |= descendant_masks[child]
            descendant_masks[index] = descendants
        package_masks = ancestor_masks.copy()
        package_costs = [None] * len(entries)
        candidates = 0
        for index in order:
            package_costs[index] = [sum(costs[member][field] for member in members(package_masks[index]))
                                    for field in range(5)]
            candidates |= 1 << index

        selected = []
        fees = 0
        selected_weight = 0
        selected_sigops = 0
        include_witness = False
        while candidates:
            best = None
            # Ascending arrival indexes make exact equal-rate ties FIFO. With
            # at most 1,000 entries the scan is bounded, without a stale heap.
            for index in members(candidates):
                if best is None or package_costs[index][0] * package_costs[best][1] > package_costs[best][0] * package_costs[index][1]:
                    best = index
            package = package_masks[best]
            package_fee, _, package_weight, package_sigops, package_witness = package_costs[best]
            try:
                next_fees = _sum((fees, package_fee))
                with_witness = include_witness or bool(package_witness)
                reserved = bytes(32) if with_witness else None
                # The commitment's bytes do not affect the template size.
                commitment = bytes(32) if with_witness else None
                coinbase = build_coinbase(len(path), pay_script, next_fees, extra_nonce, reserved, commitment)
                coinbase = self.boundary.template_coinbase(coinbase, path)
            except (ValidationError, UnsupportedFeature):
                candidates &= ~descendant_masks[best]
                continue
            weight = (80 + len(encode_compact_size(len(selected) + package.bit_count() + 1))) * 4
            weight += coinbase.weight() + selected_weight + package_weight
            sigops = self._transaction_sigops_cost(coinbase) + selected_sigops + package_sigops
            if weight > MAX_BLOCK_WEIGHT or sigops > 80_000:
                # More selected transactions cannot make this package fit.
                # Its ancestors may still fit independently; its children do not.
                candidates &= ~descendant_masks[best]
                continue
            selected.extend(entries[index] for index in order if package & (1 << index))
            fees = next_fees
            selected_weight += package_weight
            selected_sigops += package_sigops
            include_witness = with_witness
            candidates &= ~package
            affected = 0
            for index in members(package):
                affected |= descendant_masks[index]
            for index in members(affected & candidates):
                removed = package_masks[index] & package
                package_masks[index] &= ~package
                for member in members(removed):
                    for field in range(5):
                        package_costs[index][field] -= costs[member][field]
        return tuple(selected), fees

    def make_block(self, pay_script: bytes, transactions=None, *, parent_hash=None, timestamp=None, extra_nonce=0, mining_cancel=None, mining_backend=None, staged_parent=None):
        """Freeze each template in a short snapshot, then mine without a read lock.

        Exhausting one header's nonce space changes the coinbase extra nonce.
        A default parent is refreshed on each attempt; an explicit branch parent
        remains selected. Cancellation is never treated as nonce exhaustion.
        """
        require_int(extra_nonce, 0, 0xFFFFFFFF)
        if mining_cancel is not None and not callable(mining_cancel):
            raise TypeError('Mining cancellation check must be callable')
        transactions = None if transactions is None else tuple(transactions)
        while True:
            if mining_cancel is not None and mining_cancel():
                raise RuntimeError('Mining cancelled')
            with self.read_snapshot():
                template = self._block_template(pay_script, transactions,
                                                parent_hash=parent_hash, timestamp=timestamp,
                                                extra_nonce=extra_nonce, staged_parent=staged_parent)
            if mining_backend is not None and getattr(mining_backend, 'mode', None) == 'asic':
                # Stratum uses 8 extra-nonce bytes rather than the local CPU's 4.
                # Reserve the additional 16 weight units; drop only dependency
                # ordered tail transactions and recompute actual included fees.
                while template.weight() + 16 > MAX_BLOCK_WEIGHT:
                    with self.read_snapshot():
                        template = self._block_template(pay_script, template.transactions[1:-1],
                                                        parent_hash=parent_hash, timestamp=timestamp,
                                                        extra_nonce=extra_nonce, staged_parent=staged_parent)
            try:
                if mining_backend is not None:
                    return mining_backend.mine(template, self.network.pow_limit, mining_cancel)
                header = mine_header(template.header, max_attempts=1 << 32,
                                     pow_limit=self.network.pow_limit,
                                     cancel_check=mining_cancel)
            except MiningExhausted:
                extra_nonce = (extra_nonce + 1) & 0xFFFFFFFF
                if extra_nonce == 0:
                    timestamp = max(template.header.timestamp + 1, self.clock())
                continue
            return Block(header, template.transactions)

    def _block_template(self, pay_script: bytes, transactions=None, *, parent_hash=None, timestamp=None, extra_nonce=0, staged_parent=None):
        parent_hash = parent_hash or self.tip_hash
        if staged_parent is None:
            state, path = self._state_for(parent_hash)
        else:
            # A transient native-validation overlay only. No unsigned block,
            # registration, UTXO or tip is ever written to SQLite here.
            if parent_hash != staged_parent.block_hash():
                raise InvalidBlock('Staged mining parent hash mismatch')
            state, path = self._state_for(staged_parent.header.previous_hash)
            self.boundary.assert_registered(staged_parent,path)
            state = self._connect(staged_parent,state.copy(),path,check_boundary=False)
            row = (parent_hash,staged_parent.header.previous_hash,len(path),
                   str(int(path[-1][0][3])+block_work(staged_parent.header.bits,self.network.pow_limit)),
                   staged_parent.serialize())
            path = path + ((row,staged_parent),)
        height = len(path)
        if transactions is None and (parent_hash == self.tip_hash or staged_parent is not None):
            txs, fees = self._select_mempool_transactions(pay_script, state, path, extra_nonce)
        else:
            txs = tuple(transactions or ())
            fees = 0
            for tx in txs:
                fees = _sum((fees, self._apply_transaction(tx, state, height, path)))
        reserved = bytes(32) if any(has_witness(t) for t in txs) else None
        coinbase = build_coinbase(height, pay_script, fees, extra_nonce, reserved)
        all_txs = (coinbase,) + txs
        if reserved is not None:
            commitment = witness_commitment(all_txs, reserved)
            coinbase = build_coinbase(height, pay_script, fees, extra_nonce, reserved, commitment)
            all_txs = (coinbase,) + txs
        coinbase = self.boundary.template_coinbase(coinbase, path)
        all_txs = (coinbase,) + txs
        root, _ = merkle_root([t.txid() for t in all_txs])
        parent = path[-1][1]
        timestamp = max(parent.header.timestamp + 1, self._mtp(path) + 1, self.clock()) if timestamp is None else timestamp
        bits = self._expected_bits_for_path(path)
        header = Header(4, parent_hash, root, timestamp, bits, 0)
        block = Block(header, all_txs)
        if block.weight() > MAX_BLOCK_WEIGHT:
            raise ValidationError('Block template weight exceeds maximum')
        if sum(self._transaction_sigops_cost(tx) for tx in all_txs) > 80_000:
            raise ValidationError('Block template sigops cost exceeds maximum')
        return block

    def _expected_bits_for_path(self, path):
        # Non-boundaries need only the parent. A boundary walks precisely its
        # preceding interval, never every header since genesis.
        relevant = (path[-1],) if (self.network.no_retarget or
                                   len(path) % self.network.retarget_interval) else path[-self.network.retarget_interval:]
        if (self.network.asert_activation_height is not None
                and len(path) >= self.network.asert_activation_height):
            relevant = path[self.network.asert_activation_height - 2:]
        if (self.network.dgw_activation_height is not None
                and len(path) >= self.network.dgw_activation_height):
            relevant = path[-24:]
        headers = {row[0]: block.header for row, block in relevant}
        return contextual_expected_bits(len(path) - 1, path[-1][0][0], headers.get,
                                        self.network.pow_limit, self.network.initial_bits,
                                        no_retarget=self.network.no_retarget,
                                        interval=self.network.retarget_interval,
                                        target_timespan=self.network.target_timespan,
                                        asert_activation_height=self.network.asert_activation_height,
                                        dgw_activation_height=self.network.dgw_activation_height,
                                        dgw_interval_activation_height=self.network.dgw_interval_activation_height,
                                        dgw_retarget_interval=self.network.dgw_retarget_interval)

    def expected_bits(self, parent_hash: bytes | None = None) -> int:
        """Required child difficulty for a known parent on its actual branch."""
        if parent_hash is not None:
            self._require_hash(parent_hash)
        with self.read_snapshot():
            return self._expected_bits_for_path(self._path(self.tip_hash if parent_hash is None else parent_hash))

    def mine(self, pay_script: bytes, count: int = 1):
        if type(count) is not int or not 1 <= count <= 10_000:
            raise ValueError('Local generation count must be between 1 and 10000')
        blocks = []
        for _ in range(count):
            block = self.make_block(pay_script)
            self.accept_block(block)
            blocks.append(block)
        return blocks

    def list_utxos(self, script_pubkey=None):
        with self.read_snapshot():
            query = 'SELECT txid,idx,value,script,height,coinbase FROM utxos'
            arguments = ()
            if script_pubkey is not None:
                query += ' WHERE script=?'
                arguments = (script_pubkey,)
            rows = self.connection.execute(query + ' ORDER BY txid,idx', arguments)
            return [((row[0], row[1]), Coin(TxOutput(row[2], row[3]), row[4], bool(row[5])))
                    for row in rows]

    def balance(self, script_pubkey, *, mature_only=False):
        with self.read_snapshot():
            next_height = self._row(self.tip_hash)[2] + 1
            return _sum(coin.output.value for _, coin in self.list_utxos(script_pubkey) if not mature_only or not coin.coinbase or coinbase_is_mature(coin.height, next_height))

    def state_commitment(self):
        with self.read_snapshot():
            entries = [[hash_to_display(key[0]), key[1], coin.output.value, coin.output.script_pubkey.hex(), coin.height, coin.coinbase] for key, coin in self.list_utxos()]
            return sha256d(json.dumps(entries, separators=(',', ':')).encode()).hex()

    def _summary_next_bits(self, parent_row, parent_header):
        """Read only difficulty's required ancestry from the validated index.

        This display query does not validate or accept blocks. Constructor and
        block-acceptance validation keep their existing complete chain paths.
        Non-boundaries read one header; boundaries follow the preceding interval
        on this parent's actual branch using the ordinary difficulty function.
        """
        # Cache the result only for the exact SQLite revision and parent.
        # Repeated UI polls need not walk the fixed ASERT anchor again. Both
        # local SQL changes and commits from another connection invalidate it.
        cache_key = None
        if (self.network.asert_activation_height is not None
                and parent_row[2] + 1 >= self.network.asert_activation_height):
            cache_key = (self._path_cache_token(), parent_row[0])
            if (self._summary_difficulty_cache is not None
                    and self._summary_difficulty_cache[0] == cache_key):
                return self._summary_difficulty_cache[1]
        cursor = parent_row
        headers = {parent_row[0]: parent_header}

        def lookup(digest):
            nonlocal cursor
            if digest in headers:
                return headers[digest]
            if digest != cursor[1] or cursor[2] <= 0:
                raise StorageError('Unexpected difficulty ancestor in block index')
            row = self._summary_row(digest)
            if row[2] != cursor[2] - 1:
                raise StorageError('Difficulty ancestor height/index mismatch')
            header = self._summary_header(row)
            headers[digest] = header
            cursor = row
            return header

        result = contextual_expected_bits(parent_row[2], parent_row[0], lookup,
                                        self.network.pow_limit, self.network.initial_bits,
                                        no_retarget=self.network.no_retarget,
                                        interval=self.network.retarget_interval,
                                        target_timespan=self.network.target_timespan,
                                        asert_activation_height=self.network.asert_activation_height,
                                        dgw_activation_height=self.network.dgw_activation_height,
                                        dgw_interval_activation_height=self.network.dgw_interval_activation_height,
                                        dgw_retarget_interval=self.network.dgw_retarget_interval)
        if cache_key is not None:
            self._summary_difficulty_cache = (cache_key, result)
        return result

    def _summary_header(self, row):
        header = Header.deserialize(row[4][:80])
        if header.digest() != row[0] or header.previous_hash != row[1]:
            raise StorageError('Block header/index mismatch')
        if row[2] == 0 and (row[0] != self.network.genesis.block_hash()
                           or header != self.network.genesis.header):
            raise StorageError('Unexpected genesis in block index')
        return header

    def _summary_row(self, block_hash):
        # Do not materialize complete transaction bodies merely to display
        # difficulty. In particular a retarget reads at most one interval of
        # 80-byte headers, even when the stored blocks are large.
        row = self.connection.execute(
            'SELECT hash,parent,height,work,substr(raw,1,80) FROM blocks WHERE hash=?',
            (block_hash,)).fetchone()
        if row is None:
            raise ValidationError('Unknown parent or block')
        return row

    def summary(self):
        """Cheap snapshot for periodic UI polling, without a UTXO commitment.

        Full diagnostic info and persisted-state verification remain available
        independently. Avoid touching the indexed-path cache here: another
        connection's new block must not trigger a genesis walk on each refresh.
        """
        with self.read_snapshot():
            row = self._summary_row(self.tip_hash)
            header = self._summary_header(row)
            return {'network': self.network.name, 'profile': self.network.profile_id,
                    'height': row[2], 'tip': hash_to_display(row[0]), 'chainwork': row[3],
                    'bits': f'{header.bits:08x}',
                    'next_bits': f'{self._summary_next_bits(row, header):08x}',
                    'asert_activation_height': self.network.asert_activation_height,
                    'dgw_activation_height': self.network.dgw_activation_height,
                    'dgw_interval_activation_height': self.network.dgw_interval_activation_height,
                    'dgw_retarget_interval': self.network.dgw_retarget_interval,
                    'no_retarget': self.network.no_retarget,
                    'retarget_interval': self.network.retarget_interval,
                    'target_timespan': self.network.target_timespan,
                    'utxos': self.connection.execute('SELECT COUNT(*) FROM utxos').fetchone()[0],
                    'mempool': self.connection.execute('SELECT COUNT(*) FROM mempool').fetchone()[0],
                    'spending_support': ('native P2WPKH / SIGHASH_ALL plus exact P2WSH HTLC v1' if self.htlc_policy.active(row[2]) else 'native P2WPKH / SIGHASH_ALL only'), 'conditional_spend': self.htlc_policy.info(row[2]), 'extended_spending': self.spending_policy.info(row[2]), 'public_network_ready': False}

    def info(self):
        with self.read_snapshot():
            row = self._row(self.tip_hash)
            header = Block.deserialize(row[4]).header
            return {'network': self.network.name, 'profile': self.network.profile_id,
                    'height': row[2], 'tip': hash_to_display(row[0]), 'chainwork': row[3],
                    'bits': f'{header.bits:08x}', 'next_bits': f'{self.expected_bits():08x}',
                    'asert_activation_height': self.network.asert_activation_height,
                    'dgw_activation_height': self.network.dgw_activation_height,
                    'dgw_interval_activation_height': self.network.dgw_interval_activation_height,
                    'dgw_retarget_interval': self.network.dgw_retarget_interval,
                    'no_retarget': self.network.no_retarget,
                    'retarget_interval': self.network.retarget_interval,
                    'target_timespan': self.network.target_timespan,
                    'utxos': len(self.list_utxos()), 'utxo_commitment': self.state_commitment(),
                    'mempool': self.connection.execute('SELECT COUNT(*) FROM mempool').fetchone()[0],
                    'spending_support': ('native P2WPKH / SIGHASH_ALL plus exact P2WSH HTLC v1' if self.htlc_policy.active(row[2]) else 'native P2WPKH / SIGHASH_ALL only'), 'conditional_spend': self.htlc_policy.info(row[2]), 'extended_spending': self.spending_policy.info(row[2]), 'public_network_ready': False}
