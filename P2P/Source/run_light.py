"""Dedicated lightweight edition; separate default profile and executable."""
from pathlib import Path
import multiprocessing
import sys
import traceback

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'vendor'))
sys.path.insert(0, str(ROOT))

if __name__ == '__main__':
    multiprocessing.freeze_support()
    if any(flag in sys.argv for flag in ('--legacy-lab', '--wallet-self-check', '--peer-self-check')):
        raise SystemExit('Use the Full edition for the bundled Bitcoin Core test laboratory.')
    try:
        if '--light-server-check' in sys.argv:
            from smw_trade.market.light_network import ElectrumPeer,LightNetwork,DEFAULT_SERVERS
            import json
            directory=Path(sys.argv[sys.argv.index('--data-dir')+1]);directory.mkdir(parents=True,exist_ok=False)
            peers=[ElectrumPeer(url) for url in DEFAULT_SERVERS]
            try:
                results,errors=LightNetwork.parallel(peers,lambda p:p.call('blockchain.headers.subscribe'))
                report={'passed':len({p.address for p,r in results})>=2,'tls_connections':[{'url':p.url,'height':r['height']} for p,r in results],
                        'errors':errors,'transaction_or_header_validation':False,'public_funds_used':False}
                (directory/'report.json').write_text(json.dumps(report,indent=2))
                if not report['passed']:raise ValueError('Packaged TLS connection check failed.')
            finally:
                for peer in peers:peer.close()
        else:
            from smw_trade.app import main
            main(ROOT, flavor='light')
    except Exception:
        if not any(flag in sys.argv for flag in ('--market-self-check','--light-server-check')):
            raise
        directory = Path(sys.argv[sys.argv.index('--data-dir') + 1])
        directory.parent.mkdir(parents=True, exist_ok=True)
        directory.with_suffix('.error.log').write_text(traceback.format_exc(), encoding='utf8')
        raise SystemExit(1)
