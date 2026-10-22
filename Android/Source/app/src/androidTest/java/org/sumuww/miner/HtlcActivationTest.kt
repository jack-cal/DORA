package org.sumuww.miner

import androidx.test.platform.app.InstrumentationRegistry
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.io.File
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class HtlcActivationTest {
 @Test fun actualNativeSignaturesAndHeightGatedTransactions() {
  val context=InstrumentationRegistry.getInstrumentation().targetContext
  if(!Python.isStarted())Python.start(AndroidPlatform(context))
  val result=JSONObject(Python.getInstance().getModule("sumuww.htlc_selftest").callAttr("run_json").toString())
  File(context.getExternalFilesDir(null),"htlc-runtime-test.json").writeText(result.toString(2))
  assertEquals(9100,result.getInt("public_htlc_activation_height"))
  assertEquals(106,result.getInt("tested_boundary_height"))
  assertFalse(result.getBoolean("public_funds"))
  assertTrue(result.toString(),result.getBoolean("passed"))
 }
}
