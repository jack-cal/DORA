package org.sumuww.miner
import androidx.test.platform.app.InstrumentationRegistry
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import android.app.NotificationManager
import android.content.Intent
import android.view.View
import android.view.ViewGroup
import java.io.File
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
class InteractionLifecycleTest {
 @Test fun contextualBackNavigation(){
  val inst=InstrumentationRegistry.getInstrumentation();val context=inst.targetContext
  SumuwwConsent.accept(context)
  val activity=inst.startActivitySync(Intent(context,MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) as MainActivity
  val action=MainActivity::class.java.getDeclaredMethod("action",String::class.java,String::class.java,String::class.java).apply{isAccessible=true}
  val page=MainActivity::class.java.getDeclaredField("page").apply{isAccessible=true}
  val pairs=listOf(0 to 5,0 to 6,2 to 5,4 to 8,4 to 10,4 to 11,4 to 12,4 to 13,4 to 14,1 to 9,2 to 9,4 to 9)
  try{
   for((from,to) in pairs){
    inst.runOnMainSync{action.invoke(activity,"page",from.toString(),"");action.invoke(activity,"page",to.toString(),"");activity.onBackPressed()}
    assertEquals("Back from $to must return to originating $from",from,page.getInt(activity))
   }
   val saved=android.os.Bundle()
   inst.runOnMainSync{action.invoke(activity,"page","4","");action.invoke(activity,"page","9","");action.invoke(activity,"page","8","");MainActivity::class.java.getDeclaredMethod("onSaveInstanceState",android.os.Bundle::class.java).apply{isAccessible=true}.invoke(activity,saved);activity.onBackPressed()}
   assertArrayEquals("Navigation origin is lost on configuration save",intArrayOf(4,9),saved.getIntArray("backPages"))
   assertEquals(9,page.getInt(activity))
   inst.runOnMainSync{activity.onBackPressed()};assertEquals(4,page.getInt(activity))
   File(context.getExternalFilesDir(null),"interaction-navigation.json").writeText(JSONObject().put("passed",true).put("origin_return_cases",pairs.size).put("nested_settings_return",true).toString(2))
  }finally{inst.runOnMainSync{activity.finish()}}
 }
 @Test fun miningNavigationStopBackgroundAndNotificationExit(){
  val inst=InstrumentationRegistry.getInstrumentation();val context=inst.targetContext
  SumuwwConsent.accept(context)
  // A system permission dialog pauses the UI and its status poller.
  if(android.os.Build.VERSION.SDK_INT>=33)inst.uiAutomation.grantRuntimePermission(context.packageName,android.Manifest.permission.POST_NOTIFICATIONS)
  if(!Python.isStarted())Python.start(AndroidPlatform(context))
  PcRuntime.stopIfStarted()
  val globals=Python.getInstance().getModule("builtins").callAttr("dict")
  Python.getInstance().getModule("builtins").callAttr("exec","""
   import tempfile,json
   from pathlib import Path
   import pc_runtime as bridge
   from sumuww.app_service import AppService
   from sumuww import keystore
   keystore._publish_no_replace=bridge._publish_android
   owned=tempfile.TemporaryDirectory(prefix='owned-ui-lifecycle-')
   service=AppService(Path(owned.name)/'node',network='regtest',peers=[],bootstrap=False,allow_lan=False,allow_internet=False)
   service.start().result(timeout=30)
   service.create_wallet(Path(owned.name)/'wallet.json','Owned-ui-test-password').result(timeout=30)
   bridge._service=service;bridge._runtime_state='running';bridge._session_opened()
  """.trimIndent(),globals)
  val prefs=context.getSharedPreferences("sumuww-ui",0);val old=prefs.getString("mining-target",null)
  val oldCharging=prefs.getBoolean("charging-only",false)
  val oldLimit=if(prefs.contains("battery-limit"))prefs.getInt("battery-limit",15)else null
  val oldLanguage=UiLanguage.code(context)
  UiLanguage.set(context,InstrumentationRegistry.getArguments().getString("auditLocale","ko"))
  prefs.edit().putString("mining-target","10000").putBoolean("charging-only",false).commit()
  val activity=inst.startActivitySync(Intent(context,MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) as MainActivity
  val dispatch=MainActivity::class.java.getDeclaredMethod("action",String::class.java,String::class.java,String::class.java).apply{isAccessible=true}
  fun status()=JSONObject(PcRuntime.call("status"))
  fun waitUntil(label:String,seconds:Int=20,predicate:()->Boolean){
   val end=android.os.SystemClock.elapsedRealtime()+seconds*1000
   while(!predicate()){
    if(android.os.SystemClock.elapsedRealtime()>=end){
     val captions=org.json.JSONArray()
     inst.runOnMainSync{
      fun inspect(view:View){
       if(view is android.widget.TextView||view.isClickable)captions.put(JSONObject().put("type",view.javaClass.simpleName).put("text",if(view is android.widget.TextView)view.text.toString() else "").put("description",view.contentDescription?.toString()).put("visible",view.visibility).put("clickable",view.isClickable))
       if(view is ViewGroup)for(i in 0 until view.childCount)inspect(view.getChildAt(i))
      };inspect(activity.window.decorView)
     }
     val current=status()
     File(context.getExternalFilesDir(null),"battery-restart-failure.json").writeText(JSONObject().put("label",label).put("page",pageOf(activity)).put("batch",current.optJSONObject("mobile_batch")).put("mining",current.optJSONObject("mining")).put("security",current.optJSONObject("security")).put("protection",MiningProtection.read(context).reason).put("views",captions).toString(2))
    }
    assertTrue(label,android.os.SystemClock.elapsedRealtime()<end);Thread.sleep(100)
   }
  }
  fun button(view:View,caption:String):View?{
   if(view.isClickable&&view.contentDescription?.toString()==UiLanguage.text(context,caption))return view
   if(view is ViewGroup)for(i in 0 until view.childCount)button(view.getChildAt(i),caption)?.let{return it}
   return null
  }
  fun click(caption:String){
   waitUntil("Missing button: $caption"){
    var found=false;inst.runOnMainSync{found=button(activity.window.decorView,caption)!=null};found
   }
   inst.runOnMainSync{assertTrue(button(activity.window.decorView,caption)!!.performClick())}
  }
  try{
   waitUntil("Activity must be resumed before testing foreground controls"){
    MainActivity::class.java.getDeclaredField("polling").apply{isAccessible=true}.getBoolean(activity)
   }
   inst.runOnMainSync{dispatch.invoke(activity,"page","1","")}
   click("채굴 시작")
   waitUntil("Mining did not start"){status().getJSONObject("mobile_batch").getBoolean("running")}
   for(route in listOf(2,3,4,1)){
    inst.runOnMainSync{dispatch.invoke(activity,"page",route.toString(),"")};inst.waitForIdleSync()
    assertTrue("Navigation interrupted mining",status().getJSONObject("mobile_batch").getBoolean("running"))
   }
   click("채굴 중지")
   waitUntil("Stop did not settle"){!status().getJSONObject("mobile_batch").getBoolean("running")}
   val stopped=status().getJSONObject("node").getLong("height")
   Thread.sleep(1000);assertEquals("Mining restarted after Stop",stopped,status().getJSONObject("node").getLong("height"))
   click("채굴 시작")
   waitUntil("Explicit restart failed"){status().getJSONObject("mobile_batch").getBoolean("running")}
   fun battery(level:Int){inst.uiAutomation.executeShellCommand("dumpsys battery set level "+level).use{android.os.ParcelFileDescriptor.AutoCloseInputStream(it).readBytes()}}
   prefs.edit().putInt("battery-limit",15).commit()
   battery(17);Thread.sleep(1000)
   assertTrue("17 percent must run with a 15 percent threshold",status().getJSONObject("mobile_batch").getBoolean("running"))
   repeat(3){cycle->
    battery(15)
    waitUntil("Battery boundary failed to stop actual mining, cycle $cycle"){!status().getJSONObject("mobile_batch").getBoolean("running")}
    waitUntil("Protection stop reason missing"){status().getJSONObject("mobile_batch").optString("protection_reason").isNotBlank()}
    battery(17)
    Thread.sleep(500)
    assertFalse("Battery recovery must not silently restart mining",status().getJSONObject("mobile_batch").getBoolean("running"))
    click("채굴 시작")
    waitUntil("Explicit restart after protection failed, cycle $cycle"){status().getJSONObject("mobile_batch").getBoolean("running")}
    assertTrue("Restart retained stale protection reason",status().getJSONObject("mobile_batch").optString("protection_reason").let{it.isBlank()||it=="null"})
   }
   inst.runOnMainSync{activity.finish()}
   Thread.sleep(1000)
   assertTrue("Closing UI unexpectedly killed background mining",status().getJSONObject("mobile_batch").getBoolean("running"))
   val manager=context.getSystemService(NotificationManager::class.java)
   waitUntil("Node notification unavailable"){manager.activeNotifications.any{it.id==42&&it.notification.actions?.isNotEmpty()==true}}
   manager.activeNotifications.first{it.id==42}.notification.actions[0].actionIntent.send()
   waitUntil("Notification Stop did not stop node",40){try{status().optString("runtime_state")=="stopped"}catch(e:com.chaquo.python.PyException){if(e.message?.contains("Service is stopping")==true)false else throw e}}
   Thread.sleep(1500)
   assertEquals("Node restarted after notification Stop","stopped",status().optString("runtime_state"))
   File(context.getExternalFilesDir(null),"interaction-lifecycle.json").writeText(JSONObject().put("passed",true).put("checks",10).put("battery_recovery_cycles",3).put("locale",UiLanguage.code(context)).put("actual_start_stop_buttons",true).put("navigation_preserves_batch",true).put("stop_is_terminal_until_explicit_restart",true).put("closing_ui_preserves_background_work",true).put("notification_stop_shuts_down_node",true).toString(2))
  }finally{
   inst.uiAutomation.executeShellCommand("dumpsys battery reset").close()
   inst.runOnMainSync{activity.finish()};context.stopService(Intent(context,PcNodeService::class.java));PcRuntime.stopIfStarted()
   Python.getInstance().getModule("builtins").callAttr("exec","bridge.stop(); owned.cleanup()",globals)
   UiLanguage.set(context,oldLanguage)
   prefs.edit().putBoolean("charging-only",oldCharging).apply{
    if(old==null)remove("mining-target")else putString("mining-target",old)
    if(oldLimit==null)remove("battery-limit")else putInt("battery-limit",oldLimit)
   }.commit()
  }
 }
 private fun pageOf(activity:MainActivity)=MainActivity::class.java.getDeclaredField("page").apply{isAccessible=true}.getInt(activity)
}
