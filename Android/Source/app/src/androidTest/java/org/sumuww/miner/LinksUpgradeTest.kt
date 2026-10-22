package org.sumuww.miner

import androidx.test.platform.app.InstrumentationRegistry
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.io.File
import org.junit.Test

/** Run only against the separate .audit package; never the user's node data. */
class LinksUpgradeTest {
 @Test fun pairedProofsLatePeerAndPreservedRules() {
  val context=InstrumentationRegistry.getInstrumentation().targetContext
  check(context.packageName.endsWith(".audit")) { "Isolated audit package required" }
  if(!Python.isStarted())Python.start(AndroidPlatform(context))
  val builtins=Python.getInstance().getModule("builtins")
  val globals=builtins.callAttr("dict")
  globals.callAttr("__setitem__","test_cache",context.cacheDir.absolutePath)
  builtins.callAttr("exec","""
   import io, sys, tempfile, unittest, pc_tests
   tempfile.tempdir = test_cache
   sys.modules['tests'] = pc_tests
   from pc_tests.test_links9000 import LinkUpgradeTests
   from pc_tests.test_beacon_recovery import BeaconRecoveryTests
   from pc_tests.test_links_transport import LinkTransportTests
   from pc_tests.test_links_legacy_transport import LegacyLinkTransportTests
   from pc_tests import test_p20_dgw10
   stream = io.StringIO()
   suite = unittest.TestSuite([
       unittest.defaultTestLoader.loadTestsFromTestCase(LinkUpgradeTests),
       unittest.defaultTestLoader.loadTestsFromTestCase(BeaconRecoveryTests),
       unittest.defaultTestLoader.loadTestsFromTestCase(LinkTransportTests),
       unittest.defaultTestLoader.loadTestsFromTestCase(LegacyLinkTransportTests),
       unittest.defaultTestLoader.loadTestsFromModule(test_p20_dgw10)])
   result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
   report = stream.getvalue()
   if not result.wasSuccessful(): raise AssertionError(report)
   assert result.testsRun == 27, report
  """.trimIndent(),globals)
  File(context.getExternalFilesDir(null),"links-upgrade-test.txt").writeText(globals.callAttr("get","report").toString())
 }
}
