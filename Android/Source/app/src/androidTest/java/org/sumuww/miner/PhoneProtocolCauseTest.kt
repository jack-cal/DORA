package org.sumuww.miner

import androidx.test.platform.app.InstrumentationRegistry
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.junit.Test
import java.io.File

/** Diagnostic only: fresh DHT results, separate temporary chain, no wallet/mining. */
class PhoneProtocolCauseTest {
    @Test fun freshExternalProtocolTrials() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        AndroidInterfaces.configure(context)
        if (!Python.isStarted()) Python.start(AndroidPlatform(context))
        val globals = Python.getInstance().getModule("builtins").callAttr("dict")
        globals.callAttr("__setitem__", "output_path", File(context.getExternalFilesDir(null), "phone-protocol-cause.json").absolutePath)
        globals.callAttr("__setitem__", "fixture_parent", context.cacheDir.absolutePath)
        Python.getInstance().getModule("builtins").callAttr("exec", """
            import asyncio, collections, ipaddress, json, socket, tempfile, time
            from pathlib import Path
            from mobile_interfaces import _read_android, network_identity
            from sumuww.dht_discovery import DhtDiscovery
            from sumuww.peer import PeerNode
            from sumuww.wire import decode_version
            report = {'scope':'physical mobile network; fresh DHT only; temporary chain; no mining or wallet; protocol trials are diagnostic, not a production fix', 'phases':[], 'events':[], 'complete':False}
            # Exclusions only. Never connect to this PC during this experiment.
            excluded = {'61.108.95.185','2406:5900:2:fd9::627'}
            def save():Path(output_path).write_text(json.dumps(report), encoding='utf-8')
            def event(kind, **values):
                row = {'t':time.monotonic(),'kind':kind,**values}
                if len(report['events']) < 3000:report['events'].append(row)
            class TrialNode(PeerNode):
                async def _open_target(self, target):
                    if target[0] in excluded:raise OSError('Test excludes this PC')
                    event('dial', protocol=self.trial_protocol,target=target)
                    return await super()._open_target(target)
                async def _handshake(self, session):
                    self._legacy_targets.discard(session.outgoing)
                    self._v2_targets.discard(session.outgoing)
                    if self.trial_protocol==1:self._legacy_targets.add(session.outgoing)
                    elif self.trial_protocol==2:self._v2_targets.add(session.outgoing)
                    return await super()._handshake(session)
                def _remember_legacy(self, target):pass
                async def _read(self, session):
                    try:frame=await super()._read(session)
                    except BaseException as exc:
                        event('read_failed',protocol=self.trial_protocol,target=session.outgoing,stage=session.handshake_stage,error=type(exc).__name__,detail=str(exc),ready=session.ready,local_closing=session.writer.is_closing())
                        raise
                    if frame.command in ('version','verack','headers','pong','addr'):
                        extra={}
                        if frame.command=='version':
                            version=decode_version(frame.payload)
                            extra={'remote_protocol':version.protocol,'nonce_hint':f'{version.nonce:016x}'}
                        event('received',protocol=self.trial_protocol,target=session.outgoing,command=frame.command,**extra)
                    return frame
            async def search(family, v6):
                hints=[]
                d=DhtDiscovery('dora',lambda values:hints.extend(values),family=family,source_provider=lambda:v6,
                               network_provider=network_identity,self_endpoints=lambda:tuple((i.host,18444) for i in _read_android()))
                try:
                    if await d._ensure_transport():
                        d._active=True
                        for _ in range(2):await d.lookup_once()
                    return {'family':family,'hints':sorted(set(hints)),'info':d.info()}
                finally:await d.stop()
            async def run():
                interfaces=_read_android()
                report['network_identity']=network_identity()
                report['interfaces']=[i.host for i in interfaces]
                save()
                v6=next((i.host for i in interfaces if ':' in i.host and ipaddress.ip_address(i.host).is_global),None)
                report['search']=await asyncio.gather(search(socket.AF_INET,v6),search(socket.AF_INET6,v6))
                hints=[]
                for result in report['search']:
                    for endpoint in result['hints']:
                        target=tuple(endpoint)
                        if target[0] not in excluded and target not in hints:hints.append(target)
                report['fresh_external_hints']=hints
                save()
                for phase,protocol in enumerate((3,1,3)):
                    with tempfile.TemporaryDirectory(prefix='smw-protocol-cause-',dir=fixture_parent) as folder:
                        node=TrialNode(Path(folder)/'isolated.sqlite',network='dora',host='127.0.0.1',port=0,
                                       allow_internet=True,allow_lan=False,discover_peers=True,dht_enabled=False,
                                       auto_address=False,bootstrap_seeds=(),bootstrap_peers=(),max_peers=3,outgoing_target=3,
                                       timeout=5,poll_interval=.5,network_provider=network_identity)
                        node.trial_protocol=protocol
                        row={'phase':phase,'requested_protocol':protocol,'started':time.monotonic(),'samples':[]}
                        report['phases'].append(row)
                        try:
                            await node.start()
                            for target in hints[:16]:node._addresses.add_hint(target)
                            until=time.monotonic()+90
                            while time.monotonic()<until:
                                sessions=[{'target':s.outgoing,'ready':s.ready,'sync':s.synchronized,'stage':s.handshake_stage,'protocol':s.protocol,'closing':s.writer.is_closing()} for s in node._sessions.values()]
                                row['samples'].append({'t':time.monotonic(),'sessions':sessions,'height':node.chain.summary()['height']})
                                row['attempts']=list(node._recent_peer_attempts)
                                save()
                                await asyncio.sleep(3)
                        finally:
                            row['test_initiated_stop_at']=time.monotonic()
                            await node.stop()
                            save()
                report['complete']=True
                save()
            try:asyncio.run(run())
            except BaseException as exc:
                report['test_error']=type(exc).__name__+': '+str(exc)
                save()
                raise
        """.trimIndent(), globals)
    }
}
