package org.sumuww.miner
import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

/** Bounded presentation receipts. Original active-chain history is authoritative. */
internal class TransferAlerts(private val context:Context) {
 private val prefs=context.getSharedPreferences("sumuww-transfer-alerts",Context.MODE_PRIVATE)
 private fun queue(items:JSONArray):String {
  val bounded=JSONArray()
  for(i in (items.length()-MAX_QUEUE).coerceAtLeast(0) until items.length())bounded.put(items.get(i))
  return bounded.toString()
 }
 fun result(title:String,message:String){synchronized(guard){
  val items=JSONArray(prefs.getString("queue","[]")!!)
  items.put(JSONObject().put("title",title).put("message",message))
  prefs.edit().putString("queue",queue(items)).commit()
 }}
 fun recordSubmitted(wallet:String,txid:String){synchronized(guard){
  if(wallet.isBlank())return
  val data=JSONObject(prefs.getString(wallet,"{}")!!)
  val tracked=data.optJSONObject("tracked")?:JSONObject()
  val before=tracked.optJSONObject(txid)
  if(before?.optString("stage")!="confirmed"&&tracked.optString(txid)!="confirmed")tracked.put(txid,JSONObject().put("stage","submitted").put("time",System.currentTimeMillis()))
  data.put("tracked",trim(tracked,data.optInt("height",0)))
  prefs.edit().putString(wallet,data.toString()).commit()
 }}
 fun cutoff(wallet:String,height:Int):Int=synchronized(guard){
  val data=JSONObject(prefs.getString(wallet,"{}")!!)
  (minOf(data.optInt("height",height),height)-RECHECK_BLOCKS).coerceAtLeast(0)
 }
 private fun trim(tracked:JSONObject,height:Int):JSONObject {
  val entries=tracked.keys().asSequence().map{it to tracked.get(it)}.filter{(_,value)->
   if(value !is JSONObject)true else if(value.optString("stage")=="confirmed") value.optInt("height",height)>=height-RECHECK_BLOCKS
   else System.currentTimeMillis()-value.optLong("time",System.currentTimeMillis())<30L*86400000
  }.sortedByDescending{(_,value)->(value as? JSONObject)?.optLong("time",0)?:0}.take(MAX_TRACKED)
  return JSONObject().apply{entries.forEach{(id,value)->put(id,value)}}
 }
 fun observe(wallet:String,height:Int,rows:JSONArray,tip:String="",coverageFloor:Int?=null):List<JSONObject> {synchronized(guard){
  if(wallet.isBlank())return emptyList()
  val data=JSONObject(prefs.getString(wallet,"{}")!!)
  val first=!data.has("height");val previous=data.optInt("height",height)
  val tracked=data.optJSONObject("tracked")?:JSONObject()
  val events=mutableListOf<JSONObject>();val seen=mutableSetOf<String>()
  val ui=context.getSharedPreferences("sumuww-ui",0)
  fun emit(id:String,amount:Long,stage:String,confirmations:Int=0){
   val incoming=amount>0
   if(ui.getBoolean(if(incoming)"alert-incoming" else "alert-outgoing",true))events.add(JSONObject().put("wallet",wallet).put("txid",id).put("incoming",incoming).put("stage",stage).put("net_amount",amount).put("confirmations",confirmations))
  }
  for(i in 0 until rows.length()){
   val tx=rows.getJSONObject(i);if(tx.optBoolean("coinbase"))continue
   val amount=tx.optLong("net_amount");if(amount==0L)continue
   val id=tx.optString("txid");if(id.isBlank())continue;seen.add(id)
   val pending=tx.optString("status")=="pending";val stage=if(pending)"pending" else "confirmed"
   val before=tracked.optJSONObject(id)?.optString("stage")?:tracked.optString(id)
   val eligible=if(pending)amount>0&&!first||before in listOf("confirmed","revoked","recheck") else before.isNotBlank()||(!first&&tx.optInt("height")>previous)
   if(before!=stage&&eligible&&!(before=="submitted"&&pending))emit(id,amount,if(pending&&before=="confirmed")"recheck" else stage,tx.optInt("confirmations"))
   if(pending||eligible||first)tracked.put(id,JSONObject().put("stage",stage).put("height",tx.optInt("height",height)).put("amount",amount).put("time",System.currentTimeMillis()))
  }
  // Absence is meaningful only in a complete scan after a changed tip.
  if(coverageFloor!=null&&tip.isNotEmpty()&&tip!=data.optString("tip")){
   tracked.keys().asSequence().toList().forEach{id->
    val record=tracked.optJSONObject(id)?:return@forEach
    if(id !in seen&&record.optString("stage")=="confirmed"&&record.optInt("height")>=coverageFloor){
     emit(id,record.optLong("amount"),"revoked");record.put("stage","revoked").put("time",System.currentTimeMillis())
    }
   }
  }
  data.put("height",height).put("tracked",trim(tracked,height));if(tip.isNotEmpty())data.put("tip",tip)
  val items=JSONArray(prefs.getString("queue","[]")!!);events.forEach{items.put(it)}
  prefs.edit().putString(wallet,data.toString()).putString("queue",queue(items)).commit()
  return events
 }}
 fun take():JSONObject?=synchronized(guard){
  val items=JSONArray(prefs.getString("queue","[]")!!);if(items.length()==0)return@synchronized null
  val ui=context.getSharedPreferences("sumuww-ui",0)
  var selected:JSONObject?=null;val remaining=JSONArray()
  for(i in 0 until items.length()){
   val item=items.getJSONObject(i)
   val enabled=if(item.has("incoming"))ui.getBoolean(if(item.optBoolean("incoming"))"alert-incoming" else "alert-outgoing",true)else true
   if(enabled){if(selected==null)selected=item else remaining.put(item)}
  }
  prefs.edit().putString("queue",queue(remaining)).commit();selected
 }
 companion object {
  const val MAX_QUEUE=100;const val MAX_TRACKED=2048;const val RECHECK_BLOCKS=144
  private val guard=Any()
  fun amount(units:Long)=java.math.BigDecimal.valueOf(units).movePointLeft(8).stripTrailingZeros().toPlainString()
 }
}
