# SUMUWW Coin Information and Registration

## Scope

This document covers the coin, its public technical information and independent third-party information registration or trading support. Participation requires no creator's technical permission.

## Coin information

SUMUWW is an independent proof-of-work coin with its own genesis and transaction history. Nodes independently validate transactions and blocks and select the chain with the greatest valid cumulative work. Issuance and difficulty follow shared consensus rules. Included transaction fees may be claimed by the block miner.

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

## Public technical material

- Whitepaper: purpose, consensus principles and security limits.
- Protocol specification: issuance arithmetic, identifiers, encoding and validation conditions.
- Public implementation: source for verifying consensus and data validation, subject to LICENSE and dependency notices.
- Consensus verification: evidence for issuance arithmetic, block validation and chain selection, with the tested scope and limitations stated explicitly.

## Information registration and trading support

Information-site registration and exchange support are separate from consensus. A creator need not apply for a listing before a third party can use SUMUWW. Exchanges decide whether to support it under their own review and applicable requirements, without special consensus privileges.

Technical information includes the coin name and unit, genesis and network identifiers, issuance, consensus, address and transaction formats, fees, maturity and public specification and source. An exchange operates its own validating node, deposit and withdrawal integration and confirmation policy. SUMUWW does not manage an exchange's internal customer balances.

Only verified registration, listing, fees or support status may be represented as completed. Open source does not automatically confer listing approval.

## Factual limits

Do not guarantee price, liquidity, listings, income, mining time, irreversible finality or immunity to attacks. The 600-second target is not a fixed duration for every block. A greater-work valid branch may change transaction history. Consensus architecture and actual independent participation or hashrate are distinct facts.

P2P peers can observe connection IP addresses. The protocol does not guarantee anonymity. Do not publish private endpoints or unverified operator identities.
