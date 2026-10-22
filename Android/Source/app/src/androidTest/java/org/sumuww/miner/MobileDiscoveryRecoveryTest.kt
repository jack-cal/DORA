package org.sumuww.miner

import android.net.ConnectivityManager
import androidx.test.platform.app.InstrumentationRegistry
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.junit.Assert.assertEquals
import org.junit.Test

/** Isolated Android runtime tests; no production wallet, node or fixed peer. */
class MobileDiscoveryRecoveryTest {
    @Test fun platformNetworkIdentityMatchesActualDefaultNetwork() {
        val app = InstrumentationRegistry.getInstrumentation().targetContext
        AndroidInterfaces.configure(app)
        val manager = app.getSystemService(ConnectivityManager::class.java)
        val network = manager.activeNetwork
        val links = network?.let { manager.getLinkProperties(it) }
        val expected = if (network == null || links == null) "" else
            "${network.networkHandle}|${links.interfaceName}|${links.linkAddresses.map { it.toString() }.sorted().joinToString(",")}"
        assertEquals(expected, AndroidInterfaces.networkIdentity())
        if (!Python.isStarted()) Python.start(AndroidPlatform(app))
        val value = Python.getInstance().getModule("mobile_interfaces").callAttr("network_identity")
        val actual = value?.toString().orEmpty()
        assertEquals(expected, if (actual == "None") "" else actual)
    }

    @Test fun realUdpDiscoveryRecoveryAndTcpSynchronization() {
        val app = InstrumentationRegistry.getInstrumentation().targetContext
        AndroidInterfaces.configure(app)
        if (!Python.isStarted()) Python.start(AndroidPlatform(app))
        val globals = Python.getInstance().getModule("builtins").callAttr("dict")
        globals.callAttr("__setitem__", "test_cache", app.cacheDir.absolutePath)
        Python.getInstance().getModule("builtins").callAttr("exec", """
            import io, sys, tempfile, unittest, pc_tests
            tempfile.tempdir = test_cache
            sys.modules['tests'] = pc_tests
            from pc_tests import (test_mobile_dht_recovery, test_dht_peer_v29,
                                  test_android_dht_ipv6, test_handshake_progress_deadline)
            modules = (test_mobile_dht_recovery, test_dht_peer_v29,
                       test_android_dht_ipv6, test_handshake_progress_deadline)
            suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(m) for m in modules)
            stream = io.StringIO()
            result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
            print(stream.getvalue(), flush=True)
            if not result.wasSuccessful(): raise AssertionError(stream.getvalue())
            assert result.testsRun == 25, result.testsRun
        """.trimIndent(), globals)
    }
}
