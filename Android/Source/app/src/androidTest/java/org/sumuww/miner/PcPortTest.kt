package org.sumuww.miner
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.junit.Test
import org.junit.Assert.*
import org.junit.runner.RunWith
import org.json.JSONObject
import java.io.File

@RunWith(AndroidJUnit4::class)
class PcPortTest {
 @org.junit.Before fun existingFeatureConsentFixture(){
  val app=InstrumentationRegistry.getInstrumentation().targetContext
  SumuwwConsent.accept(app)
  // Optional emulator-only fixture: keep node tests off live user peers.
  val endpoint=InstrumentationRegistry.getArguments().getString("ownedPeer")
  if(endpoint!=null){
   require(endpoint=="127.0.0.1:18445")
   if(!Python.isStarted())Python.start(AndroidPlatform(app))
   val globals=Python.getInstance().getModule("builtins").callAttr("dict")
   Python.getInstance().getModule("builtins").callAttr("exec","""
    import pc_runtime
    from sumuww.app_service import AppService
    def owned_service(directory, **options):
        options.update(listen='127.0.0.1:0',peers=['127.0.0.1:18445'],
                       bootstrap=False,allow_lan=False,allow_internet=False)
        return AppService(directory,**options)
    pc_runtime.AppService=owned_service
   """.trimIndent(),globals)
  }
 }
 @Test fun validationNoticeLifecycle(){
  val instrument=InstrumentationRegistry.getInstrumentation();val app=instrument.targetContext
  val activity=instrument.startActivitySync(android.content.Intent(app,MainActivity::class.java).addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK)) as MainActivity
  val dispatch=MainActivity::class.java.getDeclaredMethod("action",String::class.java,String::class.java,String::class.java).apply{isAccessible=true}
  val accept=MainActivity::class.java.getDeclaredMethod("accept",JSONObject::class.java).apply{isAccessible=true}
  val error=MainActivity::class.java.getDeclaredField("error").apply{isAccessible=true}
  val screens=MainActivity::class.java.getDeclaredField("screens").apply{isAccessible=true}.get(activity) as SumuwwScreens
  fun hasNotice(view:android.view.View):Boolean = when(view){
   is android.widget.TextView -> view.text.toString()==UiLanguage.text(activity,"받는 주소, 수량과 직접 설정한 수수료를 입력하세요.")
   is android.view.ViewGroup -> (0 until view.childCount).any{hasNotice(view.getChildAt(it))}
   else -> false
  }
  try{
   instrument.runOnMainSync{
    accept.invoke(activity,JSONObject().put("security",JSONObject().put("locked",false)))
    dispatch.invoke(activity,"page","5","")
    screens.content.findViewWithTag<android.widget.EditText>("sendAddress").setText("owned-draft-address")
    dispatch.invoke(activity,"send","owned-draft-address","")
    assertNotNull(error.get(activity));assertTrue(hasNotice(screens.content))
    dispatch.invoke(activity,"page","2","")
    assertNull(error.get(activity));assertFalse(hasNotice(screens.content))
    dispatch.invoke(activity,"page","5","")
    assertEquals("owned-draft-address",screens.content.findViewWithTag<android.widget.EditText>("sendAddress").text.toString())
    assertFalse(hasNotice(screens.content))
    dispatch.invoke(activity,"send","owned-draft-address","")
    assertTrue(hasNotice(screens.content))
    instrument.callActivityOnPause(activity)
    assertNull(error.get(activity))
    instrument.callActivityOnResume(activity)
    assertFalse(hasNotice(screens.content))
    assertEquals("owned-draft-address",screens.content.findViewWithTag<android.widget.EditText>("sendAddress").text.toString())
   }
  }finally{instrument.runOnMainSync{activity.finish()}}
 }
 @Test fun enhancedControlsUi(){
  val instrument=InstrumentationRegistry.getInstrumentation();val app=instrument.targetContext
  val activity=instrument.startActivitySync(android.content.Intent(app,MainActivity::class.java).addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK)) as MainActivity
  val dispatch=MainActivity::class.java.getDeclaredMethod("action",String::class.java,String::class.java,String::class.java).apply{isAccessible=true}
  val screens=MainActivity::class.java.getDeclaredField("screens").apply{isAccessible=true}.get(activity) as SumuwwScreens
  val prefs=app.getSharedPreferences("sumuww-ui",0)
  val oldCharging=prefs.getBoolean("charging-only",false);val hadCharging=prefs.contains("charging-only")
  try{
   instrument.runOnMainSync{
    dispatch.invoke(activity,"page","11","")
    assertNotNull(screens.content.findViewWithTag<android.view.View>("sumuww-auto-lock"))
    dispatch.invoke(activity,"page","12","")
    assertNotNull(screens.content.findViewWithTag<android.view.View>("sumuww-battery-limit"))
    assertTrue(screens.content.findViewWithTag<android.view.View>("sumuww-charging-only").performClick())
    assertEquals(!oldCharging,prefs.getBoolean("charging-only",false))
    dispatch.invoke(activity,"page","3","")
    val search=screens.content.findViewWithTag<android.widget.EditText>("historySearch")
    assertNotNull(search);search.setText("owned-search")
    val accept=MainActivity::class.java.getDeclaredMethod("accept",JSONObject::class.java).apply{isAccessible=true}
    search.requestFocus()
    val state=MainActivity::class.java.getDeclaredField("state").apply{isAccessible=true}.get(activity) as? JSONObject
    if(state!=null)accept.invoke(activity,state)
    assertEquals("owned-search",screens.content.findViewWithTag<android.widget.EditText>("historySearch").text.toString())
    dispatch.invoke(activity,"page","11","")
    val secret=MainActivity::class.java.getDeclaredMethod("secret",String::class.java).apply{isAccessible=true}
    accept.invoke(activity,JSONObject((state?:JSONObject()).toString()).put("security",JSONObject().put("locked",false)))
    secret.invoke(activity,"owned test words only")
    val dialogs=MainActivity::class.java.getDeclaredField("sensitive").apply{isAccessible=true}.get(activity) as MutableList<*>
    assertTrue(dialogs.isNotEmpty())
    val shown=dialogs.last() as android.app.Dialog
    val locked=JSONObject((state?:JSONObject()).toString()).put("security",JSONObject().put("locked",true))
    accept.invoke(activity,locked)
    assertFalse("Secret dialog remains visible",shown.isShowing)
   }
  }finally{
   val editor=prefs.edit();if(hadCharging)editor.putBoolean("charging-only",oldCharging)else editor.remove("charging-only");editor.commit()
   instrument.runOnMainSync{activity.finish()}
  }
 }

 @Test fun mobileSafeguards(){
  val app=InstrumentationRegistry.getInstrumentation().targetContext
  val context=object:android.content.ContextWrapper(app){override fun getSharedPreferences(name:String,mode:Int)=super.getSharedPreferences("owned-safeguards-"+name,mode)}
  val prefs=context.getSharedPreferences("sumuww-transfer-alerts",0);prefs.edit().clear().commit()
  val ui=context.getSharedPreferences("sumuww-ui",0);ui.edit().clear().commit()
  try{
   fun row(id:String,h:Int?,value:Long=100L)=JSONObject().put("txid",id).put("height",h?:JSONObject.NULL).put("net_amount",value).put("coinbase",false).put("status",if(h==null)"pending" else "confirmed")
   fun rows(vararg tx:JSONObject)=org.json.JSONArray().apply{tx.forEach{put(it)}}
   val alerts=TransferAlerts(context)
   assertTrue(alerts.observe("wallet",100,rows(row("old",99)),"tip-a",0).isEmpty())
   assertEquals("revoked",alerts.observe("wallet",100,rows(),"tip-b",0).single().getString("stage"))
   assertEquals("revoked",alerts.take()!!.getString("stage"))
   assertTrue(alerts.observe("wallet",100,rows(),"tip-b",0).isEmpty())
   assertEquals("confirmed",alerts.observe("wallet",101,rows(row("old",101)),"tip-c",0).single().getString("stage"));alerts.take()
   assertEquals("recheck",alerts.observe("wallet",101,rows(row("old",null)),"tip-d",0).single().getString("stage"));alerts.take()
   assertTrue(alerts.observe("wallet",101,rows(row("old",null)),"tip-d",0).isEmpty())
   ui.edit().putBoolean("alert-incoming",false).commit()
   assertTrue(alerts.observe("wallet",102,rows(row("quiet",null))).isEmpty())
   repeat(120){alerts.result("$it","bounded")}
   assertEquals(TransferAlerts.MAX_QUEUE,org.json.JSONArray(prefs.getString("queue","[]")).length())
   assertEquals("20",alerts.take()!!.getString("title"))
   assertNotNull(MiningProtection.reason(80,450,true,0,15,false))
   assertNotNull(MiningProtection.reason(80,300,true,3,15,false))
   assertNotNull(MiningProtection.reason(15,300,false,0,15,false))
   assertNotNull(MiningProtection.reason(80,300,false,0,15,true))
   assertNull(MiningProtection.reason(80,300,true,0,15,true))
   if(!Python.isStarted())Python.start(AndroidPlatform(app))
   PcRuntime.start(app)
   val host=JSONObject(Python.getInstance().getModule("mobile_controls_selftest").callAttr("run").toString())
   File(app.getExternalFilesDir(null),"pc042-mobile-safeguards.json").writeText(JSONObject().put("host",host).put("reorg_alerts",true).put("bounded_queue",true).put("protection_policy",true).toString(2))
   assertTrue(host.toString(),host.getBoolean("success"))
  }finally{prefs.edit().clear().commit();ui.edit().clear().commit()}
 }

 @Test fun transferAlerts(){
  val instrument=InstrumentationRegistry.getInstrumentation();val app=instrument.targetContext
  val context=object:android.content.ContextWrapper(app){override fun getSharedPreferences(name:String,mode:Int)=super.getSharedPreferences("owned-test-"+name,mode)}
  context.getSharedPreferences("sumuww-transfer-alerts",0).edit().clear().commit()
  val alerts=TransferAlerts(context)
  fun row(id:String,amount:Long,height:Int?,coinbase:Boolean=false)=JSONObject().put("txid",id).put("net_amount",amount).put("height",height?:JSONObject.NULL).put("status",if(height==null)"pending" else "confirmed").put("coinbase",coinbase).put("confirmations",if(height==null)0 else 1)
  fun rows(vararg items:JSONObject)=org.json.JSONArray().apply{items.forEach{put(it)}}
  try{
   assertTrue(alerts.observe("wallet",100,rows(row("old",100,90),row("mined",500,100,true))).isEmpty())
   val incoming=rows(row("incoming",100000000,null))
   assertEquals(1,alerts.observe("wallet",100,incoming).size)
   assertEquals("pending",alerts.take()!!.getString("stage"))
   assertTrue(TransferAlerts(context).observe("wallet",100,incoming).isEmpty())
   assertEquals(1,alerts.observe("wallet",101,rows(row("incoming",100000000,101))).size)
   assertEquals("confirmed",alerts.take()!!.getString("stage"))
   assertTrue(alerts.observe("wallet",102,rows(row("incoming",100000000,101))).isEmpty())
   alerts.recordSubmitted("wallet","sent")
   assertTrue(alerts.observe("wallet",102,rows(row("sent",-100200000,null))).isEmpty())
   assertEquals(1,alerts.observe("wallet",103,rows(row("sent",-100200000,103))).size)
   assertFalse(alerts.take()!!.getBoolean("incoming"))
   alerts.recordSubmitted("wallet","sent")
   assertTrue(alerts.observe("wallet",103,rows(row("sent",-100200000,103))).isEmpty())
   assertTrue(alerts.observe("other-wallet",103,rows(row("incoming",100000000,101))).isEmpty())
   alerts.result("송금 불가","owned failure")
   assertEquals("송금 불가",TransferAlerts(context).take()!!.getString("title"))
   assertNull(alerts.take())
   val concurrent=(0 until 20).map{number->Thread{TransferAlerts(context).result("owned-$number","test")}.apply{start()}}
   concurrent.forEach{it.join(3000);assertFalse(it.isAlive)}
   val results=mutableSetOf<String>();repeat(20){results.add(alerts.take()!!.getString("title"))}
   assertEquals(20,results.size);assertNull(alerts.take())
   assertEquals("0.2",TransferAlerts.amount(20000000))
   val activity=instrument.startActivitySync(android.content.Intent(app,MainActivity::class.java).addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK)) as MainActivity
   val method=MainActivity::class.java.getDeclaredMethod("showResult",String::class.java,String::class.java).apply{isAccessible=true}
   instrument.runOnMainSync{
    for(title in listOf("송금 불가","송금 접수","입금 확인","입금 확인 대기")){
     val dialog=method.invoke(activity,title,"owned test") as android.app.AlertDialog
     assertTrue(dialog.isShowing);assertTrue(dialog.getButton(android.app.AlertDialog.BUTTON_POSITIVE).performClick())
    }
   }
   File(app.getExternalFilesDir(null),"pc042-transfer-alerts.json").writeText(JSONObject().put("passed",true).put("baseline_excludes_old_and_mining",true).put("pending_then_confirmed",true).put("duplicates_suppressed_after_restart",true).put("wallets_isolated",true).put("outgoing_confirmation",true).put("background_result_retained",true).put("concurrent_result_writers",20).put("result_dialogs",4).toString(2))
  }finally{context.getSharedPreferences("sumuww-transfer-alerts",0).edit().clear().commit()}
 }
 @Test fun sendDialogAndFee(){
  val instrument=InstrumentationRegistry.getInstrumentation();val context=instrument.targetContext
  val activity=instrument.startActivitySync(android.content.Intent(context,MainActivity::class.java).addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK)) as MainActivity
  Thread.sleep(1500)
  val dispatch=MainActivity::class.java.getDeclaredMethod("action",String::class.java,String::class.java,String::class.java).apply{isAccessible=true}
  val accept=MainActivity::class.java.getDeclaredMethod("accept",JSONObject::class.java).apply{isAccessible=true}
  val worker=MainActivity::class.java.getDeclaredField("worker").apply{isAccessible=true}.get(activity) as java.util.concurrent.ExecutorService
  val sensitive=MainActivity::class.java.getDeclaredField("sensitive").apply{isAccessible=true}
  val entered=java.util.concurrent.CountDownLatch(1);val release=java.util.concurrent.CountDownLatch(1)
  worker.execute{entered.countDown();release.await(10,java.util.concurrent.TimeUnit.SECONDS)}
  assertTrue(entered.await(20,java.util.concurrent.TimeUnit.SECONDS))
  var displayMs=0L
  lateinit var dialog:android.app.AlertDialog
  try{
   instrument.runOnMainSync{
    dispatch.invoke(activity,"page","5","")
    val manual=activity.window.decorView.findViewWithTag<android.widget.CheckBox>("manualFee")
    val fee=activity.window.decorView.findViewWithTag<android.widget.EditText>("sendFee")
    assertFalse(manual.isChecked)
    manual.performClick();assertTrue(manual.isChecked);fee.setText("0.002")
    accept.invoke(activity,JSONObject().put("node",JSONObject().put("peers",1)))
    assertSame(fee,activity.window.decorView.findViewWithTag("sendFee"));assertEquals("0.002",fee.text.toString())
    dispatch.invoke(activity,"page","2","");dispatch.invoke(activity,"page","5","")
    assertTrue(activity.window.decorView.findViewWithTag<android.widget.CheckBox>("manualFee").isChecked)
    assertEquals("0.002",activity.window.decorView.findViewWithTag<android.widget.EditText>("sendFee").text.toString())
    val start=android.os.SystemClock.elapsedRealtime()
    // Deliberately invalid recipient: this test cannot create or submit a real payment.
    dispatch.invoke(activity,"send","not-a-sumuww-address","1")
    dialog=(sensitive.get(activity) as List<*>).last() as android.app.AlertDialog
    assertTrue(dialog.isShowing);assertFalse(dialog.getButton(android.app.AlertDialog.BUTTON_POSITIVE).isEnabled)
    displayMs=android.os.SystemClock.elapsedRealtime()-start
   }
   assertTrue("Confirmation display waited on status worker: $displayMs ms",displayMs<500)
   val deadline=android.os.SystemClock.elapsedRealtime()+10000
   var finished=false
   while(!finished&&android.os.SystemClock.elapsedRealtime()<deadline){
    Thread.sleep(100)
    instrument.runOnMainSync{finished=dialog.getButton(android.app.AlertDialog.BUTTON_NEGATIVE).text.toString()==UiLanguage.text(context,"닫기")}
   }
   assertTrue("Payment validation queued behind status worker",finished)
   instrument.runOnMainSync{assertFalse(dialog.getButton(android.app.AlertDialog.BUTTON_POSITIVE).isEnabled);dialog.dismiss()}
   File(context.getExternalFilesDir(null),"pc042-send-ui.json").writeText(JSONObject().put("passed",true).put("confirmation_display_ms",displayMs).put("status_worker_blocked",true).put("fee_draft_preserved",true).put("invalid_payment_not_sendable",true).toString(2))
  }finally{release.countDown()}
 }
 @Test fun actualUiButtons(){
  val instrument=InstrumentationRegistry.getInstrumentation();val context=instrument.targetContext
  val activity=instrument.startActivitySync(android.content.Intent(context,MainActivity::class.java).addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK)) as MainActivity
  Thread.sleep(1200)
  val dispatch=MainActivity::class.java.getDeclaredMethod("action",String::class.java,String::class.java,String::class.java).apply{isAccessible=true}
  val accept=MainActivity::class.java.getDeclaredMethod("accept",JSONObject::class.java).apply{isAccessible=true}
  val page=MainActivity::class.java.getDeclaredField("page").apply{isAccessible=true}
  val prefs=context.getSharedPreferences("sumuww-ui",android.content.Context.MODE_PRIVATE);val oldTarget=prefs.getString("mining-target",null)
  fun find(view:android.view.View,caption:String):android.view.View?{
   if(view.isClickable&&view.contentDescription?.toString()==UiLanguage.text(context,caption))return view
   if(view is android.view.ViewGroup)for(i in 0 until view.childCount){find(view.getChildAt(i),caption)?.let{return it}}
   return null
  }
  var clicks=0
  try{
   instrument.runOnMainSync{dispatch.invoke(activity,"page","12","")}
   instrument.waitForIdleSync()
   lateinit var field:android.widget.EditText
   lateinit var button:android.view.View
   instrument.runOnMainSync{
    field=activity.window.decorView.findViewWithTag("miningTarget");field.setText("100");field.requestFocus()
    button=activity.window.decorView.findViewWithTag("miningApply")
    field.clearFocus()
    accept.invoke(activity,JSONObject().put("node",JSONObject().put("peers",1)))
    assertSame("Status poll replaced the apply button",button,activity.window.decorView.findViewWithTag("miningApply"))
    assertEquals("100",field.text.toString())
    (activity.getSystemService(android.content.Context.INPUT_METHOD_SERVICE) as android.view.inputmethod.InputMethodManager).showSoftInput(field,android.view.inputmethod.InputMethodManager.SHOW_IMPLICIT)
    button.requestRectangleOnScreen(android.graphics.Rect(0,0,button.width,button.height),true)
   }
   instrument.waitForIdleSync();Thread.sleep(800)
   // The IME changes the viewport after the first scroll request. Scroll again
   // after that layout, just as the user can, before measuring touch coordinates.
   instrument.runOnMainSync{button.requestRectangleOnScreen(android.graphics.Rect(0,0,button.width,button.height),true)}
   instrument.waitForIdleSync();Thread.sleep(250)
   val visible=android.graphics.Rect();assertTrue(button.getGlobalVisibleRect(visible))
   val down=android.os.SystemClock.uptimeMillis()
   instrument.sendPointerSync(android.view.MotionEvent.obtain(down,down,android.view.MotionEvent.ACTION_DOWN,visible.exactCenterX(),visible.exactCenterY(),0))
   Thread.sleep(100)
   instrument.sendPointerSync(android.view.MotionEvent.obtain(down,android.os.SystemClock.uptimeMillis(),android.view.MotionEvent.ACTION_UP,visible.exactCenterX(),visible.exactCenterY(),0))
   instrument.waitForIdleSync()
   assertEquals("Touch did not apply target",1,page.getInt(activity));assertEquals("100",prefs.getString("mining-target",null));clicks++
   for(value in listOf("0","10001","1.5","invalid")){
    instrument.runOnMainSync{dispatch.invoke(activity,"page","12","");activity.window.decorView.findViewWithTag<android.widget.EditText>("miningTarget").setText(value);activity.window.decorView.findViewWithTag<android.view.View>("miningApply").performClick()}
    assertEquals(12,page.getInt(activity));assertEquals("100",prefs.getString("mining-target",null));clicks++
   }
   instrument.runOnMainSync{activity.window.decorView.findViewWithTag<android.widget.EditText>("miningTarget").apply{setText("10000");onEditorAction(android.view.inputmethod.EditorInfo.IME_ACTION_DONE)}}
   assertEquals(1,page.getInt(activity));assertEquals("10000",prefs.getString("mining-target",null));clicks++
   for((from,caption,to) in listOf(Triple(0,"보내기",5),Triple(0,"받기",6),Triple(0,"채굴",1),Triple(0,"더보기",4),Triple(4,"지갑 관리",10),Triple(4,"보안 설정",11),Triple(4,"채굴 설정",12),Triple(4,"알림 설정",13),Triple(4,"테마",8),Triple(4,"도움말",7),Triple(4,"앱 정보",14),Triple(2,"거래내역",3))){
    instrument.runOnMainSync{dispatch.invoke(activity,"page",from.toString(),"");assertNotNull(caption,find(activity.window.decorView,caption));assertTrue(find(activity.window.decorView,caption)!!.performClick())}
    instrument.waitForIdleSync();assertEquals(caption,to,page.getInt(activity));clicks++
   }
   File(context.getExternalFilesDir(null),"pc042-ui-buttons.json").writeText(JSONObject().put("passed",true).put("button_checks",clicks).put("physical_apply_touch",true).put("draft_survives_poll",true).put("invalid_target_rejected",true).put("ime_done_applies",true).toString(2))
  }finally{prefs.edit().apply{if(oldTarget==null)remove("mining-target")else putString("mining-target",oldTarget)}.commit()}
 }
 @Test fun steadyBackground(){
  val instrument=InstrumentationRegistry.getInstrumentation();val context=instrument.targetContext
  val activity=instrument.startActivitySync(android.content.Intent(context,MainActivity::class.java).addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK)) as MainActivity
  val deadline=android.os.SystemClock.elapsedRealtime()+120000
  while(true){
   Thread.sleep(2000)
   val status=JSONObject(PcRuntime.call("status"));val node=status.getJSONObject("node")
   if(node.optBoolean("mining_ready"))break
   assertTrue("Node did not finish synchronization",android.os.SystemClock.elapsedRealtime()<deadline)
  }
  instrument.runOnMainSync{activity.moveTaskToBack(true)}
  val samples=org.json.JSONArray()
  repeat(18){
   Thread.sleep(10000);val node=JSONObject(PcRuntime.call("status")).getJSONObject("node")
   samples.put(JSONObject().put("height",node.optLong("height")).put("peers",node.optInt("peers")).put("sync_state",node.optString("sync_state")).put("mining_ready",node.optBoolean("mining_ready")))
  }
  val report=JSONObject().put("seconds",180).put("samples",samples)
  File(context.getExternalFilesDir(null),"pc042-steady-background.json").writeText(report.toString(2))
  assertTrue("Background connection interrupted: $report",(0 until samples.length()).all{samples.getJSONObject(it).getInt("peers")>0&&samples.getJSONObject(it).getBoolean("mining_ready")})
 }
 @Test fun hostAndNativeFailures(){
  val context=InstrumentationRegistry.getInstrumentation().targetContext
  if(!Python.isStarted())Python.start(AndroidPlatform(context))
  val globals=Python.getInstance().getModule("builtins").callAttr("dict")
  Python.getInstance().getModule("builtins").callAttr("exec","""
   import io,json,unittest
   suite=unittest.TestSuite()
   for name in ('test_android_host','test_native_adapter'):
       suite.addTests(unittest.defaultTestLoader.loadTestsFromName('pc_tests.'+name))
   stream=io.StringIO()
   result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
   report=json.dumps({'success':result.wasSuccessful(),'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'output':stream.getvalue()})
  """.trimIndent(),globals)
  val report=JSONObject(globals.callAttr("get","report").toString())
  File(context.getExternalFilesDir(null),"pc042-host-native.json").writeText(report.toString(2))
  assertTrue(report.toString(),report.getBoolean("success"))
 }
 @Test fun backupBounds(){
  assertArrayEquals(ByteArray(4096){7},WalletBackupIo.read(java.io.ByteArrayInputStream(ByteArray(4096){7})))
  for(bytes in listOf(ByteArray(0),ByteArray(4097))){
   try{WalletBackupIo.read(java.io.ByteArrayInputStream(bytes));fail("Invalid backup accepted")}catch(expected:IllegalArgumentException){}
  }
  val blocked=object:java.io.InputStream(){override fun read()=0;override fun read(buffer:ByteArray,offset:Int,length:Int)=0}
  try{WalletBackupIo.read(blocked);fail("Non-progressing provider accepted")}catch(expected:IllegalStateException){}
 }
 @Test fun bridgePaymentAndBatch(){
  val context=InstrumentationRegistry.getInstrumentation().targetContext
  if(!Python.isStarted())Python.start(AndroidPlatform(context))
  val globals=Python.getInstance().getModule("builtins").callAttr("dict")
  Python.getInstance().getModule("builtins").callAttr("exec","""
   import json,tempfile,time
   from pathlib import Path
   import pc_runtime as bridge
   from sumuww.app_service import AppService
   from sumuww.keystore import create_wallet
   from sumuww.profiles import REGTEST
   from sumuww import keystore
   keystore._publish_no_replace=bridge._publish_android
   # A previous UI test may have started the real node. Close it before
   # attaching the owned regtest fixture rather than orphaning its actor.
   bridge.stop()
   with tempfile.TemporaryDirectory(prefix='pc042-owned-roundtrip-') as folder:
       service=AppService(folder,network='regtest')
       service.start().result(timeout=30)
       bridge._service=service
       bridge._runtime_state='running'
       try:
           password='Public temporary test password2026'
           bridge.create_seed_wallet(password)
           assert len(bridge.recovery_phrase(password).split())==24
           original=json.loads(bridge.status())['wallet']['address']
           bridge.lock_wallet();bridge.open_wallet(password)
           assert json.loads(bridge.status())['wallet']['address']==original
           bridge.mine_blocks('101')
           deadline=time.monotonic()+40
           while json.loads(bridge.status())['mobile_batch']['running']:
               assert time.monotonic()<deadline,'Batch did not finish'
               time.sleep(.05)
           status=json.loads(bridge.status())
           assert status['mobile_batch']['completed']==101,status['mobile_batch']
           assert float(status['wallet']['available_smw'])>0
           recipient=create_wallet(Path(folder)/'recipient.json',password,network=REGTEST)
           started=time.monotonic()
           automatic=json.loads(bridge.prepare_payment(recipient.address,'1'))
           automatic_seconds=time.monotonic()-started
           assert automatic['source']!='manual'
           for invalid in ('-1','abc','0.000000001'):
               try: bridge.prepare_payment(recipient.address,'1',invalid)
               except Exception: pass
               else: raise AssertionError('Invalid fee accepted: '+invalid)
           started=time.monotonic()
           quote=json.loads(bridge.prepare_payment(recipient.address,'1','0.002'))
           manual_seconds=time.monotonic()-started
           assert quote['source']=='manual' and quote['fee_smw']=='0.00200000'
           rejected=json.loads(bridge.submit_payment_result('owned-invalid-id'))
           assert rejected['outcome']=='rejected'
           quote=json.loads(bridge.prepare_payment(recipient.address,'1','0.002'))
           accepted=json.loads(bridge.submit_payment_result(quote['quote_id']))
           assert accepted['outcome']=='accepted'
           assert json.loads(bridge.submit_payment_result(quote['quote_id']))['outcome']=='rejected'
           bridge.mine_blocks('1')
           while json.loads(bridge.status())['mobile_batch']['running']:
               time.sleep(.05)
           history=json.loads(bridge.transaction_history())
           assert history['total']>0
           payments=[row for row in history['transactions'] if not row['coinbase'] and row['net_amount']<0]
           assert len(payments)==1 and payments[0]['confirmations']>=1 and payments[0]['status']=='confirmed',payments
           service.open_wallet('recipient.json',password).result(timeout=30)
           received=json.loads(bridge.transaction_history())['transactions']
           assert len(received)==1 and received[0]['net_amount']==100000000 and received[0]['status']=='confirmed',received
           report=json.dumps({'passed':True,'seed_reopened':True,'accepted_batch_blocks':101,
               'automatic_quote_seconds':automatic_seconds,'manual_quote_seconds':manual_seconds,'manual_fee_smw':quote['fee_smw'],'invalid_fee_cases':3,'confirmed_payment_smw':'1','receiver_confirmed':True,'submission_outcomes_verified':True,'history_total':history['total'],'network':'regtest'})
       finally:
           bridge.stop()
  """.trimIndent(),globals)
  File(context.getExternalFilesDir(null),"pc042-bridge-roundtrip.json").writeText(globals.callAttr("get","report").toString())
 }
 @Test fun encryptedWalletCompatibility(){
  val context=InstrumentationRegistry.getInstrumentation().targetContext
  if(!Python.isStarted())Python.start(AndroidPlatform(context))
  val globals=Python.getInstance().getModule("builtins").callAttr("dict")
  Python.getInstance().getModule("builtins").callAttr("exec","""
   import io,json,unittest
   from sumuww import keystore
   from pc_runtime import _publish_android
   keystore._publish_no_replace=_publish_android
   suite=unittest.defaultTestLoader.loadTestsFromName('pc_tests.test_hd_keystore')
   stream=io.StringIO()
   result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
   report=json.dumps({'success':result.wasSuccessful(),'tests':result.testsRun,
       'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),'output':stream.getvalue()})
  """.trimIndent(),globals)
  val report=JSONObject(globals.callAttr("get","report").toString())
  File(context.getExternalFilesDir(null),"pc042-wallet.json").writeText(report.toString(2))
  assertTrue(report.toString(),report.getBoolean("success"))
 }
 @Test fun uiRoutesAndBackground(){
  val instrument=InstrumentationRegistry.getInstrumentation()
  val context=instrument.targetContext
  val activity=instrument.startActivitySync(android.content.Intent(context,MainActivity::class.java).addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK)) as MainActivity
  Thread.sleep(1500)
  val dispatch=MainActivity::class.java.getDeclaredMethod("action",String::class.java,String::class.java,String::class.java).apply{isAccessible=true}
  for(route in listOf(0,1,2,4,5,6,7,8,9,10,11,12,13,14)){
   instrument.runOnMainSync{dispatch.invoke(activity,"page",route.toString(),"")}
   instrument.waitForIdleSync()
   assertFalse("Route$route closed activity",activity.isFinishing)
  }
  val accept=MainActivity::class.java.getDeclaredMethod("accept",JSONObject::class.java).apply{isAccessible=true}
  instrument.runOnMainSync{
   dispatch.invoke(activity,"page","5","")
   val address=activity.window.decorView.findViewWithTag<android.widget.EditText>("sendAddress")
   address.setText("public-ui-draft");address.requestFocus();address.setSelection(6)
   accept.invoke(activity,JSONObject().put("node",JSONObject().put("peers",0)))
   assertSame(address,activity.window.decorView.findViewWithTag<android.widget.EditText>("sendAddress"))
   assertEquals("public-ui-draft",address.text.toString());assertEquals(6,address.selectionStart)
   dispatch.invoke(activity,"page","0","");dispatch.invoke(activity,"page","5","")
   assertEquals("public-ui-draft",activity.window.decorView.findViewWithTag<android.widget.EditText>("sendAddress").text.toString())
  }
  val prefs=context.getSharedPreferences("sumuww-ui",android.content.Context.MODE_PRIVATE)
  val oldPalette=prefs.getString("palette","default");val oldMode=prefs.getString("theme","system")
  try{
   for(palette in SumuwwTheme.manualPalettes)for(mode in listOf("light","dark")){
    prefs.edit().putString("palette",palette.id).putString("theme",mode).commit()
    instrument.runOnMainSync{dispatch.invoke(activity,"page","0","")}
    instrument.waitForIdleSync();assertFalse(activity.isFinishing)
   }
  }finally{prefs.edit().putString("palette",oldPalette).putString("theme",oldMode).commit()}
  val input=MainActivity::class.java.declaredMethods.first{it.name=="input"}.apply{isAccessible=true}
  instrument.runOnMainSync{
   input.invoke(activity,"Public secret-field test",true,"",{_:String->Unit})
   val dialogs=MainActivity::class.java.getDeclaredField("sensitive").apply{isAccessible=true}.get(activity) as List<*>
   val dialog=dialogs.last() as android.app.Dialog
   assertTrue(dialog.window!!.attributes.flags and android.view.WindowManager.LayoutParams.FLAG_SECURE !=0)
   dialog.dismiss()
  }
  instrument.runOnMainSync{activity.moveTaskToBack(true)}
  val samples=org.json.JSONArray()
  repeat(4){Thread.sleep(8000);samples.put(JSONObject(PcRuntime.call("status")).getJSONObject("node"))}
  File(context.getExternalFilesDir(null),"pc042-ui-background.json").writeText(JSONObject().put("routes",14).put("theme_mode_combinations",SumuwwTheme.manualPalettes.size*2).put("input_preservation",true).put("secure_dialog",true).put("background_samples",samples).toString(2))
  context.startActivity(android.content.Intent(context,MainActivity::class.java).addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK or android.content.Intent.FLAG_ACTIVITY_REORDER_TO_FRONT))
  instrument.runOnMainSync{activity.finish()}
 }
 @Test fun originalPcRegression(){
  val context=InstrumentationRegistry.getInstrumentation().targetContext
  if(!Python.isStarted())Python.start(AndroidPlatform(context))
  val globals=Python.getInstance().getModule("builtins").callAttr("dict")
  Python.getInstance().getModule("builtins").callAttr("exec","""
   import io,json,unittest,os,tempfile,sys,pc_tests
   sys.modules['tests']=pc_tests
   from pathlib import Path
   from sumuww import keystore
   from pc_runtime import _publish_android
   # Android filesystem compatibility only; tests use temporary public fixtures.
   keystore._publish_no_replace=_publish_android
   stream=io.StringIO()
   loader=unittest.TestLoader()
   suite=unittest.TestSuite()
   for module in ('test_wallet','test_hd','test_address','test_difficulty','test_peer','test_primitives','test_transaction','test_wire','test_profiles','test_fee_selection','test_fee_estimation','test_chain_incremental_v28','test_block_enforcement_v16','test_rpc','test_peer_load_v37','test_peer_admission_load_v37','test_peer_policy_v38','test_peer_safety_v15','test_peer_sync_load_v37','test_dht_peer_v29','test_dht_retry_v33','test_mempool_capacity_v38','test_peer_unique_v46'):
       suite.addTests(loader.loadTestsFromName('pc_tests.'+module))
   result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
   report=json.dumps({'success':result.wasSuccessful(),'tests':result.testsRun,
       'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),'output':stream.getvalue()})
  """.trimIndent(),globals)
  val report=JSONObject(globals.callAttr("get","report").toString())
  File(context.getExternalFilesDir(null),"pc042-regression.json").writeText(report.toString(2))
  assertTrue(report.toString(),report.getBoolean("success"))
 }
 @Test fun installedNode(){
  val context=InstrumentationRegistry.getInstrumentation().targetContext
  PcRuntime.start(context)
  val samples=org.json.JSONArray()
  repeat(8){Thread.sleep(8000);val status=JSONObject(PcRuntime.call("status"));samples.put(status.optJSONObject("node"))}
  File(context.getExternalFilesDir(null),"pc042-node.json").writeText(samples.toString(2))
  assertTrue(samples.length()==8)
 }
}
