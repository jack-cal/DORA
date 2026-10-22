package org.sumuww.miner

import androidx.test.platform.app.InstrumentationRegistry
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.io.File
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class BoundaryRuntimeTest {
 @Test fun realCryptographyTcpRelayAndPersistedBoundary() {
  val context=InstrumentationRegistry.getInstrumentation().targetContext
  if(!Python.isStarted())Python.start(AndroidPlatform(context))
  val result=JSONObject(Python.getInstance().getModule("sumuww.boundary_selftest").callAttr("run_json").toString())
  File(context.getExternalFilesDir(null),"boundary-runtime-test.json").writeText(result.toString(2))
  assertEquals(9000,result.getInt("activation_height"))
  assertTrue(result.toString(),result.getBoolean("passed"))
 }
}
