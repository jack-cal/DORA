package org.sumuww.miner
import androidx.test.platform.app.InstrumentationRegistry
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.io.File
import org.junit.Test

class InternetProbeTest {
 @Test fun ownedEndpointProbe() {
  val app=InstrumentationRegistry.getInstrumentation().targetContext
  if(!Python.isStarted())Python.start(AndroidPlatform(app))
  val folder=app.getExternalFilesDir(null)!!
  val globals=Python.getInstance().getModule("builtins").callAttr("dict")
  Python.getInstance().getModule("builtins").callAttr("exec",File(folder,"owned-internet-probe.py").readText(),globals)
  File(folder,"owned-internet-probe-report.json").writeText(globals.callAttr("get","report").toString())
 }
}
