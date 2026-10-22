package org.sumuww.miner
import androidx.test.platform.app.InstrumentationRegistry
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.io.File
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class OperatorShutdownTest {
 @Test fun installedAndroidOperatorLoss() {
  val app=InstrumentationRegistry.getInstrumentation().targetContext
  val phase=InstrumentationRegistry.getArguments().getString("phase") ?: "initial"
  val folder=app.getExternalFilesDir(null)!!
  if(!Python.isStarted())Python.start(AndroidPlatform(app))
  val globals=Python.getInstance().getModule("builtins").callAttr("dict")
  globals.callAttr("__setitem__","phase",phase)
  globals.callAttr("__setitem__","fixture_root",File(folder,"owned-operator-loss").absolutePath)
  Python.getInstance().getModule("builtins").callAttr("exec",File(folder,"owned-operator-loss.py").readText(),globals)
  val report=JSONObject(globals.callAttr("get","report").toString())
  report.put("android_pid",android.os.Process.myPid())
  report.put("app_version",app.packageManager.getPackageInfo(app.packageName,0).versionName)
  File(folder,"operator-loss-$phase.json").writeText(report.toString(2))
  assertTrue(report.toString(),report.getBoolean("passed"))
 }
}
