"""Reproducible local test: mining, signed payment, restart and chain reorg."""

import argparse
from dataclasses import replace
import json
from pathlib import Path

from . import __version__

from .__main__ import create_test_payment, test_key
from .chain import Chain
from .errors import InvalidTransaction
from .primitives import format_amount, hash_to_display
from .wallet_paths import reject_wallet_overwrite

FIXTURE_TIME = 1_700_000_100


def run(directory):
    directory = Path(directory)
    if directory.exists() and any(directory.iterdir()):
        raise ValueError('Demo needs a new or empty directory; existing files are preserved')
    directory.mkdir(parents=True, exist_ok=True)
    database = directory / 'sumuww.sqlite'
    alice, bob, miner = [test_key(i) for i in (1, 2, 3)]
    clock = lambda: FIXTURE_TIME
    with Chain(database, clock=clock) as chain:
        initial = chain.info()
        chain.mine(alice.script_pubkey, 99)
        immature = chain.balance(alice.script_pubkey, mature_only=True)
        assert immature == 0
        chain.mine(alice.script_pubkey)
        mature = chain.balance(alice.script_pubkey, mature_only=True)
        assert mature == 5_000_000_000
        fork_point = chain.tip_hash
        tx = create_test_payment(chain, 1, bob.pubkey, 300_000_000, 100_000)
        chain.submit_transaction(tx)
        # Altered outputs retain a conflicting outpoint; resign to test spending,
        # not just a bad-signature path.
        from .wallet import sign_p2wpkh
        conflicting = replace(tx, outputs=tuple(replace(o, value=o.value - 1) if i == 0 else o for i, o in enumerate(tx.outputs)))
        previous = next(coin.output for key, coin in chain.list_utxos() if key == (tx.inputs[0].prev_txid, tx.inputs[0].prev_index))
        conflicting = sign_p2wpkh(conflicting, 0, previous, alice)
        try:
            chain.submit_transaction(conflicting)
        except InvalidTransaction:
            double_spend_rejected = True
        else:
            raise AssertionError('Conflicting spend was accepted')
        block = chain.mine(miner.script_pubkey)[0]
        assert chain.balance(bob.script_pubkey) == 300_000_000
        before_restart = chain.info()
        balances = {'alice_total_smw': format_amount(chain.balance(alice.script_pubkey)), 'bob_total_smw': format_amount(chain.balance(bob.script_pubkey)), 'miner_total_smw': format_amount(chain.balance(miner.script_pubkey))}
    with Chain(database, clock=clock) as chain:
        restart_identical = chain.info() == before_restart
        assert restart_identical
        alternative = chain.make_block(miner.script_pubkey, (), parent_hash=fork_point, extra_nonce=1)
        tie_activated = chain.accept_block(alternative)
        assert not tie_activated and chain.tip_hash == block.block_hash()
        winner = chain.make_block(miner.script_pubkey, (), parent_hash=alternative.block_hash(), extra_nonce=1)
        assert chain.accept_block(winner)
        assert chain.balance(bob.script_pubkey) == 0
        returned_to_pool = tx.txid() in {item.txid() for item in chain.mempool_transactions()}
        assert returned_to_pool
        reorg = chain.info()
        chain.mine(miner.script_pubkey)
        assert chain.balance(bob.script_pubkey) == 300_000_000
        final = chain.info()
    result = {'artifact_version': __version__, 'scope': 'independent local-regtest prototype', 'public_network_ready': False, 'fixture_time': FIXTURE_TIME, 'test_keys_public': True, 'initial': initial, 'maturity': {'height_99_spendable_smw': format_amount(immature), 'height_100_spendable_in_next_block_smw': format_amount(mature)}, 'payment': {'txid': hash_to_display(tx.txid()), 'amount_smw': '3.00000000', 'fee_smw': '0.00100000', 'confirmed_height': 101, 'double_spend_rejected': double_spend_rejected, **balances}, 'restart_preserved_tip_and_utxo': restart_identical, 'reorg': {'equal_work_replaced_tip': tie_activated, 'disconnected_payment_returned_to_mempool': returned_to_pool, 'after_reorg': reorg, 'reconfirmed_height': final['height']}, 'final': final}
    output = directory / 'demo_result.json'
    document = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    reject_wallet_overwrite(output)
    output.write_text(document, encoding='utf-8')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description='Run SUMUWW demonstration with public test keys in a fresh directory')
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(run(args.directory), ensure_ascii=False, indent=2))
    except (ValueError, OSError) as exc:
        parser.exit(2, f'{type(exc).__name__}: {exc}\n')


if __name__ == '__main__':
    main()
