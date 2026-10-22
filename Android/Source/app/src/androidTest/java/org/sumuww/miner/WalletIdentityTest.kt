package org.sumuww.miner

import androidx.test.platform.app.InstrumentationRegistry
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.junit.Assert.*
import org.junit.Test

class WalletIdentityTest {
 @Test fun newApplicationAndWalletIdentityKeepSameChainPayments() {
  val app=InstrumentationRegistry.getInstrumentation().targetContext
  assertEquals("org.sumuww.miner",app.packageName.removeSuffix(".audit"))
  if(!Python.isStarted())Python.start(AndroidPlatform(app))
  val globals=Python.getInstance().getModule("builtins").callAttr("dict")
  globals.callAttr("__setitem__","test_cache",app.cacheDir.absolutePath)
  Python.getInstance().getModule("builtins").callAttr("exec","""
   import io, json, tempfile, unittest
   from java import jclass
   import pc_runtime
   from sumuww import keystore
   keystore._publish_no_replace=pc_runtime._publish_android
   tempfile.tempdir=test_cache
   from pc_tests.test_wallet_identity import WalletIdentityTests
   stream=io.StringIO()
   result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(WalletIdentityTests))
   if not result.wasSuccessful():raise AssertionError(stream.getvalue())
   # Ensure the reflection adapter follows the new Java package as well.
   interfaces=json.loads(str(jclass('org.sumuww.miner.AndroidInterfaces').read()))
   assert isinstance(interfaces,list)
  """.trimIndent(),globals)
 }
}
