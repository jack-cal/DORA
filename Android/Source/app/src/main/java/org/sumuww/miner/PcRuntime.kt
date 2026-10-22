package org.sumuww.miner
import android.content.Context
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.io.File

/** New platform-only bridge. The original PC AppService owns every node operation. */
object PcRuntime {
 @Volatile var generation=0L
  private set
 private var nextGeneration=0L
 @Volatile private var visible=false
 fun setForeground(value:Boolean){
  visible=value
  if(Python.isStarted())Python.getInstance().getModule("pc_runtime").callAttr("set_foreground",value.toString())
 }
 @Synchronized fun start(context:Context):String {
  AndroidInterfaces.configure(context)
  PrivacyRuntime.configure(context)
  check(SumuwwConsent.accepted(context)){"Required SMW consent is missing"}
  if(!Python.isStarted())Python.start(AndroidPlatform(context.applicationContext))
  val module=Python.getInstance().getModule("pc_runtime")
  module.callAttr("set_foreground",visible.toString())
  module.callAttr("security_settings",context.getSharedPreferences("sumuww-ui",0).getInt("auto-lock-seconds",300).toString())
  val result=module.callAttr("start",File(context.filesDir,"sumuww").absolutePath).toString()
  if(!SumuwwConsent.accepted(context)){module.callAttr("stop");error("Required SMW consent was withdrawn")}
  if(generation==0L)generation=++nextGeneration
  return result
 }
 @Synchronized fun stopIfStarted(expectedGeneration:Long?=null){
  if(expectedGeneration!=null&&(expectedGeneration==0L||expectedGeneration!=generation))return
  if(Python.isStarted())Python.getInstance().getModule("pc_runtime").callAttr("stop")
  generation=0L
 }
 @Volatile var diagnostics=org.json.JSONObject()
 fun call(method:String,vararg args:String):String {
  val value=Python.getInstance().getModule("pc_runtime").callAttr(method,*args).toString()
  return if(method=="status")org.json.JSONObject(value).put("mobile_diagnostics",org.json.JSONObject(diagnostics.toString())).toString()else value
 }
}
