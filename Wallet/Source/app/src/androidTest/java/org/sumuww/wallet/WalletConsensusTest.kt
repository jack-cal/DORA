package org.sumuww.wallet

import androidx.test.platform.app.InstrumentationRegistry
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.io.File
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class WalletConsensusTest {
 @Test fun dgwCompatibility() {
  val instrumentation=InstrumentationRegistry.getInstrumentation()
  val app=instrumentation.targetContext
  if(!Python.isStarted())Python.start(AndroidPlatform(app))
  val data=instrumentation.context.assets.open("asert-vectors.json").bufferedReader().use{it.readText()}
  val globals=Python.getInstance().getModule("builtins").callAttr("dict")
  globals.callAttr("__setitem__","vector_json",data)
  val dgwData=instrumentation.context.assets.open("dgw-official.json").bufferedReader().use{it.readText()}
  globals.callAttr("__setitem__","dgw_json",dgwData)
  val code="""
import json,io,unittest
from sumuww.asert import next_bits
from sumuww.profiles import DORA
from sumuww.primitives import valid_target
cases=json.loads(vector_json)
limit=valid_target(0x1d00ffff,(1<<256)-1)
passed=all(next_bits(a,t,h,limit)==expected for a,t,h,expected in cases)
from sumuww.dgw import next_bits as dgw_bits
dgw=json.loads(dgw_json)
dgw_passed=dgw_bits(list(reversed(dgw['history_oldest_first'])),(1<<256)-1,spacing=dgw['spacing'])==dgw['expected_bits']
stream=io.StringIO()
result=unittest.TextTestRunner(stream=stream).run(unittest.defaultTestLoader.loadTestsFromName('pc_tests.test_dgw_upgrade'))
report=json.dumps({'passed':passed and dgw_passed and result.wasSuccessful() and DORA.dgw_activation_height==8064 and DORA.asert_activation_height is None,'asert_vectors':len(cases),'dgw_tests':result.testsRun,'dgw_official_vector_passed':dgw_passed,'activation_height':DORA.dgw_activation_height,'algorithm':'DGW v3','output':stream.getvalue()})
""".trimIndent()
  Python.getInstance().getModule("builtins").callAttr("exec",code,globals)
  val report=JSONObject(globals.callAttr("get","report").toString())
  File(app.getExternalFilesDir(null),"consensus-upgrade-test.json").writeText(report.toString(2))
  assertTrue(report.toString(),report.getBoolean("passed"))
 }
}
