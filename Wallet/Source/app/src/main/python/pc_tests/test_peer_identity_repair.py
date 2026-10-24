"""Identity accounting and repair of already established alternate routes."""
import asyncio
import tempfile
import time
import unittest
from pathlib import Path

from sumuww.peer import PeerNode, _Session, VERIFIED_PEER_FRESHNESS


class Writer:
    def __init__(self):
        self.closed = False

    def is_closing(self):
        return self.closed

    def close(self):
        self.closed = True


class PeerIdentityRepairTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.node = PeerNode(Path(self.tmp.name) / 'node.sqlite', discover_peers=False)

    def tearDown(self):
        self.node.chain.close()
        self.tmp.cleanup()

    def route(self, identity, host, *, verified=True):
        session = _Session(None, Writer(), (host, 40113))
        session.remote_ip = host
        session.ready = True
        session.nonce = identity
        session.synchronized = verified
        session.verified_once = verified
        session.last_verified_at = time.monotonic()
        self.node._sessions[id(session.writer)] = session
        return session

    def test_aliases_do_not_inflate_nodes_or_mining_anchors(self):
        self.route(1, '127.0.0.1')
        self.route(1, '::1')
        self.route(2, '127.0.0.1')
        info = self.node.info()
        self.assertEqual(2, info['peers'])
        self.assertEqual(3, info['active_connections'])
        self.assertEqual(2, info['synchronized_peers'])
        self.assertEqual(2, info['validated_mining_anchors'])
        self.assertEqual(2, len(info['peer_connections']))
        self.assertEqual(2, len({row['peer_id'] for row in info['peer_connections']}))

    def test_repair_releases_duplicate_but_preserves_other_app_on_same_ip(self):
        original = self.route(1, '127.0.0.1')
        duplicate = self.route(1, '::1')
        other_app = self.route(2, '127.0.0.1')
        self.node._retire_duplicate_transports()
        self.assertFalse(original.writer.is_closing())
        self.assertTrue(duplicate.writer.is_closing())
        self.assertFalse(other_app.writer.is_closing())
        self.assertIs(original, self.node._outgoing_session(duplicate.outgoing))
        self.assertEqual(2, self.node.info()['active_connections'])
        self.assertEqual(1, self.node.info()['stats']['duplicate_connection_rejections'])
        self.node._retire_duplicate_transports()
        self.assertEqual(1, self.node.info()['stats']['duplicate_connection_rejections'])

    def test_unverified_nonce_claim_cannot_displace_validated_route(self):
        claimant = self.route(1, '127.0.0.1', verified=False)
        established = self.route(1, '::1')
        self.node._retire_duplicate_transports()
        self.assertTrue(claimant.writer.is_closing())
        self.assertFalse(established.writer.is_closing())
        self.assertEqual(1, self.node.synchronization_info()['validated_mining_anchors'])

    def test_no_route_is_retired_before_any_full_validation(self):
        first = self.route(1, '127.0.0.1', verified=False)
        second = self.route(1, '::1', verified=False)
        self.node._retire_duplicate_transports()
        self.assertFalse(first.writer.is_closing())
        self.assertFalse(second.writer.is_closing())
        self.assertEqual(0, self.node.synchronization_info()['validated_mining_anchors'])
        self.assertEqual(1, self.node.info()['peers'])

    def test_fresh_validated_route_survives_stale_alias(self):
        stale = self.route(1, '127.0.0.1')
        fresh = self.route(1, '::1')
        stale.last_verified_at -= VERIFIED_PEER_FRESHNESS * 2
        self.node._retire_duplicate_transports()
        self.assertTrue(stale.writer.is_closing())
        self.assertFalse(fresh.writer.is_closing())
        self.assertEqual(1, self.node.synchronization_info()['validated_mining_anchors'])
