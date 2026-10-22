"""Standalone Windows GUI entry; data remains in the application's saved path."""

import multiprocessing
import os
import sys


def main():
    multiprocessing.freeze_support()
    # Windowed builds have no console streams. Libraries and argparse still
    # expect writable streams, while the GUI reports service errors itself.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, 'w', encoding='utf-8')
    if sys.stderr is None:
        sys.stderr = open(os.devnull, 'w', encoding='utf-8')
    from sumuww.app import main as run_app
    args = sys.argv[1:]
    if args and args[0] == 'app':
        args = args[1:]
    return run_app(args) or 0


if __name__ == '__main__':
    raise SystemExit(main())
