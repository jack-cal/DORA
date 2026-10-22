import ctypes
import json
from unittest.mock import patch
import mobile_peer_trace as trace
from pc_tests.test_phone_connection_trace import PhoneConnectionTraceTests

class _Log:
    def __call__(self, priority, tag, payload):
        events.append(json.loads(payload))
class _Library:
    pass
events=[]
library=_Library()
setattr(library, '__android_log_write', _Log())
with patch.object(ctypes, 'CDLL', return_value=library):
    trace.install()

class RuntimeTraceTests(PhoneConnectionTraceTests):
    async def asyncSetUp(self):
        events.clear()
        trace._window=0
        trace._count=0
        await super().asyncSetUp()
    async def test_eof_is_recorded_before_client_cleanup(self):
        session=next(s for s in self.client._sessions.values() if s.ready)
        sid=session._trace_id
        await self.server.stop()
        await self.wait(lambda:any(e['event']=='session_end' and e.get('sid')==sid for e in events))
        rows=[e for e in events if e.get('sid')==sid]
        names=[e['event'] for e in rows]
        self.assertIn('transport_eof', names)
        self.assertIn('local_close', names)
        self.assertLess(names.index('transport_eof'),names.index('local_close'))
        self.assertIn('frame_received', names)
        self.assertIn('handshake_end', names)
