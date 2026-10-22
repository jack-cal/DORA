import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from sumuww.app_service import AppService


class ManagedPrivacyTests(unittest.IsolatedAsyncioTestCase):
    async def test_default_direct_never_constructs_or_starts_a_router(self):
        with tempfile.TemporaryDirectory() as folder:
            factory=Mock(side_effect=AssertionError('Direct mode must not start Tor/I2P'))
            service=AppService(folder,network='regtest',peers=[],bootstrap=False,
                               allow_internet=True,allow_lan=False,privacy_router_factory=factory)
            try:
                await asyncio.wrap_future(service.start())
                self.assertEqual('direct',(await asyncio.wrap_future(service.status()))['connection']['privacy']['mode'])
                factory.assert_not_called()
            finally: await asyncio.wrap_future(service.stop())

    async def test_unavailable_embedded_router_does_not_restore_direct_mode(self):
        class Unavailable:
            def __init__(self,mode,folder):self.mode=mode;self.stopped=False
            async def ensure_running(self):raise OSError('Missing/corrupt pinned runtime')
            async def stop(self):self.stopped=True
            def info(self):return {'embedded':True,'running':False,'version':None}
        with tempfile.TemporaryDirectory() as folder:
            routers=[]
            def factory(*args):
                value=Unavailable(*args);routers.append(value);return value
            service=AppService(folder,network='regtest',peers=[],bootstrap=False,
                               allow_internet=True,allow_lan=False,privacy_router_factory=factory)
            try:
                await asyncio.wrap_future(service.start())
                await asyncio.wrap_future(service.configure_privacy('tor'))
                await asyncio.sleep(.15)
                state=await asyncio.wrap_future(service.status())
                self.assertEqual('tor',state['connection']['privacy']['mode'])
                self.assertTrue(state['connection']['privacy']['router_error'])
                self.assertEqual('127.0.0.1',service._node.address[0])
                await asyncio.wrap_future(service.configure_privacy('direct'))
                self.assertTrue(routers[0].stopped)
                self.assertEqual('direct',(await asyncio.wrap_future(service.status()))['connection']['privacy']['mode'])
            finally:await asyncio.wrap_future(service.stop())
