package org.sumuww.miner

import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.net.Uri
import android.os.Handler
import android.os.Looper
import org.json.JSONObject
import java.net.URI
import java.net.HttpURLConnection
import java.net.URL
import java.io.ByteArrayOutputStream
import java.util.concurrent.Executors

/** Explicit, read-only GitHub lookup. Installation remains a user action. */
internal object SumuwwUpdateSource {
 const val MANIFEST="https://raw.githubusercontent.com/jack-cal/SUMUWW/main/updates.json"
 const val RELEASES="https://github.com/jack-cal/SUMUWW/releases"
 const val MAX_BYTES=65536
 data class Release(val version:String,val url:String,val available:Boolean)
 fun releaseUrl(text:String):String {
  require(text.length<=2048)
  val u=URI(text)
  require(u.scheme=="https"&&u.host=="github.com"&&u.rawUserInfo==null&&u.fragment==null&&u.rawQuery==null&&(u.port==-1||u.port==443))
  require(Regex("/jack-cal/SUMUWW/releases(?:/tag/[A-Za-z0-9._-]+)?").matches(u.rawPath?:""))
  return text
 }
 fun version(value:String):List<Int>{
  val m=Regex("(\\d{1,5})\\.(\\d{1,5})\\.(\\d{1,5})(?:-[A-Za-z0-9._-]+)?").matchEntire(value)?:error("Invalid update version")
  return (1..3).map{m.groupValues[it].toInt()}
 }
 fun parse(raw:ByteArray,installed:String):Release {
  require(raw.size<=MAX_BYTES)
  val manifest=JSONObject(raw.toString(Charsets.UTF_8));require(manifest.get("schema_version") is Int&&manifest.getInt("schema_version")==1)
  val row=manifest.getJSONObject("android");val latest=row.getString("version");val a=version(latest);val b=version(installed)
  val difference=(0..2).firstOrNull{a[it]!=b[it]}
  return Release(latest,releaseUrl(row.getString("release_url")),difference!=null&&a[difference]>b[difference])
 }
}

internal class SumuwwUpdates(private val activity:Activity,private val visible:()->Boolean) {
 private var dialog:AlertDialog?=null
 private val main=Handler(Looper.getMainLooper())
 private val worker=Executors.newSingleThreadExecutor{r->Thread(r,"sumuww-update-check").apply{isDaemon=true}}
 @Volatile private var connection:HttpURLConnection?=null
 @Volatile private var generation=0
 private fun tr(s:String)=UiLanguage.text(activity,s)
 fun cancel(){generation++;connection?.disconnect();connection=null;dialog?.dismiss();dialog=null}
 fun close(){cancel();worker.shutdownNow()}
 private fun message(text:String,url:String?=null){
  if(!visible()||activity.isDestroyed||activity.isFinishing)return
  dialog?.dismiss()
  dialog=SumuwwVerticalCaptions.builder(activity).setTitle(tr("업데이트 확인")).setMessage(text)
   .setNegativeButton(tr("닫기")){_,_->cancel()}.apply{
    if(url!=null)setPositiveButton(tr("다운로드 페이지 열기")){_,_->
     try{activity.startActivity(Intent(Intent.ACTION_VIEW,Uri.parse(SumuwwUpdateSource.releaseUrl(url))).addCategory(Intent.CATEGORY_BROWSABLE))}
     catch(_:Exception){message(tr("업데이트 페이지를 열 수 없습니다."))}
    }
   }.create().apply{setOnCancelListener{cancel()};show()}
 }
 fun check(){
  cancel();if(worker.isShutdown)return
  val epoch=generation
  message(tr("업데이트 확인 중…"),SumuwwUpdateSource.RELEASES)
  worker.execute{
   var current:HttpURLConnection?=null
   try{
    if(generation!=epoch)return@execute
    val config=activity.assets.open("update_config.json").bufferedReader().use{JSONObject(it.readText())}
    require(config.getString("manifest_url")==SumuwwUpdateSource.MANIFEST)
    current=URL(SumuwwUpdateSource.MANIFEST).openConnection() as HttpURLConnection
    connection=current
    if(generation!=epoch)return@execute
    current.instanceFollowRedirects=false;current.connectTimeout=7000;current.readTimeout=7000
    current.setRequestProperty("User-Agent","SUMUWW-update-check");current.setRequestProperty("Accept","application/json")
    require(current.responseCode==200)
    val raw=current.inputStream.use{stream->
     val out=ByteArrayOutputStream();val buffer=ByteArray(4096)
     while(true){val n=stream.read(buffer);if(n<0)break;require(out.size()+n<=SumuwwUpdateSource.MAX_BYTES);out.write(buffer,0,n)}
     out.toByteArray()
    }
    val installed=activity.packageManager.getPackageInfo(activity.packageName,0).versionName?:error("Missing installed version")
    val release=SumuwwUpdateSource.parse(raw,installed)
    main.post{if(generation==epoch)message(tr(if(release.available)"새 버전이 있습니다." else "새 업데이트가 없습니다.")+"\nSUMUWW "+installed+"\nGitHub "+release.version,release.url)}
   }catch(_:Exception){main.post{if(generation==epoch)message(tr("업데이트 정보를 가져올 수 없습니다."),SumuwwUpdateSource.RELEASES)}}
   finally{current?.disconnect();if(connection===current)connection=null}
  }
 }
}
