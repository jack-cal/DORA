package org.sumuww.miner

import android.app.*
import android.content.*
import android.content.res.Configuration
import android.os.*
import android.text.InputType
import android.view.*
import android.widget.*
import org.json.JSONObject
import java.io.File
import java.util.concurrent.Executors

/** Fresh UI controller; every operation delegates to PC042's service adapter. */
class MainActivity:Activity(){
 private lateinit var screens:SumuwwScreens
 private val worker=Executors.newSingleThreadExecutor()
 private val controls=Executors.newSingleThreadExecutor()
 private val transfers=Executors.newSingleThreadExecutor()
 private val main=Handler(Looper.getMainLooper())
 private var error:String?=null
 private val updates by lazy{SumuwwUpdates(this){page==14&&polling&&SumuwwConsent.accepted(this)}}
 private val backPages=java.util.ArrayDeque<Int>()
 private var page=0
  set(value){if(field!=value){error=null;};field=value}
 private var state:JSONObject?=null
 private var blocks:JSONObject?=null; private var blocksOffset=0; private var blocksSearch=""; private var blocksBusy=false; private var blocksRequest=0
 private var history:JSONObject?=null; private var offset=0; private var filter="all"; private var search=""
 private var lastActivitySignal=0L
 private var target="1"; private var appliedTarget="1"; private var recipient=""; private var quantity=""
 private var manualFee=false; private var feeDraft="1"; private var feeMode=1
 private var touching=false
 private var polling=false
 private var cpu=0; private var cpuWall=SystemClock.elapsedRealtime(); private var cpuTime=android.os.Process.getElapsedCpuTime()
 private val sensitive=mutableListOf<Dialog>()
 private var epoch=0; private var historyRequest=0; private var preparing=false
 private var pollError=false
 private var lastStatusAt=0L
 private fun checkStatusFreshness(){if(lastStatusAt>0L&&SystemClock.elapsedRealtime()-lastStatusAt>15000L&&!pollError){pollError=true;render()}}
 private val freshness=object:Runnable{override fun run(){if(!polling)return;checkStatusFreshness();main.postDelayed(this,1000)}}
 private var resultShowing=false
 private var bootRequested=false; private var withdrawing=false
 private var consentOverlay:View?=null
 private var privacyDialog:AlertDialog?=null
 private val prefs get()=getSharedPreferences("sumuww-ui",MODE_PRIVATE)
 private fun tr(s:String)=UiLanguage.text(this,s)
 private fun mode()=prefs.getString("theme","system")?:"system"
 private fun dark()=when(mode()){"dark"->true;"light"->false;else->resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK==Configuration.UI_MODE_NIGHT_YES}
 private val poll=object:Runnable{override fun run(){if(!polling||worker.isShutdown)return;worker.execute{try{val now=SystemClock.elapsedRealtime();val used=android.os.Process.getElapsedCpuTime();cpu=(((used-cpuTime)*100)/(now-cpuWall).coerceAtLeast(1)/Runtime.getRuntime().availableProcessors().coerceAtLeast(1)).toInt().coerceIn(0,100);cpuWall=now;cpuTime=used;val next=JSONObject(PcRuntime.call("status"));postUi{if(pollError){error=null;pollError=false};accept(next)}}catch(e:Exception){postUi{pollError=true;error=e.message;render()}}finally{main.post{if(polling)main.postDelayed(this,5000)}}}}}
 override fun onCreate(saved:Bundle?){
  setTheme(if(dark())R.style.AppThemeDark else R.style.AppThemeLight);super.onCreate(saved)
  LocaleBrand.syncLauncher(this)
  appliedTarget=prefs.getString("mining-target","1")?.toIntOrNull()?.takeIf{it in 1..10000}?.toString()?:"1"
  target=appliedTarget
  saved?.let{page=it.getInt("page");target=it.getString("target","1")?:"1";recipient=it.getString("recipient","")?:"";quantity=it.getString("quantity","")?:"";manualFee=it.getBoolean("manualFee");feeMode=it.getInt("feeMode",1).coerceIn(0,2);feeDraft=it.getString("feeDraft","1")?:"1";offset=it.getInt("offset");filter=it.getString("filter","all")?:"all";search=it.getString("search","")?:""}
  saved?.let{blocksOffset=it.getInt("blocksOffset");blocksSearch=it.getString("blocksSearch", "")?:""}
  saved?.getIntArray("backPages")?.filter{it in 0..15}?.takeLast(32)?.forEach{backPages.addLast(it)}
  if(Build.VERSION.SDK_INT>=30)window.setDecorFitsSystemWindows(false)
  screens=SumuwwScreens(this,{tr(it)},{a,b,c->action(a,b,c)})
  setContentView(screens.appRoot);render()
  val splash=sumuwwSplash(this,SumuwwThemeCalendar.resolve(prefs.getString("palette","default")),dark())
  screens.appRoot.addView(splash);main.postDelayed({screens.appRoot.removeView(splash)},800)
  if(SumuwwConsent.accepted(this))bootRuntime()

 }
 override fun onResume(){super.onResume();if(!SumuwwConsent.accepted(this)){polling=false;render();return};bootRuntime();polling=true;checkStatusFreshness();render();main.removeCallbacks(freshness);main.postDelayed(freshness,1000);if(!controls.isShutdown)controls.execute{try{PcRuntime.setForeground(true)}catch(_:Exception){}};main.removeCallbacks(poll);main.postDelayed(poll,1000)}
 override fun dispatchTouchEvent(event:MotionEvent):Boolean{
  if(event.actionMasked==MotionEvent.ACTION_DOWN){touching=true
   val now=SystemClock.elapsedRealtime()
   if(SumuwwConsent.accepted(this)&&bootRequested&&now-lastActivitySignal>1000&&!controls.isShutdown){lastActivitySignal=now;controls.execute{try{PcRuntime.call("user_activity")}catch(_:Exception){}}}
  }
  return try{super.dispatchTouchEvent(event)}finally{if(event.actionMasked==MotionEvent.ACTION_UP||event.actionMasked==MotionEvent.ACTION_CANCEL)touching=false}
 }
 override fun onPause(){privacyDialog?.dismiss();privacyDialog=null;updates.cancel();captureDrafts();error=null;touching=false;epoch++;polling=false;if(!controls.isShutdown)controls.execute{try{PcRuntime.setForeground(false)}catch(_:Exception){}};main.removeCallbacks(poll);main.removeCallbacks(freshness);sensitive.toList().forEach{it.dismiss()};sensitive.clear();super.onPause()}
 override fun onDestroy(){updates.close();polling=false;main.removeCallbacksAndMessages(null);worker.shutdown();controls.shutdown();transfers.shutdown();super.onDestroy()}
 override fun onSaveInstanceState(saved:Bundle){captureDrafts();saved.putInt("page",page);saved.putIntArray("backPages",backPages.toIntArray());saved.putString("target",target);saved.putString("recipient",recipient);saved.putString("quantity",quantity);saved.putBoolean("manualFee",manualFee);saved.putInt("feeMode",feeMode);saved.putString("feeDraft",feeDraft);saved.putInt("offset",offset);saved.putString("filter",filter);saved.putString("search",search);saved.putInt("blocksOffset",blocksOffset);saved.putString("blocksSearch",blocksSearch);super.onSaveInstanceState(saved)}
 private fun navigate(next:Int){
  if(next in listOf(0,1,2,4))backPages.clear()
  else if(next!=page){if(backPages.size>=32)backPages.removeFirst();backPages.addLast(page)}
  page=next
 }
 override fun onBackPressed(){if(consentOverlay!=null){if(SumuwwConsent.accepted(this))closeConsent()else finish();return};captureDrafts();page=if(backPages.isNotEmpty())backPages.removeLast()else when(page){3,5,6->2;8,10,11,13,14->9;12->1;7,9,15->4;else->0};if(page==3)loadHistory();if(page==15)loadBlocks();render()}
 private fun postUi(block:()->Unit){main.post{if(!isDestroyed&&!isFinishing){if(touching)main.postDelayed({postUi(block)},50)else block()}}}
 private fun accept(next:JSONObject){
  lastStatusAt=SystemClock.elapsedRealtime();if(pollError){pollError=false;error=null}
  val before=address();val wasLocked=state?.optJSONObject("security")?.optBoolean("locked")?:false
  state=next
  if(!wasLocked&&next.optJSONObject("security")?.optBoolean("locked")==true){epoch++;sensitive.toList().forEach{it.dismiss()};sensitive.clear()}
  if(before!=address()){history=null;offset=0;historyRequest++;if(page==3)loadHistory()}
  val runtimeError=next.optString("runtime_error","");if(runtimeError.isNotBlank()&&runtimeError!="null")error=runtimeError
  // Keep focused input views intact during background status polling.
  if(page in listOf(5,12))screens.updateFormStatus(next,cpu)
  else if(page==15){if(blocks==null&&!blocksBusy&&currentFocus?.tag!="blockSearch")loadBlocks()}
  else if(page==3&&currentFocus?.tag=="historySearch"){}
  else if(!touching)render()
  showTransferAlert()
 }
 private fun captureDrafts(){
  if(!::screens.isInitialized)return
  if(page==5){screens.content.findViewWithTag<EditText>("sendAddress")?.let{recipient=it.text.toString()};screens.content.findViewWithTag<EditText>("sendAmount")?.let{quantity=it.text.toString()};screens.content.findViewWithTag<EditText>("sendFee")?.let{feeDraft=it.text.toString()};screens.content.findViewWithTag<CheckBox>("manualFee")?.let{manualFee=it.isChecked};screens.content.findViewWithTag<android.widget.Spinner>("feeMode")?.let{feeMode=it.selectedItemPosition.coerceIn(0,2)}}
  if(page==15)screens.content.findViewWithTag<EditText>("blockSearch")?.let{blocksSearch=it.text.toString()}
  if(page==3)screens.content.findViewWithTag<EditText>("historySearch")?.let{search=it.text.toString()}
  if(page==12)screens.content.findViewWithTag<EditText>("miningTarget")?.let{target=it.text.toString()}
 }
 private fun render(){
  if(isDestroyed||isFinishing)return
  if(!SumuwwConsent.accepted(this)){showConsent(false);return}
  captureDrafts()
  val palette=SumuwwThemeCalendar.resolve(prefs.getString("palette","default"))
  screens.render(SumuwwScreens.Model(page,state,history,offset,filter,cpu,
   state?.optJSONObject("mobile_batch")?.optDouble("elapsed_seconds",0.0)?.toLong()?.let{seconds->"%02d:%02d:%02d".format(seconds/3600,seconds/60%60,seconds%60)}?:"00:00:00",
   if(page==12)target else appliedTarget,recipient,quantity,error,false,dark(),palette,mode(),UiLanguage.languages[UiLanguage.code(this)]?:"English",manualFee,feeDraft,search,pollError,blocks,blocksSearch,feeMode))
  window.statusBarColor=SumuwwTheme.background(palette,dark());window.navigationBarColor=SumuwwTheme.background(palette,dark())
  if(Build.VERSION.SDK_INT>=30){
   val mask=WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS or WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS
   window.insetsController?.setSystemBarsAppearance(if(dark())0 else mask,mask)
  }else{
   val mask=View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR or View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR
   window.decorView.systemUiVisibility=if(dark())window.decorView.systemUiVisibility and mask.inv() else window.decorView.systemUiVisibility or mask
  }
 }
 private fun bootRuntime(){
  if(bootRequested||withdrawing||!SumuwwConsent.accepted(this))return
  bootRequested=true
  try{startForegroundService(Intent(this,PcNodeService::class.java))}catch(e:Exception){fail(e)}
  if(Build.VERSION.SDK_INT>=33&&checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS)!=android.content.pm.PackageManager.PERMISSION_GRANTED)requestPermissions(arrayOf(android.Manifest.permission.POST_NOTIFICATIONS),42)
  worker.execute{try{val result=JSONObject(PcRuntime.start(this));postUi{if(SumuwwConsent.accepted(this)){accept(result);if(page==3)loadHistory();if(page==15)loadBlocks()}}}catch(e:Exception){fail(e)}}
 }
 private fun closeConsent(){consentOverlay?.let{screens.appRoot.removeView(it)};consentOverlay=null}
 private fun showConsent(managing:Boolean){
  if(consentOverlay!=null)return
  consentOverlay=sumuwwConsentView(this,SumuwwThemeCalendar.resolve(prefs.getString("palette","default")),dark(),managing,withdrawing,
   {
    if(!withdrawing){SumuwwConsent.accept(this);closeConsent();render();bootRuntime();polling=true;main.removeCallbacks(poll);main.postDelayed(poll,1000)}
   },{
    SumuwwVerticalCaptions.builder(this).setTitle(SumuwwConsent.text(this,"revoke"))
     .setMessage(SumuwwConsent.text(this,"revokeBody"))
     .setNegativeButton(tr("취소"),null).setPositiveButton(tr("확인")){_,_->withdrawConsent()}.show()
   },{if(managing)closeConsent()else finish()}, {
    SumuwwVerticalCaptions.builder(this).setTitle(tr("언어")).setItems(UiLanguage.languages.values.toTypedArray()){_,i->
     UiLanguage.set(this,UiLanguage.languages.keys.elementAt(i));closeConsent();showConsent(managing)
    }.show()
   })
  screens.appRoot.addView(consentOverlay,android.widget.FrameLayout.LayoutParams(-1,-1))
  consentOverlay?.requestApplyInsets()
 }
 private fun withdrawConsent(){
  withdrawing=true;SumuwwConsent.revoke(this);epoch++;polling=false;main.removeCallbacks(poll)
  sensitive.toList().forEach{it.dismiss()};sensitive.clear()
  closeConsent();showConsent(false)
  controls.execute{
   var stopped=false
   repeat(3){if(!stopped)try{PcRuntime.stopIfStarted();stopped=true}catch(e:Exception){android.util.Log.w("SumuwwConsent","Shutdown after withdrawal failed",e)}}
   stopService(Intent(this,PcNodeService::class.java))
   postUi{bootRequested=false;withdrawing=!stopped;state=null;history=null;error=null;backPages.clear();page=0;closeConsent();render()}
  }
 }
 private fun fail(e:Exception){postUi{error=if(listOf("fee rate","manual fee exceeds","relay minimum").any { (e.message?:"").lowercase().contains(it) })tr("수수료율과 지갑의 수수료 한도를 확인하세요.") else e.message?:e.javaClass.simpleName;render()}}
 private fun call(method:String,vararg args:String){val executor=if(method=="stop_mining")controls else if(method=="submit_payment")transfers else worker;if(executor.isShutdown)return;executor.execute{try{PcRuntime.call(method,*args);val next=JSONObject(PcRuntime.call("status"));postUi{error=null;accept(next)}}catch(e:Exception){fail(e)}}}
 private fun address()=state?.optJSONObject("wallet")?.optString("address","")?:""
 private fun showResult(title:String,message:String):AlertDialog?{
  if(!polling)return null
  resultShowing=true
  val dialog=SumuwwVerticalCaptions.builder(this).setTitle(tr(title)).setMessage(message).setPositiveButton(tr("확인"),null).create()
  sensitive.add(dialog);dialog.setOnDismissListener{resultShowing=false;sensitive.remove(dialog)};dialog.show()
  return dialog
 }
 private fun showTransferAlert(){
  if(!polling||resultShowing||preparing||sensitive.isNotEmpty())return
  val event=TransferAlerts(this).take()?:return
  if(event.has("title")){showResult(event.getString("title"),event.getString("message"));return}
  val incoming=event.getBoolean("incoming");val pending=event.getString("stage")=="pending"
  val title=if(incoming){if(pending)"입금 확인 대기" else "입금 확인"}else "송금 블록 확인"
  val stage=event.getString("stage")
  if(stage=="revoked"||stage=="recheck"){
   showResult("거래 재확인 필요",tr("체인 변경으로 이전 블록 확인이 취소됐습니다. 거래내역에서 다시 확인하세요.")+"\n"+event.getString("txid"));return
  }
  val detail=if(pending)"블록에 포함되기 전입니다. 아직 사용 가능한 잔액이 아닙니다." else "블록에 포함됐습니다. 확인 수가 늘어날수록 거래 확정성이 높아집니다."
  showResult(title,TransferAlerts.amount(kotlin.math.abs(event.getLong("net_amount")))+" SMW\n"+tr(detail)+"\n"+event.optString("wallet")+"\n"+event.getString("txid"))
 }
 private fun submitPayment(id:String){
  val wallet=address()
  val progress=showResult("송금 처리 중",tr("거래를 제출하고 있습니다. 중복 전송하지 마세요."))
  transfers.execute{try{
   val response=JSONObject(PcRuntime.call("submit_payment_result",id))
   if(response.getString("outcome")!="accepted"){
    TransferAlerts(this).result(if(response.getString("outcome")=="rejected")"송금 불가" else "송금 결과 확인 필요",response.optString("error")+"\n"+tr("거래내역을 확인하세요. 접수 여부가 불명확하면 다시 보내지 마세요."))
    postUi{progress?.dismiss();showTransferAlert()}
    return@execute
   }
   val result=response.getJSONObject("result")
   TransferAlerts(this).recordSubmitted(wallet,result.getString("txid"))
   TransferAlerts(this).result("송금 접수",tr("거래가 내 노드에 접수됐습니다. 상대방 수신과 블록 확인은 아직 대기 중입니다.")+"\n"+result.getString("txid"))
   postUi{progress?.dismiss();showTransferAlert();call("status")}
  }catch(e:Exception){TransferAlerts(this).result("송금 결과 확인 필요",(e.message?:e.javaClass.simpleName)+"\n"+tr("거래내역을 확인하세요. 접수 여부가 불명확하면 다시 보내지 마세요."));postUi{progress?.dismiss();showTransferAlert()}}}
 }
 private fun confirmPrivacy(mode:String){
  val key="privacy-help-hidden-$mode"
  fun activate(){call("configure_privacy",mode,if(mode=="i2p")"7656" else "9050")}
  if(prefs.getBoolean(key,false)){activate();return}
  val hide=CheckBox(this).apply{text=tr("다음부터 도움말을 보지 않겠습니다.");isChecked=false;SumuwwVerticalCaptions.watch(this)}
  val padding=(16*resources.displayMetrics.density).toInt()
  val view=LinearLayout(this).apply{orientation=LinearLayout.VERTICAL;setPadding(padding,0,padding,0);addView(hide)}
  val notice=when(mode){"tor"->"Tor 사용 안내";"i2p"->"I2P 사용 안내";else->"일반 연결 안내"}
  privacyDialog=SumuwwVerticalCaptions.builder(this).setTitle(tr("IP 보호")+" · "+mode.uppercase()).setMessage(tr(notice)).setView(view)
   .setNegativeButton(tr("취소"),null).setPositiveButton(tr("실행")){_,_->
    prefs.edit().putBoolean(key,hide.isChecked).apply();activate()
   }.show()
  privacyDialog?.setOnDismissListener{privacyDialog=null}
 }

 private fun action(a:String,b:String,c:String){if(!SumuwwConsent.accepted(this)){showConsent(false);return};captureDrafts();when(a){
  "consentSettings"->showConsent(true)
  "checkUpdates"->updates.check()
  "documents"->startActivity(Intent(this,DocumentationActivity::class.java))
  "page"->{navigate(b.toIntOrNull()?.takeIf{it in 0..15}?:return);if(page==3){history=null;loadHistory()};if(page==15){blocks=null;loadBlocks()};render()};"back"->onBackPressed()
  "startMining"->{
   val reason=MiningProtection.read(this).reason
   if(reason!=null){error=tr(reason);render();return}
   if(state?.optJSONObject("security")?.optBoolean("locked")==true){password("지갑 비밀번호"){pass->controls.execute{try{val next=JSONObject(PcRuntime.call("unlock_spending",pass));postUi{accept(next);action("startMining",b,c)}}catch(e:Exception){fail(e)}}};return}
   val count=b.toIntOrNull();if(count==null||count !in 1..10000){error=tr("1–10000 사이 블록 수를 입력하세요.");render()}else{target=b;call("mine_blocks",b)}};"stopMining"->call("stop_mining")
  "miningTarget"->{requireTarget(b)}
  "blocksRefresh"->{blocksOffset=0;loadBlocks()}
  "blocksPrevious"->{blocksOffset=(blocksOffset-50).coerceAtLeast(0);loadBlocks()}
  "blocksNext"->{blocksOffset+=50;loadBlocks()}
  "blockSearch"->{val height=b.trim().toIntOrNull();if(height==null||height<0){error=tr("블록 높이")+": 0–"+(state?.optJSONObject("node")?.optInt("height")?:0);render()}else{currentFocus?.clearFocus();loadBlocks(height.toString())}}
  "history"->{navigate(3);offset=0;loadHistory()};"historyRefresh"->loadHistory()
  "historyPrevious"->{offset=(offset-50).coerceAtLeast(0);loadHistory()};"historyNext"->{offset+=50;loadHistory()}
  "historyFilter"->{filter=b;offset=0;history=null;loadHistory();render()}
  "historySearch"->{search=b;offset=0;history=null;currentFocus?.clearFocus();loadHistory();render()}
  "transaction"->SumuwwVerticalCaptions.builder(this).setTitle(tr("거래내역")).setMessage(b).setPositiveButton(tr("닫기"),null).show()
  "send"->{recipient=b;quantity=c;prepare(b,c)}
  "walletManager"->walletMenu();"recoveryWords"->password("복구 단어 보기"){password->val owner=epoch;worker.execute{try{val words=PcRuntime.call("recovery_phrase",password);postUi{if(polling&&epoch==owner)secret(words)}}catch(e:Exception){fail(e)}}}
  "copyAddress"->{if(address().isNotBlank())(getSystemService(CLIPBOARD_SERVICE) as ClipboardManager).setPrimaryClip(ClipData.newPlainText("SMW",address()))}
  "copyI2p"->{val host=state?.optJSONObject("connection")?.optJSONObject("privacy")?.optString("i2p_address")?:"";if(host.isNotBlank()&&host!="null")(getSystemService(CLIPBOARD_SERVICE) as ClipboardManager).setPrimaryClip(ClipData.newPlainText("I2P",host+":18444"))}
  "shareAddress"->{if(address().isNotBlank())startActivity(Intent.createChooser(Intent(Intent.ACTION_SEND).apply{type="text/plain";putExtra(Intent.EXTRA_TEXT,address())},tr("공유하기")))}
  "refresh"->call("status");"peer"->input("피어 추가"){call("add_peer",it)}
  "privacy"->SumuwwVerticalCaptions.builder(this).setTitle(tr("IP 보호")).setItems(arrayOf("Direct","Tor","I2P")){_,i->confirmPrivacy(arrayOf("direct","tor","i2p")[i])}.show()
  "stats"->SumuwwVerticalCaptions.builder(this).setTitle(tr("상세 통계")).setMessage(JSONObject().put("node",state?.optJSONObject("node")).put("mining",state?.optJSONObject("mining")).put("mobile_mining",state?.optJSONObject("mobile_mining")).put("batch",state?.optJSONObject("mobile_batch")).toString(2)).setPositiveButton(tr("닫기"),null).show()
  "nodeSettings"->{navigate(9);render()};"help"->{navigate(7);render()};"palette"->{navigate(8);render()}
  "selectPalette"->{prefs.edit().putString("palette",b).apply();render()}
  "mode"->SumuwwVerticalCaptions.builder(this).setTitle(tr("라이트·다크")).setItems(arrayOf(tr("시스템 설정"),tr("라이트 모드"),tr("다크 모드"))){_,i->prefs.edit().putString("theme",arrayOf("system","light","dark")[i]).apply();recreate()}.show()
  "language"->SumuwwVerticalCaptions.builder(this).setTitle(tr("언어")).setItems(UiLanguage.languages.values.toTypedArray()){_,i->UiLanguage.set(this,UiLanguage.languages.keys.elementAt(i));render()}.show()
  "autoLock"->SumuwwVerticalCaptions.builder(this).setTitle(tr("자동 보안 잠금")).setItems(arrayOf("1 min","5 min","15 min")){_,i->val seconds=intArrayOf(60,300,900)[i];prefs.edit().putInt("auto-lock-seconds",seconds).apply();call("security_settings",seconds.toString());render()}.show()
  "chargingOnly"->{prefs.edit().putBoolean("charging-only",!prefs.getBoolean("charging-only",false)).apply();render()}
  "batteryLimit"->SumuwwVerticalCaptions.builder(this).setTitle(tr("최저 배터리")).setItems(arrayOf("10%","15%","20%","30%")){_,i->prefs.edit().putInt("battery-limit",intArrayOf(10,15,20,30)[i]).apply();render()}.show()
  "alertIncoming","alertOutgoing","alertMining"->{val key=when(a){"alertIncoming"->"alert-incoming";"alertOutgoing"->"alert-outgoing";else->"alert-mining"};prefs.edit().putBoolean(key,!prefs.getBoolean(key,true)).apply();render()}
  "notificationSettings"->startActivity(Intent(android.provider.Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(android.provider.Settings.EXTRA_APP_PACKAGE,packageName))
  "backgroundSettings"->startActivity(Intent(android.provider.Settings.ACTION_APPLICATION_DETAILS_SETTINGS,android.net.Uri.parse("package:$packageName")))
  "exportBackup"->startActivityForResult(Intent(Intent.ACTION_CREATE_DOCUMENT).apply{type="application/json";addCategory(Intent.CATEGORY_OPENABLE);putExtra(Intent.EXTRA_TITLE,"wallet.json")},101)
  "importBackup"->startActivityForResult(Intent(Intent.ACTION_OPEN_DOCUMENT).apply{type="application/json";addCategory(Intent.CATEGORY_OPENABLE)},102)
  "tour"->tour(0)
 }}
 private fun requireTarget(s:String){
  val n=s.trim().toIntOrNull()
  if(n==null||n !in 1..10000){error=tr("1–10000 사이 블록 수를 입력하세요.");render();return}
  appliedTarget=n.toString();target=appliedTarget
  prefs.edit().putString("mining-target",appliedTarget).apply();error=null
  (getSystemService(INPUT_METHOD_SERVICE) as android.view.inputmethod.InputMethodManager).hideSoftInputFromWindow(window.decorView.windowToken,0)
  currentFocus?.clearFocus();navigate(1);render()
  Toast.makeText(this,tr("채굴 목표를 적용했습니다.")+" "+appliedTarget+" "+tr("블록"),Toast.LENGTH_SHORT).show()
 }
 private fun input(label:String,secret:Boolean=false,initial:String="",done:(String)->Unit){
  val edit=EditText(this).apply{hint=if(UiLanguage.code(this@MainActivity)=="mn-Mong") "" else tr(label);inputType=InputType.TYPE_CLASS_TEXT or if(secret)InputType.TYPE_TEXT_VARIATION_PASSWORD else InputType.TYPE_TEXT_FLAG_MULTI_LINE}
  edit.setText(initial)
  val box=LinearLayout(this).apply{orientation=LinearLayout.VERTICAL;setPadding(32,8,32,8);addView(edit)}
  if(secret)box.addView(CheckBox(this).apply{SumuwwVerticalCaptions.watch(this);text=tr(if(label.contains("복구 단어"))"복구 단어 표시" else "비밀번호 표시");setOnCheckedChangeListener{_,checked->val cursor=edit.selectionStart;edit.inputType=InputType.TYPE_CLASS_TEXT or if(checked)InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD else InputType.TYPE_TEXT_VARIATION_PASSWORD;edit.setSelection(cursor.coerceIn(0,edit.text.length))}})
  val dialog=SumuwwVerticalCaptions.builder(this).setTitle(tr(label)).setView(box).setNegativeButton(tr("취소"),null).setPositiveButton(tr("확인"),null).create()
  if(secret){edit.isSaveEnabled=false;edit.importantForAutofill=View.IMPORTANT_FOR_AUTOFILL_NO_EXCLUDE_DESCENDANTS;dialog.window?.addFlags(WindowManager.LayoutParams.FLAG_SECURE);sensitive.add(dialog);dialog.setOnDismissListener{edit.text.clear();sensitive.remove(dialog)}}
  dialog.show();dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener{val value=edit.text.toString();dialog.dismiss();done(value)}
 }
 private fun password(label:String,done:(String)->Unit)=input(label,true,done=done)
 private fun walletMenu(){
  if(state?.optJSONObject("mobile_batch")?.optBoolean("running")==true)return
  val choices=arrayOf("지갑 열기","시드 지갑","새 지갑","복구 단어로 복구","지갑 잠금")
  fun unlocked()=state?.optJSONObject("wallet")?.optBoolean("unlocked")==true&&state?.optJSONObject("security")?.optBoolean("locked")!=true
  val adapter=object:android.widget.ArrayAdapter<String>(this,android.R.layout.simple_list_item_1,choices.map{tr(it)}){
   override fun areAllItemsEnabled()=false
   override fun isEnabled(position:Int)=if(unlocked())position==4 else position!=4
   override fun getView(position:Int,convertView:android.view.View?,parent:android.view.ViewGroup):android.view.View=super.getView(position,convertView,parent).apply{isEnabled=isEnabled(position);alpha=if(isEnabled)1f else .4f}
  }
  SumuwwVerticalCaptions.builder(this).setTitle(tr("지갑 관리")).setAdapter(adapter){_,i->if(!adapter.isEnabled(i)||state?.optJSONObject("mobile_batch")?.optBoolean("running")==true)return@setAdapter;when(i){
   0->password("지갑 비밀번호"){call("open_wallet",it)}
   1,2->{val method=if(i==1)"create_seed_wallet" else "create_wallet";password("지갑 비밀번호"){first->password("비밀번호 확인"){second->if(first!=second){error=tr("비밀번호가 일치하지 않습니다");render()}else{val owner=epoch;worker.execute{try{PcRuntime.call(method,first);val words=if(i==1)PcRuntime.call("recovery_phrase",first) else null;val next=JSONObject(PcRuntime.call("status"));postUi{accept(next);if(words!=null&&polling&&epoch==owner)secret(words)}}catch(e:Exception){fail(e)}}}}}}
   3->password("지갑 비밀번호"){pass->input("24개 복구 단어",true){words->call("recover_seed_wallet",pass,words)}}
   4->call("lock_wallet")
  }}.show()
 }
 private fun secret(words:String){if(!polling||isDestroyed)return;val text=TextView(this).apply{text=words;textSize=18f;setPadding(32,32,32,32);isSaveEnabled=false};val dialog=SumuwwVerticalCaptions.builder(this).setTitle(tr("24개 복구 단어")).setView(ScrollView(this).apply{addView(text)}).setPositiveButton(tr("확인"),null).create();dialog.window?.addFlags(WindowManager.LayoutParams.FLAG_SECURE);sensitive.add(dialog);val expire=Runnable{if(dialog.isShowing)dialog.dismiss()};dialog.setOnDismissListener{text.text="";sensitive.remove(dialog);main.removeCallbacks(expire)};dialog.show();main.postDelayed(expire,prefs.getInt("auto-lock-seconds",300)*1000L)}
 private fun prepare(to:String,amount:String){
  if(state?.optJSONObject("security")?.optBoolean("locked")==true){password("지갑 비밀번호"){pass->controls.execute{try{val next=JSONObject(PcRuntime.call("unlock_spending",pass));postUi{accept(next);prepare(to,amount)}}catch(e:Exception){fail(e)}}};return}

  if(preparing||transfers.isShutdown)return
  val fee=if(manualFee)"rate:"+feeDraft.trim() else "auto:"+listOf("slow","normal","fast")[feeMode]
  if(to.isBlank()||amount.isBlank()||(manualFee&&feeDraft.isBlank())){
   error=tr("받는 주소, 수량과 직접 설정한 수수료를 입력하세요.");render();return
  }
  preparing=true;val owner=epoch
  (getSystemService(INPUT_METHOD_SERVICE) as android.view.inputmethod.InputMethodManager).hideSoftInputFromWindow(window.decorView.windowToken,0)
  var quoteId:String?=null
  val dialog=SumuwwVerticalCaptions.builder(this).setTitle(tr("전송 확인"))
   .setMessage("$to\n$amount SMW\n"+tr("수수료 계산 및 거래 검증 중…"))
   .setNegativeButton(tr("취소"),null).setPositiveButton(tr("전송"),null).create()
  sensitive.add(dialog);dialog.setOnDismissListener{preparing=false;sensitive.remove(dialog)};dialog.show()
  val send=dialog.getButton(AlertDialog.BUTTON_POSITIVE);send.isEnabled=false
  send.setOnClickListener{val id=quoteId?:return@setOnClickListener;send.isEnabled=false;dialog.dismiss();submitPayment(id)}
  transfers.execute{try{
   val quote=JSONObject(PcRuntime.call("prepare_payment",to,amount,fee))
   postUi{
    if(!polling||epoch!=owner||!dialog.isShowing)return@postUi
    quoteId=quote.getString("quote_id")
    dialog.setMessage("$to\n${quote.optString("amount_smw")} SMW\n${tr("수수료")}: ${quote.optString("fee_smw")} SMW\n${tr("합계")}: ${quote.optString("total_smw")} SMW")
    send.isEnabled=true
   }
  }catch(e:Exception){postUi{if(dialog.isShowing&&epoch==owner){dialog.setMessage(e.message?:e.javaClass.simpleName);dialog.getButton(AlertDialog.BUTTON_NEGATIVE).text=tr("닫기")}}}}
 }
 private fun loadBlocks(height:String=""){
  if(worker.isShutdown)return
  blocksBusy=true;val request=++blocksRequest;val requestedOffset=blocksOffset
  worker.execute{try{
   val next=JSONObject(PcRuntime.call("block_history",requestedOffset.toString(),"50",height))
   postUi{blocksBusy=false;if(request==blocksRequest){blocks=next;blocksOffset=next.optInt("offset");error=null;if(page==15&&currentFocus?.tag!="blockSearch")render()}}
  }catch(e:Exception){postUi{blocksBusy=false;if(request==blocksRequest){error=e.message;if(page==15&&currentFocus?.tag!="blockSearch")render()}}}}
 }
 private fun loadHistory(){if(worker.isShutdown)return;if(address().isBlank()){history=JSONObject().put("transactions",org.json.JSONArray()).put("total",0);if(page==3)render();return};val request=++historyRequest;val requestedOffset=offset;val requestedFilter=filter;val requestedSearch=search;worker.execute{try{val next=JSONObject(PcRuntime.call("filtered_history",requestedOffset.toString(),"50",requestedFilter,requestedSearch));postUi{if(request==historyRequest){history=next;if(page==3)render()}}}catch(e:Exception){postUi{if(request==historyRequest){history=JSONObject().put("transactions",org.json.JSONArray()).put("total",0)} };fail(e)}}}
 private fun tour(index:Int){val guide=SumuwwTour.page(this,UiLanguage.code(this));if(index>=guide.steps.size)return;val step=guide.steps[index];SumuwwVerticalCaptions.builder(this).setTitle(step.title).setMessage(step.body).setNegativeButton(guide.skip,null).setPositiveButton(if(index==guide.steps.lastIndex)guide.done else guide.next){_,_->tour(index+1)}.show()}
 override fun onActivityResult(request:Int,result:Int,data:Intent?){super.onActivityResult(request,result,data);if(result!=RESULT_OK)return;val uri=data?.data?:return
  if(request==101)worker.execute{try{val latest=JSONObject(PcRuntime.call("status"));val selected=latest.optJSONObject("wallet")?:error("Select a wallet before backup");val wallet=File(selected.getString("path"));require(wallet.isFile&&wallet.length() in 1..4096);val raw=wallet.readBytes();require(raw.size in 1..4096);contentResolver.openOutputStream(uri)?.use{it.write(raw)}?:error("Backup destination unavailable");postUi{Toast.makeText(this,tr("암호화 지갑 백업을 저장했습니다."),Toast.LENGTH_SHORT).show()}}catch(e:Exception){fail(e)}}
  if(request==102)password("지갑 비밀번호"){pass->worker.execute{var temp:File?=null;try{temp=File.createTempFile("restore-",".json",File(filesDir,"sumuww"));val input=contentResolver.openInputStream(uri)?:error("Backup unavailable");val raw=input.use{WalletBackupIo.read(it)};temp.writeBytes(raw);PcRuntime.call("restore_wallet",temp.absolutePath,pass);val next=JSONObject(PcRuntime.call("status"));postUi{accept(next)}}catch(e:Exception){fail(e)}finally{temp?.delete()}}}
 }
}
