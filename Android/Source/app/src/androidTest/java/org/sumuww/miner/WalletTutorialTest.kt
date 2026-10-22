package org.sumuww.miner
import android.app.AlertDialog
import android.content.Intent
import android.view.View
import android.view.ViewGroup
import android.view.WindowManager
import android.widget.EditText
import android.view.accessibility.AccessibilityNodeInfo
import androidx.test.platform.app.InstrumentationRegistry
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import java.io.File

/** Video fixture only: isolated zero-fund demo wallet, never a production wallet. */
class WalletTutorialTest {
 @Test fun recordWalletCreation() {
  val inst=InstrumentationRegistry.getInstrumentation();val context=inst.targetContext
  val automation=inst.uiAutomation
  automation.serviceInfo=automation.serviceInfo.apply{flags=flags or android.accessibilityservice.AccessibilityServiceInfo.FLAG_RETRIEVE_INTERACTIVE_WINDOWS}
  SumuwwConsent.accept(context);UiLanguage.set(context,"ko")
  context.getSharedPreferences("sumuww-ui",0).edit().putString("theme","light").putBoolean("tour-completed",true).commit()
  if(!Python.isStarted())Python.start(AndroidPlatform(context))
  PcRuntime.stopIfStarted()
  val globals=Python.getInstance().getModule("builtins").callAttr("dict")
  Python.getInstance().getModule("builtins").callAttr("exec","""
   import tempfile
   from pathlib import Path
   import pc_runtime as bridge
   from sumuww.app_service import AppService
   from sumuww import keystore
   keystore._publish_no_replace=bridge._publish_android
   owned=tempfile.TemporaryDirectory(prefix='owned-video-wallet-')
   service=AppService(Path(owned.name),network='regtest',peers=[],bootstrap=False,allow_lan=False,allow_internet=False)
   service.start().result(30)
   bridge._service=service;bridge._runtime_state='running';bridge._session_opened()
  """.trimIndent(),globals)
  val activity=inst.startActivitySync(Intent(context,MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) as MainActivity
  val dispatch=MainActivity::class.java.getDeclaredMethod("action",String::class.java,String::class.java,String::class.java).apply{isAccessible=true}
  val folder=context.getExternalFilesDir(null)!!
  fun page(p:Int){inst.runOnMainSync{dispatch.invoke(activity,"page",p.toString(),"")};inst.waitForIdleSync()}
  fun nodes(n:AccessibilityNodeInfo):List<AccessibilityNodeInfo> = listOf(n)+(0 until n.childCount).flatMap{n.getChild(it)?.let{c->nodes(c)}?:emptyList()}
  fun click(text:String){
   var selected:AccessibilityNodeInfo?=null
   val deadline=System.currentTimeMillis()+6000
   while(selected==null && System.currentTimeMillis()<deadline){
    val root=automation.rootInActiveWindow
    if(root!=null)selected=nodes(root).firstOrNull{it.text?.toString()==text||it.contentDescription?.toString()==text}
    if(selected==null)Thread.sleep(100)
   }
   val node=selected?:error("Missing tutorial control: $text")
   var target=node
   while(!target.isClickable&&target.parent!=null)target=target.parent
   assertTrue(target.performAction(AccessibilityNodeInfo.ACTION_CLICK));inst.waitForIdleSync()
  }
  fun password(){
   val field=MainActivity::class.java.getDeclaredField("sensitive").apply{isAccessible=true}
   var dialog:AlertDialog?=null
   inst.runOnMainSync{
    @Suppress("UNCHECKED_CAST")
    val dialogs=field.get(activity) as Collection<AlertDialog>
    dialog=dialogs.last()
    // Only this empty test wallet's masked password dialog is recordable.
    dialog!!.window!!.clearFlags(WindowManager.LayoutParams.FLAG_SECURE)
   }
   Thread.sleep(1200)
   fun edit(v:View):EditText? {if(v is EditText)return v;if(v is ViewGroup)for(i in 0 until v.childCount)edit(v.getChildAt(i))?.let{return it};return null}
   val pass="DemoWallet-2026!"
   for(i in 1..pass.length){inst.runOnMainSync{edit(dialog!!.window!!.decorView)!!.setText(pass.take(i))};Thread.sleep(65)}
   Thread.sleep(1800)
   inst.runOnMainSync{dialog!!.getButton(AlertDialog.BUTTON_POSITIVE).performClick()};inst.waitForIdleSync()
  }
  try {
   Thread.sleep(1800);page(0)
   File(folder,"tutorial-ready").writeText("ready")
   // Host starts screen recording after this marker.
   Thread.sleep(4000)
   page(4);Thread.sleep(2000)
   click("지갑 관리");Thread.sleep(2200)
   click("지갑 열기 / 생성 / 복구");Thread.sleep(2500)
   click("새 지갑");password();password()
   val deadline=System.currentTimeMillis()+15000
   while(JSONObject(PcRuntime.call("status")).optJSONObject("wallet")?.optBoolean("unlocked")!=true){
    assertTrue(System.currentTimeMillis()<deadline);Thread.sleep(100)
   }
   Thread.sleep(1800);page(10);Thread.sleep(4000)
   File(folder,"tutorial-done").writeText("PASS: created and unlocked isolated zero-fund wallet via actual UI")
  }finally{
   inst.runOnMainSync{activity.finish()};context.stopService(Intent(context,PcNodeService::class.java));PcRuntime.stopIfStarted()
   Python.getInstance().getModule("builtins").callAttr("exec","bridge.stop();owned.cleanup()",globals)
  }
 }
}
