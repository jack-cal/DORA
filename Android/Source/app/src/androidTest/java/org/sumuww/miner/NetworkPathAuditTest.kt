package org.sumuww.miner

import android.content.Intent
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.test.platform.app.InstrumentationRegistry
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import java.io.File

/** Emulator-owned paths and UI fixtures. Never evidence of physical 5G ingress. */
class NetworkPathAuditTest {
    private fun python(): Python {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        AndroidInterfaces.configure(context)
        PrivacyRuntime.configure(context)
        if (!Python.isStarted()) Python.start(AndroidPlatform(context))
        return Python.getInstance()
    }

    @Test fun automaticMeshAndIndependentIpv6ListenerRecovery() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val globals = python().getModule("builtins").callAttr("dict")
        globals.callAttr("__setitem__", "test_cache", context.cacheDir.absolutePath)
        python().getModule("builtins").callAttr("exec", """
            import io, sys, tempfile, unittest, pc_tests
            tempfile.tempdir = test_cache
            sys.modules['tests'] = pc_tests
            from pc_tests import test_network_path_audit
            stream = io.StringIO()
            result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
                unittest.defaultTestLoader.loadTestsFromModule(test_network_path_audit))
            if not result.wasSuccessful(): raise AssertionError(stream.getvalue())
            assert result.testsRun == 4, result.testsRun
            report = stream.getvalue()
        """.trimIndent(), globals)
        File(context.getExternalFilesDir(null), "network-path-python-tests.txt").writeText(globals.callAttr("get", "report").toString())
    }

    @Test fun actualPeerErrorIsVisibleAndUnavailableStatusHidesOldValues() {
        val inst = InstrumentationRegistry.getInstrumentation()
        val context = inst.targetContext
        SumuwwConsent.revoke(context) // This emulator test starts no production node.
        val activity = inst.startActivitySync(Intent(context, MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) as MainActivity
        try {
            inst.runOnMainSync {
                val screen = SumuwwScreens(activity, { it }, { _, _, _ -> })
                val status = JSONObject().put("node", JSONObject().put("peers", 3)
                    .put("last_peer_error", "fixture: TCP connection timed out"))
                    .put("mobile_diagnostics", JSONObject().put("last_error", "—"))
                val model = SumuwwScreens.Model(14, status, null, 0, "all", 0, "00:00:00",
                    "1", "", "", null, false, false, SumuwwThemeCalendar.resolve("default"), "light", "English")
                fun texts(view: View): List<String> = when (view) {
                    is ViewGroup -> (0 until view.childCount).flatMap { texts(view.getChildAt(it)) }
                    is TextView -> listOf(view.text.toString())
                    else -> emptyList()
                }
                screen.render(model)
                assertTrue(texts(screen.content).contains("최근 피어 연결 오류"))
                assertTrue(texts(screen.content).contains("fixture: TCP connection timed out"))
                screen.render(model.copy(statusUnavailable = true))
                assertFalse(texts(screen.content).contains("fixture: TCP connection timed out"))
                screen.render(model.copy(status = JSONObject().put("node", JSONObject().put("peers", 0))))
                assertFalse(texts(screen.content).contains("fixture: TCP connection timed out"))
            }
        } finally { inst.runOnMainSync { activity.finish() } }
    }

    @Test fun embeddedRoutersOpenTheirActualLocalApisWithoutPeerContacts() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val globals = python().getModule("builtins").callAttr("dict")
        globals.callAttr("__setitem__", "test_cache", context.cacheDir.absolutePath)
        python().getModule("builtins").callAttr("exec", """
            import asyncio, json, tempfile
            from sumuww.managed_privacy import ManagedRouter
            from mobile_interfaces import install
            install()
            async def run():
                rows = []
                for mode in ('tor', 'i2p'):
                    with tempfile.TemporaryDirectory(dir=test_cache, prefix='owned-router-api-') as root:
                        router = ManagedRouter(mode, root)
                        writer = None
                        try:
                            port = await asyncio.wait_for(router.ensure_running(), 25)
                            reader, writer = await asyncio.wait_for(asyncio.open_connection('127.0.0.1', port), 3)
                            if mode == 'tor':
                                writer.write(bytes([5,1,0])); await writer.drain()
                                assert await asyncio.wait_for(reader.readexactly(2), 3) == bytes([5,0])
                            else:
                                writer.write(b'HELLO VERSION MIN=3.1 MAX=3.1\n'); await writer.drain()
                                answer = await asyncio.wait_for(reader.readline(), 3)
                                assert answer.startswith(b'HELLO REPLY ') and b'RESULT=OK' in answer
                            rows.append({'mode':mode, 'packaged_process_running':router.info()['running'],
                                         'local_api_responded':True,
                                         'overlay_internet_bootstrap_verified':False,
                                         'sumuww_peer_connected':False})
                        finally:
                            if writer is not None:
                                writer.close()
                                try: await asyncio.wait_for(writer.wait_closed(), 1)
                                except (OSError,TimeoutError): pass
                            await router.stop()
                        assert not router.info()['running']
                return rows
            report = json.dumps(asyncio.run(run()))
        """.trimIndent(), globals)
        File(context.getExternalFilesDir(null), "network-path-router-apis.json").writeText(globals.callAttr("get", "report").toString())
    }
}
