package org.sumuww.miner

import androidx.test.platform.app.InstrumentationRegistry
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.junit.Test
import java.io.File

/** Compare one request-timing variable over fresh actual mobile peer connections. */
class PhoneAddressCloseCauseTest {
    @Test fun actualMobileAddressRequestTiming() {
        val app=InstrumentationRegistry.getInstrumentation().targetContext
        AndroidInterfaces.configure(app)
        if (!Python.isStarted()) Python.start(AndroidPlatform(app))
        val globals=Python.getInstance().getModule("builtins").callAttr("dict")
        globals.callAttr("__setitem__","output_path",File(app.getExternalFilesDir(null),"phone-address-close-cause.json").absolutePath)
        globals.callAttr("__setitem__","fixture_parent",app.cacheDir.absolutePath)
        globals.callAttr("__setitem__","chain_path",File(app.filesDir,"sumuww/node.sqlite").absolutePath)
        Python.getInstance().getModule("builtins").callAttr("exec","""
            import asyncio, ipaddress, itertools, json, socket, sqlite3, tempfile, time
            sequence=itertools.count(1)
            from pathlib import Path
            from mobile_interfaces import _read_android, network_identity
            from sumuww.dht_discovery import DhtDiscovery
            from sumuww.peer import PeerNode
            from sumuww.wire import decode_version
            report={'scope':'physical mobile; fresh DHT; temporary copy of public chain only; no wallet/mining; v3 requests with controlled getaddr timing; diagnostic not production', 'phases':[], 'events':[], 'complete':False}
            excluded={'61.108.95.185','2406:5900:2:fd9::627'}
            def save():Path(output_path).write_text(json.dumps(report),encoding='utf-8')
            def event(kind,**values):
                if len(report['events'])<10000:report['events'].append({'t':time.monotonic(),'kind':kind,**values})
            class TrialNode(PeerNode):
                async def _open_target(self,target):
                    if target[0] in excluded:raise OSError('Test excludes this PC')
                    return await super()._open_target(target)
                async def _handshake(self,session):
                    session.test_started=time.monotonic()
                    session.test_sid=next(sequence)
                    self._legacy_targets.discard(session.outgoing)
                    self._v2_targets.discard(session.outgoing)
                    event('attempt',phase=self.phase,target=session.outgoing,sid=session.test_sid)
                    result=await super()._handshake(session)
                    session.test_ready_at=time.monotonic()
                    event('ready',phase=self.phase,sid=session.test_sid,target=session.outgoing)
                    return result
                def _remember_legacy(self,target):return False
                async def _request_addresses(self,session,now=None):
                    if time.monotonic()-getattr(session,'test_ready_at',time.monotonic())<self.address_delay:return
                    return await super()._request_addresses(session,now)
                async def _send(self,session,command,payload=b''):
                    if command in ('getaddr','addr','verack'):
                        event('sent',phase=self.phase,sid=session.test_sid,target=session.outgoing,command=command)
                    return await super()._send(session,command,payload)
                async def _read(self,session):
                    try:frame=await super()._read(session)
                    except BaseException as exc:
                        event('read_failed',phase=self.phase,sid=session.test_sid,target=session.outgoing,stage=session.handshake_stage,error=type(exc).__name__,detail=str(exc),ready=session.ready,closing=session.writer.is_closing())
                        raise
                    if frame.command in ('version','verack','headers','pong','getaddr','addr'):
                        extra={}
                        if frame.command=='version':
                            v=decode_version(frame.payload);extra={'remote_protocol':v.protocol,'nonce_hint':f'{v.nonce:016x}'}
                        event('received',phase=self.phase,sid=session.test_sid,target=session.outgoing,command=frame.command,**extra)
                    return frame
            async def search(family,v6):
                hints=[]
                d=DhtDiscovery('dora',lambda values:hints.extend(values),family=family,source_provider=lambda:v6,network_provider=network_identity,
                               self_endpoints=lambda:tuple((i.host,18444) for i in _read_android()))
                try:
                    if await d._ensure_transport():
                        d._active=True
                        for _ in range(2):await d.lookup_once()
                    return {'family':family,'hints':sorted(set(hints)),'info':d.info()}
                finally:await d.stop()
            async def run():
                report['network_identity']=network_identity();save()
                interfaces=_read_android()
                v6=next((i.host for i in interfaces if ':' in i.host and ipaddress.ip_address(i.host).is_global),None)
                report['search']=await asyncio.gather(search(socket.AF_INET,v6),search(socket.AF_INET6,v6))
                hints=[]
                for result in report['search']:
                    for endpoint in result['hints']:
                        target=tuple(endpoint)
                        if target[0] not in excluded and target not in hints:hints.append(target)
                report['fresh_external_hints']=hints;save()
                for phase,delay in enumerate((8,0,8,0)):
                    with tempfile.TemporaryDirectory(prefix='smw-address-close-',dir=fixture_parent) as folder:
                        database=Path(folder)/'public-chain.sqlite'
                        # Read only the public chain DB. Never open a wallet file.
                        source=sqlite3.connect(Path(chain_path).as_uri()+'?mode=ro',uri=True)
                        dest=sqlite3.connect(database)
                        try:
                            tables={r[0] for r in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                            assert tables<= {'metadata','blocks','utxos','mempool','sqlite_sequence'},tables
                            source.backup(dest)
                        finally:dest.close();source.close()
                        node=TrialNode(database,network='dora',host='127.0.0.1',port=0,allow_internet=True,allow_lan=False,
                                       discover_peers=True,dht_enabled=False,auto_address=False,bootstrap_seeds=(),bootstrap_peers=(),
                                       max_peers=2,outgoing_target=2,timeout=5,poll_interval=.5,network_provider=network_identity)
                        node.phase=phase;node.address_delay=delay
                        row={'phase':phase,'address_delay_seconds':delay,'samples':[]}
                        report['phases'].append(row)
                        try:
                            await node.start()
                            for target in hints[:16]:node._addresses.add_hint(target)
                            async def refresh_fresh_contacts():
                                while node.running:
                                    results=await asyncio.gather(search(socket.AF_INET,v6),search(socket.AF_INET6,v6))
                                    report.setdefault('fresh_searches',[]).append({'phase':phase,'t':time.monotonic(),'results':results})
                                    for result in results:
                                        for endpoint in result['hints']:
                                            target=tuple(endpoint)
                                            if target[0] not in excluded:node._addresses.add_hint(target)
                                    save()
                                    await asyncio.sleep(1)
                            refresh=asyncio.create_task(refresh_fresh_contacts())
                            until=time.monotonic()+90
                            while time.monotonic()<until:
                                row['samples'].append({'t':time.monotonic(),'height':node.chain.summary()['height'],
                                    'sessions':[{'sid':getattr(s,'test_sid',None),'target':s.outgoing,'ready':s.ready,'sync':s.synchronized,'closing':s.writer.is_closing()} for s in node._sessions.values()]})
                                row['attempts']=list(node._recent_peer_attempts);save()
                                await asyncio.sleep(3)
                        finally:
                            row['test_initiated_stop_at']=time.monotonic()
                            if 'refresh' in locals():
                                refresh.cancel()
                                await asyncio.gather(refresh,return_exceptions=True)
                            await node.stop();save()
                report['complete']=True;save()
            try:asyncio.run(run())
            except BaseException as exc:
                report['test_error']=type(exc).__name__+': '+str(exc);save();raise
        """.trimIndent(),globals)
    }
}
