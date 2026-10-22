package org.sumuww.miner

import androidx.test.platform.app.InstrumentationRegistry
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.io.File
import org.junit.Test

class ActivationPrefixTest {
 @Test fun validLegacyPrefixSurvivesInvalidPost9000Suffix() {
  val context=InstrumentationRegistry.getInstrumentation().targetContext
  check(context.packageName.endsWith(".audit"))
  val seed=File(context.getExternalFilesDir(null),"height-8999.sqlite")
  check(seed.isFile) { "Independent regtest height-8999 fixture required" }
  if(!Python.isStarted())Python.start(AndroidPlatform(context))
  val builtins=Python.getInstance().getModule("builtins")
  val globals=builtins.callAttr("dict")
  globals.callAttr("__setitem__","test_cache",context.cacheDir.absolutePath)
  globals.callAttr("__setitem__","seed",seed.absolutePath)
  builtins.callAttr("exec","""
   import io, os, sys, tempfile, unittest, pc_tests
   tempfile.tempdir=test_cache
   sys.modules['tests']=pc_tests
   os.environ['SUMUWW_ACTIVATION_SEED']=seed
   try:
       from pc_tests.test_activation_prefix import ActivationPrefixTests
       stream=io.StringIO()
       result=unittest.TextTestRunner(stream=stream,verbosity=2).run(
           unittest.defaultTestLoader.loadTestsFromTestCase(ActivationPrefixTests))
       report=stream.getvalue()
       if not result.wasSuccessful():raise AssertionError(report)
       assert result.testsRun==2,report
   finally:os.environ.pop('SUMUWW_ACTIVATION_SEED',None)
  """.trimIndent(),globals)
  File(context.getExternalFilesDir(null),"activation-9000-android.txt").writeText(globals.callAttr("get","report").toString())
 }
}
