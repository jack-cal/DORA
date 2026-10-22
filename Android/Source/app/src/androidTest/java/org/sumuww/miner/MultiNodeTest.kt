package org.sumuww.miner
import androidx.test.platform.app.InstrumentationRegistry
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.io.File
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class MultiNodeTest {
 @Test fun installedAndroidMultiNodeTcp(){
  val app=InstrumentationRegistry.getInstrumentation().targetContext
  if(!Python.isStarted())Python.start(AndroidPlatform(app))
  val globals=Python.getInstance().getModule("builtins").callAttr("dict")
  val folder=app.getExternalFilesDir(null)!!
  val source=File(folder,"owned-multi-node-fixture.py").readText()
  Python.getInstance().getModule("builtins").callAttr("exec",source,globals)
  val report=JSONObject(globals.callAttr("get","report").toString())
  File(folder,"owned-multi-node-report.json").writeText(report.toString(2))
  assertTrue(report.toString(),report.getBoolean("passed"))
  assertEquals(11,report.getJSONArray("cases").length())
 }
}
