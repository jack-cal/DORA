package org.sumuww.miner

import androidx.test.platform.app.InstrumentationRegistry
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.junit.Test

/** Run the actual TCP handoff regression in the physical Android runtime. */
class ShortSyncedRecoveryTest {
    @Test fun retryKeepsSyncAndRestoresDiscovery() {
        val app=InstrumentationRegistry.getInstrumentation().targetContext
        AndroidInterfaces.configure(app)
        if (!Python.isStarted()) Python.start(AndroidPlatform(app))
        val globals=Python.getInstance().getModule("builtins").callAttr("dict")
        globals.callAttr("__setitem__", "test_cache", app.cacheDir.absolutePath)
        Python.getInstance().getModule("builtins").callAttr("exec", """
            import io, sys, tempfile, unittest, pc_tests
            tempfile.tempdir=test_cache
            sys.modules['tests']=pc_tests
            from pc_tests import test_short_synced_reconnect, test_protocol_retry_recovery, test_handshake_early_close
            modules=(test_short_synced_reconnect,test_protocol_retry_recovery,test_handshake_early_close)
            suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(m) for m in modules)
            expected=suite.countTestCases()
            stream=io.StringIO()
            result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
            print(stream.getvalue(),flush=True)
            if not result.wasSuccessful():raise AssertionError(stream.getvalue())
            assert result.testsRun==expected and expected>=11,(result.testsRun,expected)
        """.trimIndent(),globals)
    }
}
