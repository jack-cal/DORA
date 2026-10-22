package org.sumuww.miner
import androidx.test.platform.app.InstrumentationRegistry
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.io.File
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
class WanFaultTest {
 @Test fun virtualWanFaults(){
  val app=InstrumentationRegistry.getInstrumentation().targetContext
  if(!Python.isStarted())Python.start(AndroidPlatform(app))
  val globals=Python.getInstance().getModule("builtins").callAttr("dict")
  val folder=app.getExternalFilesDir(null)!!
  globals.callAttr("__setitem__","config_path",File(folder,"owned-wan-config.json").absolutePath)
  Python.getInstance().getModule("builtins").callAttr("exec",File(folder,"owned-wan-fixture.py").readText(),globals)
  val report=JSONObject(globals.callAttr("get","report").toString())
  File(folder,"owned-wan-report.json").writeText(report.toString(2))
  assertTrue(report.toString(),report.getBoolean("passed"))
  assertEquals(9,report.getJSONArray("cases").length())
 }
}
