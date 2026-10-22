"""Standalone manual known-node monitor; no wallet or hosted node is owned."""
import multiprocessing
import os
import sys


def main():
    multiprocessing.freeze_support()
    if sys.stdout is None:
        sys.stdout = open(os.devnull, 'w', encoding='utf-8')
    if sys.stderr is None:
        sys.stderr = open(os.devnull, 'w', encoding='utf-8')
    from sumuww.node_manager import main as run_manager
    return run_manager(sys.argv[1:]) or 0


if __name__ == '__main__':
    raise SystemExit(main())
