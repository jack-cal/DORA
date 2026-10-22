"""Observe the unchanged PC nonce search; never retain keys or header hashes."""
import threading
import time
from sumuww.block import REGTEST_POW_LIMIT


class MiningMetrics:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.guard = threading.Lock()
        self.foreground = True
        self.reset()

    def reset(self):
        with self.guard:
            self.attempts = 0
            self.seconds = 0.0
            self.started = None
            self.templates = 0
            self.rate = 0.0
            self.updated = self.clock()

    def snapshot(self):
        with self.guard:
            now = self.clock()
            return {'attempts': self.attempts,
                    'hashing_seconds': self.seconds + (now-self.started if self.started is not None else 0),
                    'hashes_per_second': self.rate if self.started is not None and now-self.updated < 3 else 0,
                    'templates': self.templates, 'hashing': self.started is not None,
                    'background': not self.foreground}

    def wrap(self, original):
        def measured(header, max_attempts=1_000_000, *, pow_limit=REGTEST_POW_LIMIT, cancel_check=None):
            beginning = self.clock()
            counted = 0
            checkpoints = 0
            last_time = beginning
            last_count = 0
            with self.guard:
                self.started = beginning
                self.templates += 1
            def checkpoint():
                nonlocal counted, checkpoints, last_time, last_count
                # PC calls before nonce 0, then before nonce 4096, 8192, ...
                if checkpoints:
                    counted += 4096
                    with self.guard:
                        self.attempts += 4096
                checkpoints += 1
                now = self.clock()
                if now-last_time >= 1:
                    with self.guard:
                        self.rate = (counted-last_count)/(now-last_time)
                        self.updated = now
                    last_time, last_count = now, counted
                cancelled = bool(cancel_check and cancel_check())
                return cancelled
            exact = None
            try:
                result = original(header, max_attempts, pow_limit=pow_limit, cancel_check=checkpoint)
                exact = result.nonce+1
                return result
            except Exception as error:
                from sumuww.errors import MiningExhausted
                if isinstance(error, MiningExhausted):
                    exact = max_attempts
                raise
            finally:
                with self.guard:
                    if exact is not None:
                        self.attempts += exact-counted
                    self.seconds += self.clock()-beginning
                    self.started = None
                    self.rate = 0.0
        return measured


metrics = MiningMetrics()
_installed = False


def install():
    global _installed
    if not _installed:
        # Only the platform adapter installs this transparent observer.
        # PC core files and all consensus validation remain byte-identical.
        from sumuww import chain
        chain.mine_header = metrics.wrap(chain.mine_header)
        _installed = True
