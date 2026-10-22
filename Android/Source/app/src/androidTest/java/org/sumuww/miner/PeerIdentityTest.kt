package org.sumuww.miner

import androidx.test.platform.app.InstrumentationRegistry
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.junit.Test

class PeerIdentityTest {
 @Test fun duplicateRoutesAndReconnectsKeepOnePeerIdentity() {
  val app=InstrumentationRegistry.getInstrumentation().targetContext
  if(!Python.isStarted())Python.start(AndroidPlatform(app))
  val globals=Python.getInstance().getModule("builtins").callAttr("dict")
  globals.callAttr("__setitem__","test_cache",app.cacheDir.absolutePath)
  globals.callAttr("__setitem__","repeat_count",(InstrumentationRegistry.getArguments().getString("repeat")?:"1").toInt())
  globals.callAttr("__setitem__","focus_case",InstrumentationRegistry.getArguments().getString("focusCase")?:"")
  val fixture=java.io.File(app.getExternalFilesDir(null),"peer-unique-fixture.py")
  globals.callAttr("__setitem__","fixture_source",if(InstrumentationRegistry.getArguments().getString("ownedFixture")=="true")fixture.readText()else "")
  Python.getInstance().getModule("builtins").callAttr("exec","""
   import io, tempfile, unittest, json
   tempfile.tempdir=test_cache
   from pc_tests import test_peer_identity_repair, test_peer_unique_v46
   if fixture_source:exec(compile(fixture_source,'owned-peer-unique-fixture.py','exec'),test_peer_unique_v46.__dict__)
   diagnostics=[]
   original_wait=test_peer_unique_v46.UniquePeerTests.wait
   async def traced_wait(self,predicate):
       try: return await original_wait(self,predicate)
       except AssertionError:
           diagnostics.append([{'info':node.info(),'sync':node.synchronization_info(),
               'known':list(node._addresses.known()),
               'configured':[{ 'target':str(k),'ready':v.is_set()} for k,v in node._configured.items()],
               'tasks':[{ 'name':t.get_name(),'done':t.done(), 'stack':[str(f.f_code.co_name)+':'+str(f.f_lineno) for f in t.get_stack()]} for t in node._tasks]}
               for node in self.nodes])
           raise
   test_peer_unique_v46.UniquePeerTests.wait=traced_wait
   suite=unittest.TestSuite()
   for _ in range(repeat_count):
       if focus_case:suite.addTests(unittest.defaultTestLoader.loadTestsFromName('pc_tests.test_peer_unique_v46.UniquePeerTests.'+focus_case))
       else:
           for module in (test_peer_identity_repair,test_peer_unique_v46):suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
   stream=io.StringIO()
   result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
   test_peer_unique_v46.UniquePeerTests.wait=original_wait
   report=json.dumps({'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'passed':result.wasSuccessful(),'output':stream.getvalue(),'diagnostics':diagnostics})
   assert result.testsRun==(1 if focus_case else 12)*repeat_count
  """.trimIndent(),globals)
  val report=org.json.JSONObject(globals.callAttr("get","report").toString())
  java.io.File(app.getExternalFilesDir(null),"peer-identity-regression.json").writeText(report.toString(2))
  org.junit.Assert.assertTrue(report.toString(),report.getBoolean("passed"))
 }
}
