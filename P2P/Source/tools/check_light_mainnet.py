"""Read-only public header/proof check; never creates keys or sends transactions."""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'vendor')]
from smw_trade.market.light_network import ElectrumPeer, LightNetwork, DEFAULT_SERVERS
from sumuww.transaction import Transaction


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--probe', action='store_true')
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    peers = [ElectrumPeer(url) for url in DEFAULT_SERVERS]
    if args.probe:
        try:
            results, errors = LightNetwork.parallel(peers, lambda p: p.call('blockchain.headers.subscribe'))
            report = {'servers': [{'url': p.url, 'height': r['height'], 'ip': p.address} for p, r in results], 'errors': errors}
        finally:
            for p in peers:
                p.close()
    else:
        last = [0]
        def progress(height, total):
            if time.monotonic() - last[0] > 10:
                print(json.dumps({'verified_headers': height, 'target': total}), flush=True)
                last[0] = time.monotonic()
        network = LightNetwork(args.directory / 'bitcoin-headers.bin', DEFAULT_SERVERS, progress=progress)
        started = time.monotonic()
        try:
            height = network.sync(force=True)
            proof_height=height-6
            item=network.consistent('blockchain.transaction.id_from_pos',proof_height,0,True)
            proof={'block_height':proof_height,'pos':0,'merkle':item['merkle']}
            network.chain.verify_merkle(item['tx_hash'],proof_height,proof)
            raw=network.consistent('blockchain.transaction.get',item['tx_hash'],False)
            tx=Transaction.deserialize(bytes.fromhex(raw))
            if tx.txid()[::-1].hex()!=item['tx_hash']:raise ValueError('Live transaction ID mismatch.')
            report = {'height': height, 'hash': network.chain.digest(height), 'header_bytes': len(network.chain.data),
                      'elapsed_seconds': round(time.monotonic() - started, 2), 'verified_servers': len(network.active),
                      'download_bytes': sum(p.received for p in network.peers), 'public_funds_used': False,
                      'servers': [p.url for p in network.active], 'public_transaction_proof':{'height':proof_height,'txid':item['tx_hash'],'passed':True}}
        finally:
            network.close()
    (args.directory / ('probe.json' if args.probe else 'report.json')).write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
