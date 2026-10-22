"""Registered independent SUMUWW rules and preserved development networks.



REGTEST preserves the v0.8 genesis and all existing chain history. RETARGET_LAB

uses a separate genesis, identity, addresses and wire magic to test contextual

difficulty changes quickly. Its 16-second/16-block schedule is a laboratory

configuration. SUMUWW targets 600 seconds and activates DGW v3 at height 8064 with its own

fixed genesis and identity. A defined rules profile is not public deployment.

"""



from dataclasses import dataclass



from .block import Block, GENESIS_TIME, PROFILE_ID, REGTEST_BITS, genesis_block, mine_header

from .difficulty import validate_profile

from .primitives import Header, REGTEST_POW_LIMIT, RETARGET_INTERVAL, TARGET_TIMESPAN, UINT256_MAX, check_pow, encode_compact, merkle_root, subsidy

from .transaction import Transaction, TxInput, TxOutput





@dataclass(frozen=True)

class NetworkProfile:

    name: str

    profile_id: str

    genesis: Block

    pow_limit: int

    initial_bits: int

    no_retarget: bool

    retarget_interval: int

    target_timespan: int

    address_hrp: str

    message_magic: bytes

    asert_activation_height: int | None = None

    dgw_activation_height: int | None = None

    dgw_interval_activation_height: int | None = None

    dgw_retarget_interval: int = 1



    def __post_init__(self):
        if type(self.dgw_retarget_interval) is not int or not 1 <= self.dgw_retarget_interval <= 0xFFFFFFFF:
            raise ValueError('Invalid DGW retarget interval')
        if self.dgw_interval_activation_height is not None:
            if (type(self.dgw_interval_activation_height) is not int or
                    self.dgw_activation_height is None or
                    not self.dgw_activation_height <= self.dgw_interval_activation_height <= 0xFFFFFFFF):
                raise ValueError('Invalid DGW interval activation')
        elif self.dgw_retarget_interval != 1:
            raise ValueError('DGW interval requires activation')


        if self.dgw_activation_height is not None:

            if (type(self.dgw_activation_height) is not int

                    or not 25 <= self.dgw_activation_height <= 0xFFFFFFFF

                    or self.no_retarget or self.asert_activation_height is not None):

                raise ValueError('Invalid or conflicting DGW activation height')

        if self.asert_activation_height is not None:

            if (type(self.asert_activation_height) is not int

                    or not 2 <= self.asert_activation_height <= 0xFFFFFFFF

                    or self.no_retarget):

                raise ValueError('Invalid ASERT activation height')

        if not isinstance(self.name, str) or not self.name or len(self.name) > 32:

            raise ValueError('Network name must contain 1 to 32 characters')

        if not isinstance(self.profile_id, str) or not 1 <= len(self.profile_id.encode('utf-8')) <= 64:

            raise ValueError('Network profile ID must contain 1 to 64 UTF-8 bytes')

        if not isinstance(self.address_hrp, str) or not 1 <= len(self.address_hrp) <= 20 or any(c not in 'abcdefghijklmnopqrstuvwxyz' for c in self.address_hrp):

            raise ValueError('Network address prefix must use lowercase ASCII letters')

        if not isinstance(self.message_magic, bytes) or len(self.message_magic) != 4:

            raise ValueError('Network message magic must contain exactly 4 bytes')

        validate_profile(self.pow_limit, self.initial_bits, no_retarget=self.no_retarget,

                         interval=self.retarget_interval, target_timespan=self.target_timespan)

        if not isinstance(self.genesis, Block) or self.genesis.header.previous_hash != bytes(32) or self.genesis.header.bits != self.initial_bits:

            raise ValueError('Genesis does not match network difficulty or parent')

        if not self.genesis.transactions or len(self.genesis.transactions) != 1 or not self.genesis.transactions[0].is_coinbase():

            raise ValueError('Network genesis must contain one coinbase')

        root, mutated = merkle_root([self.genesis.transactions[0].txid()])

        if mutated or root != self.genesis.header.merkle_root or not check_pow(self.genesis.block_hash(), self.initial_bits, self.pow_limit):

            raise ValueError('Network genesis has an invalid commitment or proof of work')





def _laboratory_genesis() -> Block:

    message = b'DORA independent retarget laboratory 0.11'

    transaction = Transaction(1, (TxInput(bytes(32), 0xFFFFFFFF, b'\x00' + message),),

                              (TxOutput(subsidy(0), b'\x6a' + bytes([len(message)]) + message),), 0)

    root, _ = merkle_root([transaction.txid()])

    header = mine_header(Header(1, bytes(32), root, GENESIS_TIME, 0x2000FFFF, 0),

                         pow_limit=(1 << 248) - 1)

    return Block(header, (transaction,))





SUMUWW_POW_LIMIT = UINT256_MAX // (TARGET_TIMESPAN * 4)

SUMUWW_INITIAL_BITS = encode_compact(SUMUWW_POW_LIMIT)

SUMUWW_GENESIS_TIME = 1_790_985_600  # 2026-10-03 00:00:00 UTC; fixed, not runtime time.

SUMUWW_GENESIS_NONCE = 5_129_435  # Once mined; importing never repeats this search.

DGW_ACTIVATION_HEIGHT = 8064





def _sumuww_genesis() -> Block:

    message = b'DORA independent network 04 Oct 2026'

    transaction = Transaction(1, (TxInput(bytes(32), 0xFFFFFFFF, b'\x00' + message),),

                              (TxOutput(subsidy(0), b'\x6a' + bytes([len(message)]) + message),), 0)

    root, _ = merkle_root([transaction.txid()])

    header = Header(1, bytes(32), root, SUMUWW_GENESIS_TIME, SUMUWW_INITIAL_BITS,

                    SUMUWW_GENESIS_NONCE)

    return Block(header, (transaction,))





REGTEST = NetworkProfile('regtest', PROFILE_ID, genesis_block(), REGTEST_POW_LIMIT,

                         REGTEST_BITS, True, RETARGET_INTERVAL, TARGET_TIMESPAN,

                         'drt', bytes.fromhex('d0524709'))

RETARGET_LAB = NetworkProfile('retarget-lab', 'dora-retarget-lab-v0.11-p2wpkh',

                              _laboratory_genesis(), (1 << 248) - 1, 0x2000FFFF,

                              False, 16, 16, 'dtl', bytes.fromhex('d052470b'))

SUMUWW = NetworkProfile('dora', 'dora-independent-v0.12-p2wpkh', _sumuww_genesis(),

                     SUMUWW_POW_LIMIT, SUMUWW_INITIAL_BITS, False,

                     RETARGET_INTERVAL, TARGET_TIMESPAN, 'sumuww', bytes.fromhex('d052470c'),

                     dgw_activation_height=DGW_ACTIVATION_HEIGHT,
                     dgw_interval_activation_height=9000, dgw_retarget_interval=10)

_NETWORKS = {profile.name: profile for profile in (REGTEST, RETARGET_LAB, SUMUWW)}


NETWORK_NAMES = tuple(_NETWORKS) + ('sumuww',)





def get_network(network: str | NetworkProfile = 'regtest') -> NetworkProfile:

    """Return an exact registered profile; custom objects cannot change rules."""

    if isinstance(network, str):

        try:

            return _NETWORKS['dora' if network == 'sumuww' else network]

        except KeyError:

            raise ValueError('Unknown development network') from None

    if any(network is profile for profile in _NETWORKS.values()):

        return network

    raise ValueError('Network must be a registered name or exact registered profile')


# Import compatibility for already published SUMUWW scripts.
DORA = SUMUWW
