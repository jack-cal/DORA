package org.sumuww.miner

import androidx.test.platform.app.InstrumentationRegistry
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import com.chaquo.python.PyObject
import org.junit.BeforeClass
import org.junit.AfterClass
import org.junit.runner.RunWith
import org.junit.runners.Suite

/** Every default app launch in this suite uses disposable test-owned data. */
@RunWith(Suite::class)
@Suite.SuiteClasses(LanguageCoverageTest::class, LocaleActionTest::class,
 InteractionLifecycleTest::class, ArabicReadabilityTest::class,
 VerticalMongolianTest::class, PrivacyHelpTest::class, NetworkUpgradeTest::class,
 WalletIdentityTest::class, StatusProtectionTest::class)
class UiRecheckSuite {
 companion object {
  private lateinit var globals:PyObject
  @BeforeClass @JvmStatic fun ownedAppProfile(){
   val context=InstrumentationRegistry.getInstrumentation().targetContext
   PrivacyRuntime.configure(context)
   if(!Python.isStarted())Python.start(AndroidPlatform(context))
   globals=Python.getInstance().getModule("builtins").callAttr("dict")
   Python.getInstance().getModule("builtins").callAttr("exec","""
import tempfile
from pathlib import Path
import pc_runtime as bridge
bridge.stop()
owned_app=tempfile.TemporaryDirectory(prefix='owned-ui-recheck-')
original_factory=bridge.AppService
def owned_factory(directory,**options):
    options.update(listen='127.0.0.1:0',peers=[],bootstrap=False,allow_internet=False,allow_lan=False)
    return original_factory(Path(owned_app.name)/'node',**options)
bridge.AppService=owned_factory
""".trimIndent(),globals)
  }
  @AfterClass @JvmStatic fun closeOwnedApp(){
   Python.getInstance().getModule("builtins").callAttr("exec","bridge.stop(); bridge.AppService=original_factory; owned_app.cleanup()",globals)
  }
 }
}
