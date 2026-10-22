package org.sumuww.miner

import androidx.test.platform.app.InstrumentationRegistry
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.junit.Test

class IncomingAdmissionTest {
 @Test fun fullListenerKeepsAnchorsAndAdmitsBoundedNewcomers() {
  val context = InstrumentationRegistry.getInstrumentation().targetContext
  if (!Python.isStarted()) Python.start(AndroidPlatform(context))
  val globals = Python.getInstance().getModule("builtins").callAttr("dict")
  globals.callAttr("__setitem__", "test_cache", context.cacheDir.absolutePath)
  Python.getInstance().getModule("builtins").callAttr("exec", """
   import io, tempfile, unittest
   tempfile.tempdir = test_cache
   from pc_tests import test_incoming_admission
   suite = unittest.defaultTestLoader.loadTestsFromModule(test_incoming_admission)
   stream = io.StringIO()
   result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
   if not result.wasSuccessful(): raise AssertionError(stream.getvalue())
   assert result.testsRun == 12
  """.trimIndent(), globals)
 }
}
