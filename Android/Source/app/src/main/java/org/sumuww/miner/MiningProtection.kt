package org.sumuww.miner
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.BatteryManager
import android.os.Build
import android.os.PowerManager
/** Device protection only; never alters SMW difficulty or rewards. */
internal object MiningProtection {
 data class Reading(val percent:Int,val temperature:Int,val charging:Boolean,val thermal:Int,val reason:String?)
 fun reason(percent:Int,temperature:Int,charging:Boolean,thermal:Int,minimum:Int,chargingOnly:Boolean):String?=when{
  thermal>=3 || temperature>=450 -> "과열 보호로 채굴을 중지했습니다."
  percent>=0 && percent<=minimum -> "배터리 부족으로 채굴을 중지했습니다."
  chargingOnly&&!charging -> "충전 중에만 채굴하도록 설정되어 있습니다."
  else->null
 }
 fun read(context:Context,battery:Intent?=null):Reading {
  val data=battery?:context.registerReceiver(null,IntentFilter(Intent.ACTION_BATTERY_CHANGED))
  val level=data?.getIntExtra(BatteryManager.EXTRA_LEVEL,-1)?:-1
  val scale=data?.getIntExtra(BatteryManager.EXTRA_SCALE,100)?:100
  val percent=if(level>=0&&scale>0)level*100/scale else -1
  val temp=data?.getIntExtra(BatteryManager.EXTRA_TEMPERATURE,0)?:0
  val charging=(data?.getIntExtra(BatteryManager.EXTRA_PLUGGED,0)?:0)!=0
  val thermal=if(Build.VERSION.SDK_INT>=29)context.getSystemService(PowerManager::class.java).currentThermalStatus else 0
  val prefs=context.getSharedPreferences("sumuww-ui",0)
  return Reading(percent,temp,charging,thermal,reason(percent,temp,charging,thermal,prefs.getInt("battery-limit",15),prefs.getBoolean("charging-only",false)))
 }
}
