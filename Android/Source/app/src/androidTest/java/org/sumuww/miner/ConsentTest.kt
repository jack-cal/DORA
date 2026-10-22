package org.sumuww.miner

import android.content.Intent
import android.view.View
import android.widget.CheckBox
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class ConsentTest {
 @Test fun migrateExistingDeviceAndNetworkConsent(){
  val app=InstrumentationRegistry.getInstrumentation().targetContext
  val prefs=app.getSharedPreferences("sumuww-consent",android.content.Context.MODE_PRIVATE)
  prefs.edit().clear().putInt("revision",2).putBoolean("mining-background",true)
   .putBoolean("network",true).putBoolean("ad-supported-use",false)
   .putBoolean("personalized-preference",true).commit()
  assertTrue(SumuwwConsent.accepted(app))
  assertEquals(3,prefs.getInt("revision",0))
  assertFalse(prefs.contains("ad-supported-use"));assertFalse(prefs.contains("personalized-preference"))
  prefs.edit().putBoolean("network",false).commit()
  assertFalse(SumuwwConsent.accepted(app))
  SumuwwConsent.accept(app)
 }
 @Test fun admissionWithdrawalAndRestart(){
  val i=InstrumentationRegistry.getInstrumentation();val app=i.targetContext
  app.stopService(Intent(app,PcNodeService::class.java));PcRuntime.stopIfStarted();Thread.sleep(500)
  SumuwwConsent.revoke(app)
  try{PcRuntime.start(app);fail("Missing consent admitted runtime")}catch(_:IllegalStateException){}
  assertEquals(0L,PcRuntime.generation)
  val a=i.startActivitySync(Intent(app,MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) as MainActivity
  val root=a.window.decorView
  fun invoke(name:String,vararg args:Any){val m=MainActivity::class.java.declaredMethods.first{it.name==name};m.isAccessible=true;m.invoke(a,*args)}
  fun await(condition:()->Boolean){val until=System.currentTimeMillis()+20000;while(!condition()&&System.currentTimeMillis()<until)Thread.sleep(100);assertTrue(condition())}
  val marker=java.io.File(app.filesDir,"consent-preservation-fixture").apply{writeText("owned test marker")}
  try{
   i.runOnMainSync{
    assertNotNull(root.findViewWithTag<View>("sumuww-consent-screen"))
    val next=root.findViewWithTag<View>("consent-continue")
    assertFalse(next.isEnabled)
    assertNull(root.findViewWithTag<View>("consent-ads"))
    assertNull(root.findViewWithTag<View>("consent-personalized"))
    root.findViewWithTag<CheckBox>("consent-mining").isChecked=true
    root.findViewWithTag<CheckBox>("consent-network").isChecked=true
    assertTrue(next.isEnabled);next.performClick()
   }
   await{PcRuntime.generation>0};val generation=PcRuntime.generation
   i.runOnMainSync{
    invoke("showConsent",true)
    root.findViewWithTag<View>("consent-continue").performClick()
   }
   i.runOnMainSync{invoke("withdrawConsent")}
   await{PcRuntime.generation==0L}
   Thread.sleep(600);i.waitForIdleSync()
   assertFalse(SumuwwConsent.accepted(app));assertTrue(marker.exists())
   i.runOnMainSync{
    assertNotNull(root.findViewWithTag<View>("sumuww-consent-screen"))
    for(key in listOf("mining","network"))root.findViewWithTag<CheckBox>("consent-$key").isChecked=true
    assertTrue(root.findViewWithTag<View>("consent-continue").isEnabled)
    root.findViewWithTag<View>("consent-continue").performClick()
   }
   await{PcRuntime.generation>generation}
   val restarted=PcRuntime.generation;PcRuntime.stopIfStarted(generation)
   assertEquals(restarted,PcRuntime.generation)
  }finally{i.runOnMainSync{a.finish()};marker.delete();SumuwwConsent.accept(app)}
 }
 @Test fun translatedConsentAndAdmission(){
  val i=InstrumentationRegistry.getInstrumentation();val app=i.targetContext
  val catalog=org.json.JSONObject(app.assets.open("consent_ui.json").bufferedReader().use{it.readText()})
  assertEquals(UiLanguage.languages.size,catalog.length())
  for(language in UiLanguage.languages.keys){
   val texts=catalog.getJSONObject(language)
   for(key in listOf("ads","privacy","personalized","sdk","formats"))assertFalse(texts.has(key))
   for(key in listOf("title","mining","network","continue","revoke"))assertTrue(texts.getString(key).isNotBlank())
  }
  SumuwwConsent.accept(app)
 }
}
