# SUMUWW Basic Protocol Specification

<!-- current-links-9000 -->
## 2026-10-22 · 9000 · 20% · DGW/10

Valid blocks through 8999 remain usable, including those sent together with an invalid later suffix. From 9000, every block needs a producer commitment. DGW uses 24 preceding blocks and recalculates at 9000, 9010, 9020…; intervening blocks keep the parent difficulty. The target interval remains 600 seconds. Connection events are random with probability 20%. Three discovered identities sign after PoW; mining and block acceptance do not wait for signatures. Cumulative work takes priority; valid, nonconflicting connections break work ties, followed by the smaller tip hash. Late evidence can change a tie. See the exact implementation and limitations below.

[Current protocol / exact format / limitations](CONNECTION_PROOFS_9000.html)
<!-- /current-links-9000 -->


## 1. Basic principles

- No administrator authority for arbitrary issuance, freezing, confiscation or balance modification.
- Rule-compliant rewards start with the first ordinary block, with no reserved developer allocation in the issuance rules.
- Every node independently validates received transactions and blocks.
- Amounts use integer smallest units; fees transfer existing value.
- Select the branch with the greatest valid cumulative work.
- Preserve history and validate it on restart to restore the same UTXOs.

## 2. Issuance rules

First 150,000 blocks: 50 SMW. Then 25 SMW, halved every 210,000 blocks using integer smallest units.

| Block height | Block subsidy |
|---|---:|
| 0–149,999 | 50 SMW |
| 150,000–359,999 | 25 SMW |
| 360,000–569,999 | 12.5 SMW |
| 570,000–779,999 | 6.25 SMW |
| 780,000–989,999 | 3.125 SMW |
| 6,660,000–6,869,999 | 0.00000001 SMW |
| H ≥ 6,870,000 | 0 SMW |

```text
0 <= H < 150000: S(H) = 5000000000
H >= 150000:
    k = floor((H - 150000) / 210000)
    if k >= 32: S(H) = 0
    otherwise: S(H) = floor(2500000000 / 2^k)
```

Nominal maximum issuance: **17,999,999.97690000 SMW**.
Maximum excluding the unspendable genesis reward: **17,999,949.97690000 SMW**.

## 3. Genesis and network identity

SUMUWW's basic execution network is `sumuww`, profile `dora-independent-v0.12-p2wpkh`. Genesis is fixed to hash `00000032e243a8c71b449b13c2da733dd329f308a75aa4358f3f22707a28af97`, UTC 2026-10-03 00:00:00 and nonce `5129435`. It has only an OP_RETURN output and is not connected to the UTXO set. Initial nBits is `0x1e0377ae`, powLimit is `floor((2^256-1)/4838400)`, address HRP is `sumuww`, and wire magic is `d052470c`. Before height 8,064, the Chain uses 600 seconds, 2,016 blocks, 1,209,600 seconds and a 4-times clamp. The [complete genesis record](vectors/sumuww_genesis.json) is included.

Genesis is the fixed height-0 anchor with a previous hash of 0. Full bytes, Merkle root, header hash and PoW are recalculated. Its transaction is not connected to UTXOs. Ordinary coinbase outputs require spending height minus creation height to be at least 100.

## 4. Blocks, transactions and UTXOs

A block header contains 80 bytes in this order: signed int32 version, previous hash 32 bytes, Merkle root 32 bytes, uint32 timestamp, uint32 nBits and uint32 nonce. Integers are little-endian, and the header ID is SHA-256d. Display hashes are reversed hexadecimal representations of internal raw bytes.

Transactions contain uint32 version, inputs, outputs and uint32 locktime using canonical CompactSize. Inputs record previous txid/index, scriptSig and sequence; outputs record signed int64 smallest-unit amounts and scriptPubKey. Witness serialization uses marker 0, flag 1 and a stack per input. TXID is SHA-256d of non-witness serialization; WTXID is SHA-256d of serialization including witness.

Validation rejects empty inputs/outputs, duplicate inputs, missing or spent UTXOs, invalid signatures, immature coinbase, negative or excessive amounts and output totals greater than inputs. Fees equal input totals minus output totals. Live outputs cannot be overwritten by the same txid/index.

Only the first transaction may be coinbase. Coinbase null outpoint, scriptSig length 2~100 bytes and height prefix are checked. Output total cannot exceed the height's subsidy plus block fees. Merkle mutation and witness commitment are checked. Block weight is `3*base_size + total_size <= 4000000`; sigops cost must not exceed 80,000.

Before block 9100, spending validation supports **native P2WPKH / SIGHASH_ALL** using secp256k1 ECDSA. From block 9100, upgraded nodes additionally validate the exact HTLC template described in [HTLC_9100.md](HTLC_9100.md). Other spending scripts or signature flags remain unsupported; a general script VM is not implemented. Activation is evaluated at the block spending an output, not the block that created its coins.

## 5. Proof of work, difficulty and time

The SHA-256d digest interpreted as a little-endian integer must be at most the target. Negative, 0, 256-bit-overflow and above-powLimit compact targets are rejected. Raw candidate nBits must exactly match the value expected from its parent and height.

**H < 8,064:** Public operation targets 600 seconds, retargeting every 2,016 blocks over 1,209,600 seconds. At retarget height h, timestamps h-1 and h-2,016 **on the same branch** are used. The first boundary at height 2,016 references heights 2,015 and 0.

```text
# H < 8064
bounded = clamp(time[h-1] - time[h-2016], 302400, 4838400)
new_target = min(floor(old_target * bounded / 1209600), powLimit)
expected_bits = compact_encode(new_target)
```

**H < 8,064:** Only public-style profiles satisfying `powLimit * 4838400 <= 2^256-1` are accepted, matching the comparison implementation's 256-bit intermediate arithmetic. Other heights retain parent nBits; delayed blocks have no arbitrary minimum-difficulty exception.

```text
H >= 9000 and (H - 9000) % 10 != 0:
    expected_bits = parent.bits
otherwise, H >= 8064:
    T[0..23] = targets of 24 preceding blocks, newest first
    time[0..23] = timestamps of those same blocks
    A = T[0]
    for n = 2..24:
        A = floor((A * n + T[n-1]) / (n + 1))
    elapsed = clamp(time[0] - time[23], 4800, 43200)
    expected_bits = compact_encode(max(1, min(floor(A * elapsed / 14400), powLimit)))
```

A new block timestamp must exceed the median of up to 11 ancestors starting from its parent. Blocks more than 7,200 seconds ahead of the node clock are temporarily inadmissible, not permanently marked invalid. Absolute transaction locktime and relative sequence conditions are checked. CLTV is supported only in the exact HTLC template from 9100; general scripts and CSV opcodes remain unsupported.

## 6. Chain selection, storage and transaction relay

Block work for valid target T is `floor(2^256/(T+1))`. Valid blocks through 8999 remain usable, including those sent together with an invalid later suffix. From 9000, every block needs a producer commitment. DGW uses 24 preceding blocks and recalculates at 9000, 9010, 9020…; intervening blocks keep the parent difficulty. The target interval remains 600 seconds. Connection events are random with probability 20%. Three discovered identities sign after PoW; mining and block acceptance do not wait for signatures. Cumulative work takes priority; valid, nonconflicting connections break work ties, followed by the smaller tip hash. Late evidence can change a tie. See the exact implementation and limitations below.

Nodes exchange version/verack, locator/headers, inventory/getdata and block/transaction messages over TCP. Each uses a separate DB and independently validates received data.

[NETWORK_PROTOCOL](docs/i18n/en/NETWORK_PROTOCOL.md)

## 7. Address encoding

SUMUWW addresses use Bech32 with HRP `sumuww`, witness version 0 and a 20-byte witness program for native P2WPKH. Validation checks the network prefix, checksum and padding. Other-network addresses, mixed case and invalid padding are rejected.


## Implementation addendum: PC 0.57.46 / Android 0.6.95

[Current fee, yugeon, replacement and script activation specification](NODE_FEATURES.md).
