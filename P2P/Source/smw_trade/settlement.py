"""End-to-end funded swap/refund runner on isolated real chain engines.

All test wallets/coins are disposable. Public funding/broadcast is unavailable.
Durable refund plans contain signed transactions, not private keys.
"""
from dataclasses import replace
from pathlib import Path
import hashlib, json, secrets, time
from sumuww.wallet import RegtestKey, sign_p2wpkh
from sumuww.transaction import Transaction, TxInput, TxOutput
from sumuww.address import _bech32_encode, _convert_bits
from sumuww.chain import Chain
from .research_chain import SwapChain
from .htlc import Contract, sign_spend
from .bitcoin import Bitcoin
from .orders import Store, amount, MAX_ATOMS
from decimal import Decimal

def key():
    return RegtestKey.from_int(secrets.randbelow(2 ** 250) + 1)

def display(tx):
    return tx.txid()[::-1].hex()

def height(chain):
    return chain._row(chain.tip_hash)[2]

def address(script, coin='btc'):
    return _bech32_encode('drt' if coin == 'smw' else 'bcrt', [0] + _convert_bits(script[2:], 8, 5, pad=True))

def smw_fund(chain, owner, contract, value):
    candidates = [(point, coin) for point, coin in chain.list_utxos(owner.script_pubkey) if not coin.coinbase or height(chain) + 1 - coin.height >= 100]
    selected = []
    total = 0
    for point, coin in candidates:
        selected.append((point, coin))
        total += coin.output.value
        if total >= value + 1000:
            break
    if total < value + 1000:
        raise ValueError('The disposable test wallet has insufficient mature balance for the order and fees.')
    outputs = [TxOutput(value, contract.script_pubkey)]
    if total > value + 1000:
        outputs.append(TxOutput(total - value - 1000, owner.script_pubkey))
    tx = Transaction(2, tuple((TxInput(*point) for point, coin in selected)), tuple(outputs), 0)
    for i, (point, coin) in enumerate(selected):
        tx = sign_p2wpkh(tx, i, coin.output, owner)
    chain.submit_transaction(tx)
    chain.mine(owner.script_pubkey)
    return tx

def spend(funding, contract, receiver, *, refund=False):
    output = next(((i, o) for i, o in enumerate(funding.outputs) if o.script_pubkey == contract.script_pubkey))
    index, previous = output
    tx = Transaction(2, (TxInput(funding.txid(), index, sequence=4294967294),), (TxOutput(previous.value - 1000, receiver.script_pubkey),), contract.refund_height if refund else 0)
    return (tx, previous)

def btc_coins(btc, owner):
    scan = btc.rpc('scantxoutset', 'start', ['addr(' + address(owner.script_pubkey) + ')'])
    if not scan['success']:
        raise ValueError('Bitcoin test-key UTXO scan did not finish')
    coins = []
    for item in scan['unspents']:
        output = btc.rpc('gettxout', item['txid'], item['vout'], True)
        if output and (not output['coinbase'] or output['confirmations'] >= 100):
            value = int(Decimal(str(output['value'])) * 100000000)
            coins.append((bytes.fromhex(item['txid'])[::-1], item['vout'], TxOutput(value, owner.script_pubkey)))
    return coins

def btc_fund(btc, contract, value, owner=None):
    if owner is None:
        txid = btc.rpc('sendtoaddress', address(contract.script_pubkey), amount(value))
    else:
        selected = []
        total = 0
        for coin in btc_coins(btc, owner):
            selected.append(coin)
            total += coin[2].value
            if total >= value + 1000:
                break
        if total < value + 1000:
            raise ValueError('Insufficient mature balance in the Bitcoin test wallet.')
        outputs = [TxOutput(value, contract.script_pubkey)]
        if total > value + 1000:
            outputs.append(TxOutput(total - value - 1000, owner.script_pubkey))
        tx = Transaction(2, tuple((TxInput(h, i) for h, i, o in selected)), tuple(outputs), 0)
        for index, (_, _, output) in enumerate(selected):
            tx = sign_p2wpkh(tx, index, output, owner)
        txid = btc.rpc('sendrawtransaction', tx.serialize().hex())
    tx = Transaction.deserialize(bytes.fromhex(btc.rpc('getrawtransaction', txid)))
    if display(tx) != txid:
        raise ValueError('Bitcoin transaction ID mismatch')
    btc.mine()
    return tx

def confirm_lock(chain, funding, contract, value):
    matches = [(p, c) for p, c in chain.list_utxos(contract.script_pubkey) if p[0] == funding.txid() and c.output.value == value]
    if len(matches) != 1:
        raise ValueError('SMW lock missing, wrong amount or already spent')
    return matches[0]

def confirm_btc_lock(btc, funding, contract, value):
    matches = [(i, o) for i, o in enumerate(funding.outputs) if o.script_pubkey == contract.script_pubkey and o.value == value]
    if len(matches) != 1:
        raise ValueError('Bitcoin funding conditions mismatch')
    i, _ = matches[0]
    output = btc.rpc('gettxout', display(funding), i, True)
    if not output or output['confirmations'] < 1 or output['scriptPubKey']['hex'] != contract.script_pubkey.hex():
        raise ValueError('Bitcoin output unconfirmed, spent or wrong script')
    if round(output['value'] * 100000000) != value:
        raise ValueError('Bitcoin amount mismatch')
    return output

def run_round(directory, bitcoin_executable, *, mode='success', progress=None, cancel=None, smw_atoms=100000000, btc_sats=200000, binding=None, detail=None, wallet_material=None):
    if mode not in ('success', 'refund'):
        raise ValueError('Unknown isolated scenario')
    if type(smw_atoms) is not int or not 0 < smw_atoms <= MAX_ATOMS or type(btc_sats) is not int or (not 0 < btc_sats <= MAX_ATOMS):
        raise ValueError('Invalid exact trade amount')
    if btc_sats < 294:
        raise ValueError('The receive amount must be at least 294 sat under the Bitcoin test-node dust policy.')
    binding = dict(binding or {})
    if binding and (binding.get('smw_atoms') != smw_atoms or binding.get('btc_sats') != btc_sats or binding.get('network') != 'regtest-only'):
        raise ValueError('Amounts do not match the signed reservation')
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    store = Store(directory / 'journal')
    session = secrets.token_hex(32)
    evidence = {**binding, 'network': 'regtest-only', 'mode': mode, 'real_bitcoin_core': True, 'public_funds': False, 'local_simulated_counterparty': True, 'smw_atoms': smw_atoms, 'btc_sats': btc_sats, 'fees': {'smw_funding_atoms': 1000, 'smw_claim_atoms': 1000, 'btc_claim_sats': 1000, 'bitcoin_funding_fee': 'Bitcoin Core wallet fee, additional'}, 'events': []}
    started = time.monotonic()

    def record(state, **values):
        if cancel is not None and cancel.is_set():
            raise RuntimeError('The test was interrupted by a shutdown request.')
        evidence.update(values)
        evidence['events'].append({'state': state, 'elapsed_seconds': round(time.monotonic() - started, 4)})
        store.checkpoint(session, state, evidence)
        if detail:
            detail(state, json.loads(json.dumps(evidence)))
        if progress:
            progress(state)
    alice_smw, bob_smw, alice_btc, bob_btc = (key(), key(), key(), key())
    if wallet_material is not None:
        keys = wallet_material['keys']
        public = wallet_material['public']
        if not binding or public.get('network') != 'regtest-only' or public.get('locked') or (set(keys) != {'smw', 'btc'}) or (not all((isinstance(k, RegtestKey) for k in keys.values()))):
            raise ValueError('Invalid local regtest signing material')
        taker_sells = binding['order_side'] == 'buy'
        if taker_sells:
            alice_smw, alice_btc = (keys['smw'], keys['btc'])
        else:
            bob_smw, bob_btc = (keys['smw'], keys['btc'])
        evidence.update(wallet_source='encrypted-local-test-vault', local_wallet_id=public['wallet_id'], local_wallet_smw_address=public['addresses']['smw'], local_wallet_btc_address=public['addresses']['btc'], local_wallet_direction='sell' if taker_sells else 'buy')
        evidence['fees']['bitcoin_funding_fee'] = 1000
    else:
        evidence['wallet_source'] = 'disposable'
    secret = secrets.token_bytes(32)
    secret_hash = hashlib.sha256(secret).digest()
    chain = SwapChain(directory / 'smw.sqlite')
    try:
        chain.mine(alice_smw.script_pubkey, 103)
        available = sum((c.output.value for p, c in chain.list_utxos(alice_smw.script_pubkey) if not c.coinbase or height(chain) + 1 - c.height >= 100))
        if available < smw_atoms + 2000:
            raise ValueError('The disposable test wallet has insufficient mature balance for the order and fees.')
        with Bitcoin(bitcoin_executable, directory / 'bitcoin', cancel=cancel) as btc:
            if wallet_material is not None:
                btc.rpc('generatetoaddress', 103, address(bob_btc.script_pubkey))
                if sum((o.value for h, i, o in btc_coins(btc, bob_btc))) < btc_sats + 2000:
                    raise ValueError('Insufficient mature balance in the Bitcoin test wallet.')
            else:
                btc.mine(101)
            smw_contract = Contract(secret_hash, bob_smw.pubkey, alice_smw.pubkey, height(chain) + 40)
            btc_contract = Contract(secret_hash, alice_btc.pubkey, bob_btc.pubkey, btc.rpc('getblockcount') + 15)
            record('AGREED', smw_atoms=smw_atoms, btc_sats=btc_sats, smw_recipient=address(bob_smw.script_pubkey, 'smw'), btc_recipient=address(alice_btc.script_pubkey), smw_seller=address(alice_smw.script_pubkey, 'smw'), btc_buyer=address(bob_btc.script_pubkey), smw_lock_address=address(smw_contract.script_pubkey, 'smw'), btc_lock_address=address(btc_contract.script_pubkey), secret_hash=secret_hash.hex(), smw_script=smw_contract.script.hex(), btc_script=btc_contract.script.hex(), smw_refund_height=smw_contract.refund_height, btc_refund_height=btc_contract.refund_height)
            smw_funding = smw_fund(chain, alice_smw, smw_contract, smw_atoms + 1000)
            confirm_lock(chain, smw_funding, smw_contract, smw_atoms + 1000)
            smw_refund, smw_prev = spend(smw_funding, smw_contract, alice_smw, refund=True)
            smw_refund = sign_spend(smw_refund, 0, smw_prev, smw_contract, alice_smw)
            record('SMW_LOCK_CONFIRMED', smw_funding=display(smw_funding), smw_refund_raw=smw_refund.serialize().hex())
            try:
                with Chain(directory / 'smw.sqlite', network='regtest') as old:
                    claim, previous = spend(smw_funding, smw_contract, bob_smw)
                    old.submit_transaction(sign_spend(claim, 0, previous, smw_contract, bob_smw, secret=secret))
            except Exception as exc:
                from sumuww.errors import UnsupportedFeature
                if not isinstance(exc, UnsupportedFeature):
                    raise
                evidence['unmodified_core_rejects_htlc'] = True
            else:
                raise AssertionError('Unmodified core unexpectedly accepts new HTLC')
            btc_funding = btc_fund(btc, btc_contract, btc_sats + 1000, bob_btc if wallet_material is not None else None)
            confirm_btc_lock(btc, btc_funding, btc_contract, btc_sats + 1000)
            refund, previous = spend(btc_funding, btc_contract, bob_btc, refund=True)
            refund = sign_spend(refund, 0, previous, btc_contract, bob_btc)
            record('BOTH_LOCKS_CONFIRMED', btc_funding=display(btc_funding), btc_refund_raw=refund.serialize().hex())
            early = btc.rpc('testmempoolaccept', [refund.serialize().hex()])[0]
            if early['allowed']:
                raise AssertionError('Early BTC refund was accepted')
            try:
                chain.submit_transaction(smw_refund)
            except Exception as exc:
                from sumuww.errors import InvalidTransaction
                if not isinstance(exc, InvalidTransaction):
                    raise
            else:
                raise AssertionError('Early SMW refund was accepted')
            evidence['early_refunds_rejected'] = True
            if mode == 'success':
                claim, previous = spend(btc_funding, btc_contract, alice_btc)
                btc_claim = sign_spend(claim, 0, previous, btc_contract, alice_btc, secret=secret)
                wrong = list(btc_claim.inputs[0].witness)
                wrong[1] = secrets.token_bytes(32)
                bad = replace(btc_claim, inputs=(replace(btc_claim.inputs[0], witness=tuple(wrong)),))
                if btc.rpc('testmempoolaccept', [bad.serialize().hex()])[0]['allowed']:
                    raise AssertionError('Wrong BTC preimage accepted')
                evidence['bitcoin_wrong_secret_rejected'] = True
                txid = btc.rpc('sendrawtransaction', btc_claim.serialize().hex())
                btc.mine()
                observed = Transaction.deserialize(bytes.fromhex(btc.rpc('getrawtransaction', txid)))
                revealed = observed.inputs[0].witness[1]
                if hashlib.sha256(revealed).digest() != secret_hash:
                    raise AssertionError('Observed preimage mismatch')
                record('BTC_CLAIM_CONFIRMED', btc_claim=txid)
                claim, previous = spend(smw_funding, smw_contract, bob_smw)
                claim = sign_spend(claim, 0, previous, smw_contract, bob_smw, secret=revealed)
                chain.submit_transaction(claim)
                chain.mine(alice_smw.script_pubkey)
                if chain.balance(bob_smw.script_pubkey) != smw_atoms:
                    raise AssertionError('SMW recipient not paid')
                received = btc.rpc('gettxout', txid, 0, True)
                if not received or received['confirmations'] < 1 or round(received['value'] * 100000000) != btc_sats or (received['scriptPubKey']['hex'] != alice_btc.script_pubkey.hex()):
                    raise AssertionError('BTC recipient not paid exact agreed amount')
                record('COMPLETED', smw_claim=display(claim), smw_received_atoms=smw_atoms, btc_received_sats=btc_sats)
            else:
                record('REFUND_WAIT')
                chain.close()
                chain = SwapChain(directory / 'smw.sqlite')
                btc.restart()
                restored = Store(directory / 'journal').history()[0]
                smw_refund = Transaction.deserialize(bytes.fromhex(restored['evidence']['smw_refund_raw']))
                refund_raw = restored['evidence']['btc_refund_raw']
                evidence['smw_chain_and_journal_reopened'] = True
                evidence['bitcoin_node_restarted'] = True
                btc.mine(btc_contract.refund_height - btc.rpc('getblockcount'))
                txid = btc.rpc('sendrawtransaction', refund_raw)
                btc.mine()
                chain.mine(alice_smw.script_pubkey, smw_contract.refund_height - height(chain))
                chain.submit_transaction(smw_refund)
                chain.mine(alice_smw.script_pubkey)
                if btc.rpc('gettxout', txid, 0, True)['confirmations'] < 1:
                    raise AssertionError('BTC refund not confirmed')
                if not any((p[0] == smw_refund.txid() for p, c in chain.list_utxos(alice_smw.script_pubkey))):
                    raise AssertionError('SMW refund not confirmed')
                record('REFUNDED', btc_refund=txid, smw_refund=display(smw_refund), smw_refunded_atoms=smw_atoms, btc_refunded_sats=btc_sats)
            evidence['passed'] = True
            evidence['bitcoin_version'] = btc.rpc('getnetworkinfo')['subversion']
            store.checkpoint(session, 'COMPLETED' if mode == 'success' else 'REFUNDED', evidence)
    finally:
        chain.close()
    evidence['elapsed_seconds'] = round(time.monotonic() - started, 3)
    (directory / 'result.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    return evidence
