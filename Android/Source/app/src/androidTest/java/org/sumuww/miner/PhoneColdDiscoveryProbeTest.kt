package org.sumuww.miner

import androidx.test.platform.app.InstrumentationRegistry
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.junit.Test
import java.io.File

/** Selected explicitly on the physical phone; UDP search only, never fixed peers. */
class PhoneColdDiscoveryProbeTest {
    @Test fun actualMobileNetworkFreshPublicDhtSearch() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        AndroidInterfaces.configure(context)
        if (!Python.isStarted()) Python.start(AndroidPlatform(context))
        val globals = Python.getInstance().getModule("builtins").callAttr("dict")
        Python.getInstance().getModule("builtins").callAttr("exec", """
            import asyncio, ipaddress, json, socket
            from mobile_interfaces import _read_android, network_identity
            from sumuww.dht_discovery import DhtDiscovery
            interfaces = _read_android()
            ipv6 = next((i.host for i in interfaces if ':' in i.host and ipaddress.ip_address(i.host).is_global), None)
            async def probe(family):
                hints = []
                d = DhtDiscovery('dora', lambda values:hints.extend(values), family=family,
                                 source_provider=lambda:ipv6, network_provider=network_identity,
                                 self_endpoints=lambda:tuple((i.host,18444) for i in interfaces))
                rounds = []
                try:
                    if await d._ensure_transport():
                        d._active = True
                        for index in range(2):
                            result = await d.lookup_once()
                            rounds.append({'round':index+1,'hints':len(result),'result':d.info()['last_lookup_result']})
                    return {'family':family,'rounds':rounds,'distinct_unverified_hints':len(set(hints)),
                            'hints':sorted(set(hints)),'info':d.info()}
                finally:await d.stop()
            async def run():return await asyncio.gather(probe(socket.AF_INET),probe(socket.AF_INET6))
            report = json.dumps({'scope':'actual Android network; empty isolated DHT state; no announcements; no peer TCP probes',
                                 'interfaces':[i.host for i in interfaces], 'results':asyncio.run(run())})
        """.trimIndent(), globals)
        File(context.getExternalFilesDir(null), "phone-cold-discovery-probe.json").writeText(globals.callAttr("get", "report").toString())
    }
}
