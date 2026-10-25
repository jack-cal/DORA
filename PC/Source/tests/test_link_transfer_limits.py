import unittest
from unittest.mock import patch
from sumuww.boundary_transport import (PartReceiver, PART_HEADER, fragments,
    MAX_TRANSFER_BYTES, MAX_TRANSFER_SECONDS)


class LinkTransferLimits(unittest.TestCase):
    def setUp(self):
        self.receiver=PartReceiver()
        self.addCleanup(self.receiver.close)

    @staticmethod
    def part(total,offset=0):
        return PART_HEADER.pack(b'bcall'.ljust(12,b'\0'),bytes(16),total,offset,bytes(32))+b'x'

    def test_rejects_large_declared_transfer_before_allocating_a_file(self):
        with patch('sumuww.boundary_transport.tempfile.TemporaryFile') as temporary:
            with self.assertRaisesRegex(ValueError,'total byte budget'):
                self.receiver.receive(object(),self.part(1<<40))
            temporary.assert_not_called()
        self.assertFalse(self.receiver.pending)

    def test_aggregate_budget_is_released_after_disconnect(self):
        sessions=[object() for _ in range(5)]
        for session in sessions[:4]:self.receiver.receive(session,self.part(MAX_TRANSFER_BYTES))
        with self.assertRaisesRegex(ValueError,'pending transfers'):
            self.receiver.receive(sessions[4],self.part(MAX_TRANSFER_BYTES))
        self.receiver.discard(sessions[0])
        self.receiver.receive(sessions[4],self.part(MAX_TRANSFER_BYTES))
        self.assertEqual(4,len(self.receiver.pending))

    def test_continuous_fragments_cannot_extend_total_deadline(self):
        session=object()
        with patch('sumuww.boundary_transport.time.monotonic',return_value=100):
            self.receiver.receive(session,self.part(100))
        with patch('sumuww.boundary_transport.time.monotonic',return_value=101+MAX_TRANSFER_SECONDS):
            with self.assertRaisesRegex(ValueError,'total transfer deadline'):
                self.receiver.receive(session,self.part(100,1))
        self.assertFalse(self.receiver.pending)

    def test_ordinary_fragmented_payload_round_trips(self):
        payload=b'normal transfer'*25000;session=object();result=None
        for part in fragments('bcall',payload):result=self.receiver.receive(session,part)
        self.assertEqual(('bcall',payload),result)
        self.assertFalse(self.receiver.pending)
