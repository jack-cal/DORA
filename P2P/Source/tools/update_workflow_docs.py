"""Update the local release guide and directly translated feature summaries."""
import html,json
from pathlib import Path
from peer_translations import NOTES

ROOT=Path(__file__).resolve().parents[1]

def put(path,text):path.write_text(text,encoding='utf8',newline='\n')

def replace(path,old,new):
    text=path.read_text(encoding='utf8')
    if new in text:return
    if old not in text:raise ValueError(str(path)+': missing expected text')
    put(path,text.replace(old,new))

for path in (ROOT/'smw_trade/market/__init__.py',ROOT/'smw_trade/market/light_network.py'):
    put(path,path.read_text(encoding='utf8').replace('0.3.5','0.3.6'))

path=ROOT/'README.txt';text=path.read_text(encoding='utf8').replace('0.3.5','0.3.6')
start=text.index('DIRECT PEERS\n') if 'DIRECT PEERS\n' in text else text.index('AUTOMATIC TRADING CONNECTIONS\n');end=text.index('\nCHAIN CONNECTIONS',start)
text=text[:start]+'''AUTOMATIC TRADING CONNECTIONS
The application discovers trading peers on the LAN and through a separate
public DHT contact namespace, reconnects to remembered peers and synchronizes
signed orders. Trading uses bidirectional TLS 1.3 connections and authenticated
identity routes; users do not enter a counterparty IP. Both trading programs
must be updated to 0.3.6. Old plaintext market connections are not accepted.
Discovery needs reachable updated participants. It does not change router or
firewall settings or guarantee connectivity through every NAT. When no peer
has acknowledged a post, it remains visibly marked Waiting for peers.
This is not a hosted orderbook, and transport encryption does not hide your
network address from the directly connected peer. See NETWORK_SECURITY.md.
''' + text[end:]
text=text.replace('Light does not require local Bitcoin Core. Setup and ads can be used before\nactivation; they do not move coins.', 'Light does not require local Bitcoin Core. Wallet setup is available before\nactivation; publishing now requires confirmed funds on an active paying chain.')
text=text.replace('1. Publish a buy/sell post with SMW quantity, BTC unit price and details.\n2. The other party reserves the whole order; reservation moves no coins.\n3. Both prepare and exchange details. The signed agreement binds amounts,',
'''1. Create or unlock Trading wallet. Deposit SMW to sell or BTC to buy, plus
   network fees, to the displayed address. Wait for confirmations. Refresh
   balance shows confirmed and available funds; posting always rechecks them.
2. Enter SMW quantity and BTC price, then Publish. Titles and descriptions are
   removed. Confirmed inputs are allocated per order to prevent reuse by other
   local orders. This allocation does not lock coins on the blockchain.
3. Click Trade beside the chosen order and confirm its full amount. Both
   wallets and chains must be ready. Funds are checked again, and the program
   reserves the order, prepares the agreement and opens My trades. Own active
   rows offer Cancel my order; reserved local trades offer Open trade.
   The signed agreement binds amounts,''')
text=text.replace('A peer cannot unlock, sign or broadcast.', 'A peer cannot unlock the wallet or sign or broadcast a coin transaction.')
text=text.replace('Unknown broadcast results remain pending, never completed. Automatic fee\nreplacement is not implemented. An insufficient fixed UTXO fee requires\ninspection of the saved transaction.', 'Unknown broadcast results remain pending, never completed. Fee increases use\na separately reviewed child transaction. Saved transactions are retained for\ninspection and recovery.')
if '\nWALLET SCOPE\n' not in text:text+='\nWALLET SCOPE\nThe trading wallet receives native SMW and BTC and handles swap locks, claims\nand refunds. A general send-to-any-address screen is not included in this\nrelease. Wallet-only backups use this application’s format.\n'
put(path,text)

path=ROOT/'EDITIONS.md';text=path.read_text(encoding='utf8').replace('0.3.4','0.3.6')
old='''The board uses direct reachable peer addresses. It has no hosted order book,
automatic Internet discovery or NAT traversal. Orders fill as a whole and are
not proof of available funds.'''
new='''The board discovers peers automatically and uses bidirectional TLS 1.3 and
identity routes. Users do not enter counterparty IPs. It has no hosted order
book or universal NAT traversal. Reachable updated participants are required.
Posting checks confirmed paying funds and fees, and allocates inputs locally;
both parties are rechecked before reservation. A received advertisement alone
is not an independently verified proof of funds. Orders fill as a whole.'''
assert old in text or new in text;text=text.replace(old,new);put(path,text)

path=ROOT/'BITCOIN_SETUP.md';text=path.read_text(encoding='utf8')
text=text.replace('After activation and successful chain checks, publish a buy/sell post with the\nSMW amount and BTC unit price. The other participant reserves the whole order.',
'''After activation and successful chain checks, deposit SMW to sell or BTC to
buy into Trading wallet, including network fees, and wait for confirmations.
Publish with the SMW amount and BTC unit price. Click Trade beside an order
to reserve its full quantity and automatically prepare/exchange the agreement.''')
text=text.replace('The order board uses directly reachable peer addresses. It has no hosted public\nmarketplace or automatic NAT traversal.',
'''The order board discovers peers automatically and routes signed trade messages
over bidirectional TLS 1.3 sessions. It has no hosted public marketplace or
universal NAT traversal. Internet discovery requires reachable updated peers.''')
put(path,text)

put(ROOT/'CURRENT_GUIDE.md','''# SUMUWW P2P Full / Light 0.3.6

Deposit SMW to sell or BTC to buy, including fees, into Trading wallet and wait
for confirmations. Publish checks available funds and reserves local inputs
per order. Trade beside an order rechecks funds and opens the prepared exchange.
Titles and free-text descriptions are removed. Every coin spend still requires
local review. This allocation is not on-chain escrow.

Peer discovery, reconnection and order synchronization are automatic. TLS 1.3
and authenticated bidirectional routes replace manual counterparty IP entry.
Both P2P programs must be updated. Internet operation requires reachable peers;
the application does not bypass every router or firewall.

Full requires synchronized local Bitcoin Core with txindex; Light verifies
headers and inclusion proofs and relies on servers for complete history. Both
require the current synchronized SUMUWW node. English remains the initial
language, with saved choices and all 34 languages retained.

Read [setup](BITCOIN_SETUP.md), [security and connection scope](NETWORK_SECURITY.md),
[edition differences](EDITIONS.md) and [verification](VERIFICATION.txt).
See [translated feature notes](docs/features/index.html). This local version
has not been published to GitHub.
''')

put(ROOT/'NETWORK_SECURITY.md','''# P2P 0.3.6 network and funding behavior

## Connections

The mainnet application opens a dual-stack listener on an OS-assigned port.
Signed multicast announcements use group 239.255.83.77:18487, a short timestamp
window and the packet's actual RFC1918 source, never a payload-supplied IP.
Public BEP5 DHT lookup uses a separate SUMUWW market TLS3 namespace. Generic
DHT routers only supply contact hints and are not trading or payment services.
Public hints cannot target loopback, LAN, link-local, reserved or multicast
addresses. Runtime global interfaces can be announced; this does not prove
external reachability. No firewall rules, router mappings or UPnP settings are
changed. Offline, mutually blocked or isolated participants cannot trade until
a reachable route exists. No hosted bootstrap/trade relay is bundled.

TLS 1.3 authenticates an Ed25519 certificate key against the board identity.
The client signs a fresh server challenge; the server signs the client nonce.
Remembered endpoints pin their identity keys and reject changes. Discovery is
self-authenticated, not a claim about the human owner or trustworthy funds.
Sessions carry requests in both directions, including through an existing
shared peer. Routed trade payloads retain their origin signatures; routes have
a four-hop limit and never instruct a peer to dial an arbitrary supplied URL.
Direct peers can see each other's IP; relays can read routed trade metadata.
No coin private keys or secret preimages are sent in these messages.

Limits include 24 live peers, 8 concurrent handshakes, 32 concurrent queued or
running requests, 16 pending requests per session, 128 KiB frames, per-session
and aggregate rate limits, timeouts, bounded discovery hints and forwarding
queues. Malformed/unsigned packets never authorize a coin transaction. Plaintext
market protocol v2 is disabled; update both participants. The separate legacy
regtest laboratory remains a test-only tool and is not the mainnet transport.

## Funding and recovery

Posting requires an unlocked wallet and current confirmed outputs owned by its
paying key. The amount, claim/refund fee reserve, current funding fee and change
minimum must fit. Unconfirmed, immature, spent, previously allocated and pending
trade inputs are excluded. Local per-order allocations survive restart and
complete recovery backups; cancellation releases an unfunded allocation.
They are not blockchain escrow and cannot prevent a separate copy of a key from
spending. Maker and taker are checked again before reservation. Actual funding
is signed locally after review and checked by the configured node before broadcast.
Advertised amounts alone are not remotely proven balances.

Trade selects a full order, prepares the signed agreement and opens My trades.
The SMW seller locks first. After confirmations the buyer locks BTC; the seller
claims BTC and the buyer claims SMW. Uncertain results remain pending. Deadlines,
six-confirmation mainnet checks, explicit claims/refunds and write-ahead recovery
remain enforced. Network messages can exchange ownership proofs and signed
agreements, but cannot approve or broadcast a coin spend.
''')

put(ROOT/'RELEASE_NOTES.txt','''SUMUWW P2P Full / Light 0.3.6 — local build, 26 October 2026

- Require confirmed paying funds and fees before posting; allocate inputs per
  order and recheck both sides at reservation. Preserve allocations in recovery.
- Remove title/detail fields. Add Trade/Open trade/Cancel buttons beside rows.
  Trade opens the prepared exchange; unsigned/unfunded posts are not accepted
  by the application posting path. Each coin spend requires local review.
- Add automatic LAN/public-DHT discovery and reconnection, bidirectional TLS 1.3,
  identity routing, identity-key pinning and bounded network resource use.
  Remove manual counterparty IP controls. Both P2P applications need this update.
- Keep existing wallets, agreements, signed transactions and valid chain data.
  Retain English on first launch, saved language choices and all 34 languages.
- General wallet withdrawals are not included. Internet connectivity depends
  on reachable updated peers; no universal NAT traversal is claimed.

See VERIFICATION.txt for the actual test scope. GitHub publication is separate.
''')
put(ROOT/'SOURCE_REVISION.md','''# Local P2P source — 26 October 2026

Full and Light 0.3.6. Unpublished local changes based on the repository commit
recorded in the source archive. SOURCE_FILES.json records every archived file.
Wallets, personal chain databases and private connection logs are excluded.
''')

messages=json.loads((ROOT/'smw_trade/market/translations.json').read_text(encoding='utf8'))
for code,note in NOTES.items():
    folder=ROOT/'docs/features'/code
    md=(folder/'FEATURES.md').read_text(encoding='utf8').replace('0.3.5','0.3.6')
    if note not in md:md=md.rstrip()+'\n\n'+note+'\n'
    put(folder/'FEATURES.md',md)
    title=md.splitlines()[0].lstrip('# ')
    paragraphs=''.join('<p>'+html.escape(p)+'</p>' for p in md.split('\n\n')[1:])
    link=messages[code].get('Update before block 9,600.','Update before block 9,600.')
    direction=' dir="rtl"' if code in ('ar','ur') else ''
    put(folder/'FEATURES.html',f'<!doctype html><html lang="{code}"{direction}><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>{html.escape(title)}</title><style>body{{max-width:900px;margin:32px auto;padding:20px;font:18px/1.7 system-ui;background:#101820;color:#edf4f5}}a{{color:#72dac4}}</style><h1>{html.escape(title)}</h1>{paragraphs}<p><a href="../../upgrade9600/{code}.html">{html.escape(link)}</a></p></html>\n')
put(ROOT/'docs/WORKFLOW_TRANSLATIONS.md','''# 0.3.6 translation scope

All 34 UI languages include the 10 funded-order messages and 3 automatic-peer
messages, authored directly in tools/workflow_translations.py and
tools/peer_translations.py. Existing messages and saved language choices remain.
Each docs/features/<language>/FEATURES.md and FEATURES.html includes the same
funding, row-button, automatic connection and reachability summary. Links are
local to this edition. NETWORK_SECURITY.md is the detailed English reference.
No external automatic translation service was used.
''')
index=ROOT/'docs/features/index.html'
put(index,index.read_text(encoding='utf8').replace('0.3.5','0.3.6'))

path=ROOT.parent/'README.md';text=path.read_text(encoding='utf8')
text=text.replace('Setup and ads can be used earlier, but they move no funds.','Wallet setup can be used earlier. Local 0.3.6 posting requires an active paying chain and confirmed funds.')
text=text.replace('The board requires directly reachable counterparty addresses. There is no hosted\npublic orderbook, automatic NAT traversal, automatic fee bumping or unattended\nrefund service.', 'The local 0.3.6 board discovers peers automatically and uses TLS identity routes.\nThere is no hosted public orderbook, universal NAT traversal, automatic fee\nbumping or unattended refund service.')
if 'Local source: **0.3.6' not in text:text=text.replace('# SUMUWW P2P — SMW/BTC trading\n','# SUMUWW P2P — SMW/BTC trading\n\nLocal source: **0.3.6, not yet published**. Download links below still refer to\nthe published 0.3.5 packages. See [local changes](Source/CURRENT_GUIDE.md).\n',1)
put(path,text)
print('Updated local 0.3.6 guides and 34 directly translated feature summaries.')
