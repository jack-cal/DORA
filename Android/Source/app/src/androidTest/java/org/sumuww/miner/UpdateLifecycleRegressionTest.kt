package org.sumuww.miner

import android.app.AlertDialog
import android.content.Intent
import androidx.test.platform.app.InstrumentationRegistry
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

/** Emulator-only: actual update HTTP and UI alongside a disposable mining node. */
class UpdateLifecycleRegressionTest {
 private fun ownedRun(body:(MainActivity,SumuwwUpdates,()->JSONObject)->Unit){
  val i=InstrumentationRegistry.getInstrumentation();val app=i.targetContext
  SumuwwConsent.accept(app);PrivacyRuntime.configure(app)
  if(android.os.Build.VERSION.SDK_INT>=33)i.uiAutomation.grantRuntimePermission(app.packageName,android.Manifest.permission.POST_NOTIFICATIONS)
  if(!Python.isStarted())Python.start(AndroidPlatform(app))
  PcRuntime.stopIfStarted()
  val globals=Python.getInstance().getModule("builtins").callAttr("dict")
  Python.getInstance().getModule("builtins").callAttr("exec","""
import tempfile
from pathlib import Path
import pc_runtime as bridge
from sumuww import keystore
from sumuww.app_service import AppService
owned=tempfile.TemporaryDirectory(prefix='owned-update-regression-')
keystore._publish_no_replace=bridge._publish_android
service=AppService(Path(owned.name)/'node',network='regtest',listen='127.0.0.1:0',peers=[],bootstrap=False,allow_lan=False,allow_internet=False)
service.start().result(timeout=30)
service.create_wallet(Path(owned.name)/'wallet.json','Owned-update-test-password').result(timeout=30)
bridge._service=service;bridge._runtime_state='running';bridge._session_opened()
  """.trimIndent(),globals)
  val oldLanguage=UiLanguage.code(app);UiLanguage.set(app,"ko")
  val prefs=app.getSharedPreferences("sumuww-ui",0)
  val charging=prefs.getBoolean("charging-only",false);prefs.edit().putBoolean("charging-only",false).commit()
  val a=i.startActivitySync(Intent(app,MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) as MainActivity
  fun status()=JSONObject(PcRuntime.call("status"))
  try{
   val end=android.os.SystemClock.elapsedRealtime()+10000
   while(!MainActivity::class.java.getDeclaredField("polling").apply{isAccessible=true}.getBoolean(a)){
    assertTrue(android.os.SystemClock.elapsedRealtime()<end);Thread.sleep(50)
   }
   i.runOnMainSync{
    MainActivity::class.java.getDeclaredField("page").apply{isAccessible=true}.setInt(a,14)
    MainActivity::class.java.getDeclaredMethod("render").apply{isAccessible=true}.invoke(a)
   }
   val delegate=MainActivity::class.java.getDeclaredField("updates\$delegate").apply{isAccessible=true}
   val controller=(delegate.get(a) as Lazy<*>).value as SumuwwUpdates
   PcRuntime.call("mine_blocks","10000")
   body(a,controller,::status)
  }finally{
   PcRuntime.call("stop_mining")
   i.runOnMainSync{a.finish()}
   app.stopService(Intent(app,PcNodeService::class.java));PcRuntime.stopIfStarted()
   Python.getInstance().getModule("builtins").callAttr("exec","bridge.stop();owned.cleanup()",globals)
   UiLanguage.set(app,oldLanguage);prefs.edit().putBoolean("charging-only",charging).commit()
  }
 }

 @Test fun actualHttpResultPreservesWalletAndMining(){ownedRun{a,controller,status->
  val i=InstrumentationRegistry.getInstrumentation()
  val before=status();val address=before.getJSONObject("wallet").getString("address")
  val field=SumuwwUpdates::class.java.getDeclaredField("dialog").apply{isAccessible=true}
  i.runOnMainSync{assertTrue(a.window.decorView.findViewWithTag<android.view.View>("sumuww-update-check").performClick())}
  var text="";val end=android.os.SystemClock.elapsedRealtime()+22000
  val offline=InstrumentationRegistry.getArguments().getString("expectFailure")=="true"
  while(android.os.SystemClock.elapsedRealtime()<end){
   i.runOnMainSync{text=(field.get(controller) as? AlertDialog)?.findViewById<android.widget.TextView>(android.R.id.message)?.text?.toString()?:""}
   if(text.contains("\nGitHub ")||text=="업데이트 정보를 가져올 수 없습니다.")break
   Thread.sleep(100)
  }
  if(offline)assertEquals("업데이트 정보를 가져올 수 없습니다.",text)else assertTrue(text,text.contains("\nGitHub "))
  i.runOnMainSync{val dialog=field.get(controller) as AlertDialog;assertTrue(dialog.getButton(AlertDialog.BUTTON_POSITIVE).isEnabled);controller.cancel()}
  val after=status();assertTrue(after.getJSONObject("node").getBoolean("running"))
  assertTrue(after.getJSONObject("mobile_batch").getBoolean("running"))
  assertEquals(address,after.getJSONObject("wallet").getString("address"))
  assertTrue(after.getJSONObject("node").getLong("height")>=before.getJSONObject("node").getLong("height"))
 }}

 @Test fun cancelAndPauseCannotResurrectDialogsOrStopMining(){ownedRun{a,controller,status->
  val i=InstrumentationRegistry.getInstrumentation()
  val field=SumuwwUpdates::class.java.getDeclaredField("dialog").apply{isAccessible=true}
  repeat(5){
   val start=android.os.SystemClock.elapsedRealtime()
   i.runOnMainSync{controller.check();controller.cancel()}
   assertTrue("Update cancellation blocked UI",android.os.SystemClock.elapsedRealtime()-start<2000)
  }
  i.runOnMainSync{controller.check();i.callActivityOnPause(a)}
  Thread.sleep(300)
  i.runOnMainSync{assertNull(field.get(controller));i.callActivityOnResume(a)}
  Thread.sleep(1500)
  i.runOnMainSync{assertNull("A cancelled reply reopened its dialog",field.get(controller))}
  assertTrue(status().getJSONObject("node").getBoolean("running"))
  assertTrue(status().getJSONObject("mobile_batch").getBoolean("running"))
 }}
}
