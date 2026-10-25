"""Standalone console entry for local node commands and the manual TCP daemon."""

import multiprocessing
import sys


def main(argv=None):
    multiprocessing.freeze_support()
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ['--version']:
        from sumuww import __version__
        print('SUMUWW ' + __version__)
        return 0
    if args == ['--htlc-selftest']:
        from sumuww.htlc_selftest import run_json
        print(run_json())
        return 0
    if args == ['--boundary-selftest']:
        from sumuww.boundary_selftest import run_json
        print(run_json())
        return 0
    if args and args[0] == 'peer':
        from sumuww.peerd import main as run_peer
        return run_peer(args[1:])
    if args and args[0] == 'rpc':
        from sumuww.rpc_client import main as run_rpc
        return run_rpc(args[1:])
    if args and args[0] == 'node':
        args.pop(0)
    from sumuww.__main__ import main as run_node
    return run_node(args)


if __name__ == '__main__':
    raise SystemExit(main())
