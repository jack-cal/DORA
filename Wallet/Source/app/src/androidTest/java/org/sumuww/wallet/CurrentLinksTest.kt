package org.sumuww.wallet

import androidx.test.platform.app.InstrumentationRegistry
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.junit.Test

/** Disposable protocol fixtures only; installed wallet data is never opened. */
class CurrentLinksTest {
    @Test fun currentConsensusAndRecovery() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        if (!Python.isStarted()) Python.start(AndroidPlatform(context))
        val builtins = Python.getInstance().getModule("builtins")
        val globals = builtins.callAttr("dict")
        globals.callAttr("__setitem__", "test_cache", context.cacheDir.absolutePath)
        builtins.callAttr("exec", """
import io, sys, tempfile, unittest, pc_tests
tempfile.tempdir = test_cache
sys.modules['tests'] = pc_tests
modules = ['test_links9000', 'test_beacon_recovery', 'test_links_transport',
           'test_links_legacy_transport', 'test_p20_dgw10', 'test_activation_prefix']
suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName('pc_tests.' + name) for name in modules)
stream = io.StringIO()
result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
if not result.wasSuccessful(): raise AssertionError(stream.getvalue())
        """.trimIndent(), globals)
    }
}
