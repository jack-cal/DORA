package org.sumuww.miner
import androidx.test.platform.app.InstrumentationRegistry
import android.content.Intent
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
class StatusProtectionTest {
 @Test fun failedStatusMustNotShowPreviousReadyPeer(){
  val inst=InstrumentationRegistry.getInstrumentation();val context=inst.targetContext
  SumuwwConsent.accept(context)
  val activity=inst.startActivitySync(Intent(context,MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) as MainActivity
  try{
   val type=MainActivity::class.java
   val accept=type.getDeclaredMethod("accept",JSONObject::class.java).apply{isAccessible=true}
   val render=type.getDeclaredMethod("render").apply{isAccessible=true}
   val failed=type.getDeclaredField("pollError").apply{isAccessible=true}
   val screens=type.getDeclaredField("screens").apply{isAccessible=true}.get(activity) as SumuwwScreens
   val sync=SumuwwScreens::class.java.getDeclaredMethod("syncState").apply{isAccessible=true}
   val node=SumuwwScreens::class.java.getDeclaredMethod("node").apply{isAccessible=true}
   inst.runOnMainSync{
    accept.invoke(activity,JSONObject().put("node",JSONObject().put("peers",1).put("mining_ready",true)))
    assertEquals(UiLanguage.text(context,"준비됨"),sync.invoke(screens))
    failed.setBoolean(activity,true);render.invoke(activity)
    assertNotEquals("Failed polling still shows the previous peer as ready",UiLanguage.text(context,"준비됨"),sync.invoke(screens))
    assertNull("Failed polling still exposes previous peer count",node.invoke(screens))
    accept.invoke(activity,JSONObject().put("node",JSONObject().put("peers",0).put("mining_ready",false)))
    assertFalse(failed.getBoolean(activity))
    assertEquals(0,(node.invoke(screens) as JSONObject).getInt("peers"))
    accept.invoke(activity,JSONObject().put("node",JSONObject().put("peers",1).put("mining_ready",true)))
    type.getDeclaredField("lastStatusAt").apply{isAccessible=true}.setLong(activity,android.os.SystemClock.elapsedRealtime()-16000)
    type.getDeclaredMethod("checkStatusFreshness").apply{isAccessible=true}.invoke(activity)
    assertTrue("Expired status is still marked fresh",failed.getBoolean(activity))
    assertNull(node.invoke(screens))
    type.getDeclaredMethod("action",String::class.java,String::class.java,String::class.java).apply{isAccessible=true}.invoke(activity,"page","12","")
    accept.invoke(activity,JSONObject().put("node",JSONObject().put("peers",0).put("mining_ready",false)))
    assertEquals("Fresh form status did not clear unavailable state",0,(node.invoke(screens) as JSONObject).getInt("peers"))
   }
  }finally{inst.runOnMainSync{activity.finish()}}
 }
 @Test fun configuredBatteryBoundary(){
  assertNull(MiningProtection.reason(17,250,false,0,15,false))
  assertNotNull(MiningProtection.reason(15,250,false,0,15,false))
  assertNotNull(MiningProtection.reason(14,250,false,0,15,false))
  assertNotNull(MiningProtection.reason(17,250,false,0,20,false))
 }
}
