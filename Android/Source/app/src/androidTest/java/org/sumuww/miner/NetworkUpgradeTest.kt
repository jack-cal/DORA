package org.sumuww.miner

import androidx.test.platform.app.InstrumentationRegistry
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.io.File
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class NetworkUpgradeTest {
 @Test fun sharedConsensusAndPrivacyTransport() {
  val context=InstrumentationRegistry.getInstrumentation().targetContext
  if(!Python.isStarted())Python.start(AndroidPlatform(context))
  val vectors=InstrumentationRegistry.getInstrumentation().context.assets.open("asert-vectors.json").bufferedReader().use{it.readText()}
  val result=JSONObject(Python.getInstance().getModule("network_upgrade_selftest").callAttr("run",vectors).toString())
  File(context.getExternalFilesDir(null),"network-upgrade-test.json").writeText(result.toString(2))
  assertTrue(result.toString(),result.getBoolean("passed"))
 }
}
