package org.sumuww.miner
import android.app.*
import android.content.Intent
import android.content.IntentFilter
import android.content.BroadcastReceiver
import android.content.Context
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import android.net.wifi.WifiManager
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import org.json.JSONObject

/** Fresh Android process-lifetime host. No networking/mining algorithm lives here. */
class PcNodeService:Service() {
 private val worker=Executors.newSingleThreadScheduledExecutor()
 private val safety=Executors.newSingleThreadExecutor()
 private val checkingSafety=java.util.concurrent.atomic.AtomicBoolean(false)
 private var thermalListener:PowerManager.OnThermalStatusChangedListener?=null
 private var receiverRegistered=false
 private var lastCompletion=""
 private var lastConnected=0L
 private var lastMiningDiagnostic=0L
 private var lastConnectionError=""
 private val batteryReceiver=object:BroadcastReceiver(){override fun onReceive(context:Context?,intent:Intent?){checkProtection(intent)}}
 private fun checkProtection(battery:Intent?=null){
  if(closing||safety.isShutdown)return
  val reading=MiningProtection.read(this,battery);val reason=reading.reason?:return
  if(!checkingSafety.compareAndSet(false,true))return
  try{safety.execute{try{
   if(!closing&&JSONObject(PcRuntime.call("status")).optJSONObject("mobile_batch")?.optBoolean("running")==true){
    PcRuntime.call("stop_mining_for_safety",reason)
    if(!closing)notificationManager.notify(42,notification(UiLanguage.text(this,reason)))
   }
  }catch(e:Exception){android.util.Log.w("SumuwwPc042","Protection check unavailable",e)}finally{checkingSafety.set(false)}}}catch(_:java.util.concurrent.RejectedExecutionException){checkingSafety.set(false)}
 }
 private var multicast:WifiManager.MulticastLock?=null
 private var wake:PowerManager.WakeLock?=null
 private val powerGuard=Any()
 @Volatile private var closing=false
 @Volatile private var runtimeGeneration=0L
 private lateinit var notificationManager:NotificationManager
 private fun notification(text:String):Notification {
  val open=PendingIntent.getActivity(this,0,Intent(this,MainActivity::class.java),PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
  val stop=PendingIntent.getService(this,1,Intent(this,PcNodeService::class.java).setAction("STOP_SUMUWW_NODE"),PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
  return Notification.Builder(this,"sumuww-node").setSmallIcon(R.drawable.nav_mining).setContentTitle(UiLanguage.text(this,"SUMUWW")).setContentText(text).setContentIntent(open).setOngoing(true).addAction(Notification.Action.Builder(null,"Stop",stop).build()).build()
 }
 override fun onCreate(){
  super.onCreate()
  if(!SumuwwConsent.accepted(this)){closing=true;stopSelf();return}
  notificationManager=getSystemService(NotificationManager::class.java)
  notificationManager.createNotificationChannel(NotificationChannel("sumuww-node","SUMUWW node",NotificationManager.IMPORTANCE_LOW))
  startForeground(42,notification("Starting node"))
  try{multicast=(applicationContext.getSystemService(WIFI_SERVICE) as? WifiManager)?.createMulticastLock("sumuww-pc042")?.apply{setReferenceCounted(false);acquire()}}catch(e:Exception){android.util.Log.w("SumuwwPc042","LAN multicast lock unavailable",e)}
  wake=getSystemService(PowerManager::class.java).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,"SMW:ActiveMining").apply{setReferenceCounted(false)}
  if(Build.VERSION.SDK_INT>=33)registerReceiver(batteryReceiver,IntentFilter(Intent.ACTION_BATTERY_CHANGED),Context.RECEIVER_NOT_EXPORTED)
  else registerReceiver(batteryReceiver,IntentFilter(Intent.ACTION_BATTERY_CHANGED))
  receiverRegistered=true
  if(Build.VERSION.SDK_INT>=29){thermalListener=PowerManager.OnThermalStatusChangedListener{checkProtection()};getSystemService(PowerManager::class.java).addThermalStatusListener(thermalListener!!)}
  worker.execute{try{PcRuntime.start(this);runtimeGeneration=PcRuntime.generation;if(closing)PcRuntime.stopIfStarted(runtimeGeneration)}catch(e:Exception){android.util.Log.e("SumuwwPc042","Node startup failed",e);if(!closing)notificationManager.notify(42,notification("Node startup failed — open SMW"))}}
  worker.scheduleWithFixedDelay({
   if(!closing)try{
    checkProtection()
    val status=JSONObject(PcRuntime.call("status"));val batch=status.optJSONObject("mobile_batch");val node=status.optJSONObject("node")
    val mining=batch?.optBoolean("running",false)==true
    val diagnosticNow=android.os.SystemClock.elapsedRealtime()
    if(mining&&diagnosticNow-lastMiningDiagnostic>=30000){
     lastMiningDiagnostic=diagnosticNow
     android.util.Log.i("SumuwwMiningMetrics",JSONObject().put("metrics",status.optJSONObject("mobile_mining")).put("elapsed_seconds",batch?.optDouble("elapsed_seconds",0.0)).put("network_wait_seconds",batch?.optDouble("network_wait_seconds",0.0)).put("network_pauses",batch?.optInt("network_pauses",0)).put("completed",batch?.optInt("completed",0)).put("height",node?.optInt("height",0)).put("next_bits",node?.optString("next_bits")).put("state",status.optJSONObject("mining")?.optString("state")).toString())
    }
    if((node?.optInt("peers",0)?:0)>0)lastConnected=System.currentTimeMillis()
    PcRuntime.diagnostics=JSONObject().put("last_connected",if(lastConnected==0L)"—" else java.text.DateFormat.getDateTimeInstance().format(java.util.Date(lastConnected))).put("last_error",lastConnectionError.ifBlank{"—"}).put("peers",node?.optInt("peers",0)?:0).put("sync_state",node?.optString("sync_state","stopped"))
    val completion=batch?.optString("started_at","")?:""
    if(!mining&&completion.isNotEmpty()&&completion!="null"&&completion!=lastCompletion&&batch?.optInt("completed",0)==batch?.optInt("target",-1)){
     lastCompletion=completion
     if(getSharedPreferences("sumuww-ui",0).getBoolean("alert-mining",true)){
     TransferAlerts(this).result("채굴 목표 완료","${batch?.optInt("completed")} "+UiLanguage.text(this,"블록"))
     notificationManager.createNotificationChannel(NotificationChannel("dora-mining-complete",UiLanguage.text(this,"채굴 완료 알림"),NotificationManager.IMPORTANCE_DEFAULT))
     val open=PendingIntent.getActivity(this,0,Intent(this,MainActivity::class.java),PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
     try{notificationManager.notify(43,Notification.Builder(this,"dora-mining-complete").setSmallIcon(R.drawable.nav_mining).setContentTitle(UiLanguage.text(this,"채굴 목표 완료")).setContentText("${batch?.optInt("completed")} "+UiLanguage.text(this,"블록")).setContentIntent(open).setAutoCancel(true).build())}catch(_:SecurityException){}
     }
    }
    
    synchronized(powerGuard){
     if(!closing){
      // Renew while mining; a stuck monitor cannot keep the CPU awake forever.
      if(mining)wake?.acquire(120000L)
      else if(wake?.isHeld==true)wake?.release()
     }
    }
    val text=if(mining)"Mining ${batch?.optInt("completed")}/${batch?.optInt("target")}" else "Node · ${node?.optInt("peers",0)?:0} peers · ${node?.optString("sync_state","stopped")?:"stopped"}"
    if(!closing)notificationManager.notify(42,notification(text))
    val address=status.optJSONObject("wallet")?.optString("address","")?:""
    if(address.isNotBlank()){
     val alerts=TransferAlerts(this);val cutoff=alerts.cutoff(address,node?.optInt("height",0)?:0)
     val rows=org.json.JSONArray();var offset=0;var snapshot="";var snapshotHeight=0;var consistent=true
     while(!closing){
      val page=JSONObject(PcRuntime.call("transaction_history",offset.toString(),"200"))
      if(offset==0){snapshot=page.getString("tip");snapshotHeight=page.getInt("height")}
      else if(snapshot!=page.getString("tip")){consistent=false;break}
      val items=page.getJSONArray("transactions")
      for(i in 0 until items.length())rows.put(items.get(i))
      offset+=items.length()
      if(items.length()==0||offset>=page.getInt("total")||(0 until items.length()).any{val tx=items.getJSONObject(it);tx.optString("status")=="confirmed"&&tx.optInt("height")<cutoff})break
     }
     val sameWallet=JSONObject(PcRuntime.call("status")).optJSONObject("wallet")?.optString("address")==address
     val events=if(consistent&&sameWallet&&!closing)alerts.observe(address,snapshotHeight,rows,snapshot,cutoff)else emptyList()
     if(events.isNotEmpty()){
      notificationManager.createNotificationChannel(NotificationChannel("dora-transfers",UiLanguage.text(this,"거래 알림"),NotificationManager.IMPORTANCE_DEFAULT))
      events.forEach{event->
       val title=if(event.getString("stage") in listOf("revoked","recheck"))"거래 재확인 필요" else if(event.getBoolean("incoming")){if(event.getString("stage")=="pending")"입금 확인 대기" else "입금 확인"}else "송금 블록 확인"
       val open=PendingIntent.getActivity(this,0,Intent(this,MainActivity::class.java),PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
       val notice=Notification.Builder(this,"dora-transfers").setSmallIcon(R.drawable.nav_wallet).setContentTitle(UiLanguage.text(this,title)).setContentText(TransferAlerts.amount(kotlin.math.abs(event.getLong("net_amount")))+" SMW").setContentIntent(open).setAutoCancel(true).build()
       try{notificationManager.notify(event.getString("txid").hashCode(),notice)}catch(e:SecurityException){android.util.Log.w("SumuwwPc042","Transfer notification permission unavailable")}
      }
     }
    }
   }catch(e:Exception){
    if(!closing)notificationManager.notify(42,notification(UiLanguage.text(this,"상태 확인 불가")))
    lastConnectionError=e.message?:e.javaClass.simpleName
    PcRuntime.diagnostics=JSONObject(PcRuntime.diagnostics.toString()).put("last_error",lastConnectionError)
    android.util.Log.w("SumuwwPc042","Node status unavailable",e)
   }
  },1,5,TimeUnit.SECONDS)
 }
 override fun onStartCommand(intent:Intent?,flags:Int,startId:Int):Int {
  if(!SumuwwConsent.accepted(this)){stopSelf();return START_NOT_STICKY}
  if(intent?.action=="STOP_SUMUWW_NODE"&&!closing){closing=true;Thread{try{PcRuntime.call("stop")}catch(e:Exception){android.util.Log.w("SumuwwPc042","Stop request failed",e)}finally{stopSelf()}}.start()}
  return START_NOT_STICKY
 }
 override fun onBind(intent:Intent?):IBinder?=null
 override fun onDestroy(){
  closing=true
  if(receiverRegistered){unregisterReceiver(batteryReceiver);receiverRegistered=false}
  if(Build.VERSION.SDK_INT>=29)thermalListener?.let{getSystemService(PowerManager::class.java).removeThermalStatusListener(it)}
  safety.shutdownNow()
  multicast?.let{if(it.isHeld)it.release()}
  synchronized(powerGuard){wake?.let{if(it.isHeld)it.release()}}
  worker.shutdownNow()
  Thread{try{PcRuntime.stopIfStarted(runtimeGeneration)}catch(e:Exception){android.util.Log.w("SumuwwPc042","Shutdown incomplete",e)}}.start()
  super.onDestroy()
 }
}
