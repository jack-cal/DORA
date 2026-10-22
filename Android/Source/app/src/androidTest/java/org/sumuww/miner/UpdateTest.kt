package org.sumuww.miner
import org.junit.Assert.*
import org.junit.Test
import org.json.JSONObject
import androidx.test.platform.app.InstrumentationRegistry
import android.content.Intent
import android.app.AlertDialog

class UpdateTest {
 private fun rejected(url:String){try{SumuwwUpdateSource.releaseUrl(url);fail("Untrusted release URL accepted")}catch(e:Exception){}}
 private fun data(version:String)="""{"schema_version":1,"android":{"version":"$version","release_url":"https://github.com/jack-cal/SUMUWW/releases/tag/test-version"}}""".toByteArray()
 @Test fun numericVersionComparison(){
  assertTrue(SumuwwUpdateSource.parse(data("0.6.100"),"0.6.75-boundary9000-candidate").available)
  assertFalse(SumuwwUpdateSource.parse(data("0.6.75"),"0.6.75-boundary9000-candidate").available)
  assertFalse(SumuwwUpdateSource.parse(data("0.6.74"),"0.6.75").available)
  assertTrue(SumuwwUpdateSource.parse(data("0.7.0"),"0.6.75").available)
 }
 @Test fun unsafeRepositoryUrlsRejected(){
  assertEquals(SumuwwUpdateSource.RELEASES,SumuwwUpdateSource.releaseUrl(SumuwwUpdateSource.RELEASES))
  for(url in listOf("http://github.com/jack-cal/SUMUWW/releases","https://github.com.evil.example/jack-cal/SUMUWW/releases","https://user@github.com/jack-cal/SUMUWW/releases","https://github.com/jack-cal/OTHER/releases",SumuwwUpdateSource.RELEASES+"?fake=1",SumuwwUpdateSource.RELEASES+"#fake",SumuwwUpdateSource.RELEASES+"/tag/../evil"))rejected(url)
 }
 @Test fun responseBoundsAndSchema(){
  for(raw in listOf(ByteArray(65537),"{}".toByteArray(),data("invalid"),"""{"schema_version":true}""".toByteArray())){
   var failed=false;try{SumuwwUpdateSource.parse(raw,"0.6.75")}catch(_:Exception){failed=true};assertTrue(failed)
  }
 }
 @Test fun updateMessagesCoverAllLanguages(){
  val app=InstrumentationRegistry.getInstrumentation().targetContext
  val catalog=JSONObject(app.assets.open("mobile_ui.json").bufferedReader().use{it.readText()})
  val languages=catalog.getJSONArray("languages")
  for(key in listOf("업데이트 확인","다운로드 페이지 열기","업데이트 페이지를 열 수 없습니다.","업데이트 확인 중…","새 버전이 있습니다.","새 업데이트가 없습니다.","업데이트 정보를 가져올 수 없습니다.")){
   val texts=catalog.getJSONObject("strings").getJSONArray(key);assertEquals(languages.length(),texts.length())
   for(i in 0 until texts.length())assertTrue(texts.getString(i).isNotBlank())
  }
 }
 @Test fun updateButtonReadsPublishedGithubVersion(){
  val i=InstrumentationRegistry.getInstrumentation();val app=i.targetContext;SumuwwConsent.accept(app)
  if(android.os.Build.VERSION.SDK_INT>=33)i.uiAutomation.grantRuntimePermission(app.packageName,android.Manifest.permission.POST_NOTIFICATIONS)
  val a=i.startActivitySync(Intent(app,MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) as MainActivity
  var controller:SumuwwUpdates?=null
  try{
   Thread.sleep(1200)
   i.runOnMainSync{
    MainActivity::class.java.getDeclaredField("page").apply{isAccessible=true}.setInt(a,14)
    MainActivity::class.java.getDeclaredMethod("render").apply{isAccessible=true}.invoke(a)
    val button=a.window.decorView.findViewWithTag<android.view.View>("sumuww-update-check");assertNotNull(button);button.performClick()
    val delegate=MainActivity::class.java.getDeclaredField("updates\$delegate").apply{isAccessible=true}
    controller=(delegate.get(a) as Lazy<*>).value as SumuwwUpdates
   }
   val field=SumuwwUpdates::class.java.getDeclaredField("dialog").apply{isAccessible=true}
   val end=android.os.SystemClock.elapsedRealtime()+20000;var text=""
   while(android.os.SystemClock.elapsedRealtime()<end){
    i.runOnMainSync{val dialog=field.get(controller) as? AlertDialog;text=dialog?.findViewById<android.widget.TextView>(android.R.id.message)?.text?.toString()?:""}
    if(text.contains("\nGitHub "))break
    Thread.sleep(100)
   }
   assertTrue("Actual GitHub manifest lookup failed: $text",text.contains("\nGitHub "))
   i.runOnMainSync{controller!!.check();controller!!.cancel()}
   Thread.sleep(300)
   i.runOnMainSync{assertNull(field.get(controller))}
  }finally{i.runOnMainSync{controller?.close();a.finish()}}
 }
}
