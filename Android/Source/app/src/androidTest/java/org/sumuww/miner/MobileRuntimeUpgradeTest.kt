package org.sumuww.miner

import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import java.security.MessageDigest
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.json.JSONObject
import org.junit.Test

/** Exercise the actual Android service adapter with an isolated throwaway wallet. */
class MobileRuntimeUpgradeTest {
 @Test fun networkChangesKeepDiscoveryAndSynchronizationWorking() {
  val context=InstrumentationRegistry.getInstrumentation().targetContext
  check(context.packageName.endsWith(".audit"))
  if(!Python.isStarted())Python.start(AndroidPlatform(context))
  val builtins=Python.getInstance().getModule("builtins")
  val globals=builtins.callAttr("dict")
  globals.callAttr("__setitem__","test_cache",context.cacheDir.absolutePath)
  builtins.callAttr("exec","""
   import io, sys, tempfile, unittest, pc_tests
   tempfile.tempdir=test_cache
   sys.modules['tests']=pc_tests
   from pc_tests.test_mobile_dht_recovery import MobileDhtRecoveryTests
   stream=io.StringIO()
   result=unittest.TextTestRunner(stream=stream,verbosity=2).run(
       unittest.defaultTestLoader.loadTestsFromTestCase(MobileDhtRecoveryTests))
   report=stream.getvalue()
   if not result.wasSuccessful(): raise AssertionError(report)
   assert result.testsRun==8,report
  """.trimIndent(),globals)
  File(context.getExternalFilesDir(null),"mobile-network-tests.txt").writeText(globals.callAttr("get","report").toString())
 }
 @Test fun actualRuntimeStartsAndReopensExistingEncryptedWallet() {
  val context=InstrumentationRegistry.getInstrumentation().targetContext
  check(context.packageName.endsWith(".audit")) { "Isolated audit package required" }
  SumuwwConsent.accept(context)
  val report=JSONObject()
  try {
   val started=JSONObject(PcRuntime.start(context))
   check(started.getString("runtime_state")=="running")
   check(started.getJSONObject("node").getBoolean("running"))
   report.put("android_runtime_started",true)
   val wallet=File(context.filesDir,"sumuww/wallet.json")
   check(!wallet.exists()) { "Fresh isolated test package required" }
   val password="isolated-runtime-test-password"
   PcRuntime.call("create_wallet",password)
   val opened=JSONObject(PcRuntime.call("status")).getJSONObject("wallet")
   val address=opened.getString("address")
   val encrypted=wallet.readBytes()
   PcRuntime.call("lock_wallet")
   PcRuntime.call("open_wallet",password)
   val reopened=JSONObject(PcRuntime.call("status")).getJSONObject("wallet")
   check(reopened.getString("address")==address)
   check(reopened.getBoolean("unlocked"))
   check(encrypted.contentEquals(wallet.readBytes()))
   report.put("existing_wallet_reopened",true)
   report.put("wallet_bytes_unchanged",true)
   report.put("wallet_sha256",MessageDigest.getInstance("SHA-256").digest(encrypted).joinToString(""){"%02x".format(it)})
   report.put("status","passed")
   File(context.getExternalFilesDir(null),"mobile-runtime-test.json").writeText(report.toString(2))
  } finally { PcRuntime.stopIfStarted() }
 }
}
