package org.sumuww.miner

import android.app.Activity
import android.content.Context
import android.content.res.ColorStateList
import android.view.View
import android.widget.*
import org.json.JSONObject

/** UI/service admission only. Does not alter consensus, wallets or mining. */
object SumuwwConsent {
 const val REVISION=3
 private fun prefs(context:Context)=context.getSharedPreferences("sumuww-consent",Context.MODE_PRIVATE)
 fun accepted(context:Context):Boolean {
  val p=prefs(context)
  val valid=p.getInt("revision",0) in 2..REVISION&&p.getBoolean("mining-background",false)&&p.getBoolean("network",false)
  if(valid&&p.getInt("revision",0)!=REVISION)accept(context)
  return valid
 }
 fun accept(context:Context){
  check(prefs(context).edit().clear().putInt("revision",REVISION).putBoolean("mining-background",true)
   .putBoolean("network",true).putLong("accepted-at",System.currentTimeMillis()).commit())
 }
 fun revoke(context:Context){check(prefs(context).edit().clear().commit())}
 fun text(context:Context,key:String):String {
  val texts=JSONObject(context.assets.open("consent_ui.json").bufferedReader().use{it.readText()})
  return texts.optJSONObject(UiLanguage.code(context))?.optString(key)?.takeIf{it.isNotBlank()}
   ?:texts.getJSONObject("en").getString(key)
 }
}

fun sumuwwConsentView(activity:Activity,palette:SumuwwTheme.Palette,dark:Boolean,managing:Boolean,
 busy:Boolean,onSave:()->Unit,onRevoke:()->Unit,onExit:()->Unit,onLanguage:()->Unit):View {
 val ui=SumuwwUiComponents(activity,palette,dark)
 fun t(key:String)=SumuwwConsent.text(activity,key)
 val page=ui.column().apply{setPadding(ui.dp(20),ui.dp(20),ui.dp(20),ui.dp(32));background=ui.rounded(ui.background,0)}
 page.addView(ui.label(t("title"),24f,ui.ink,true),ui.params(bottom=12))
 page.addView(ui.label(t("intro"),14f,ui.muted),ui.params(bottom=16))
 page.addView(ui.SumuwwPrimaryButton(UiLanguage.languages[UiLanguage.code(activity)]?:"English",onLanguage),ui.params(bottom=24))
 val required=mutableListOf<CheckBox>()
 for(key in listOf("mining","network")){
  val check=CheckBox(activity).apply{SumuwwVerticalCaptions.watch(this);
   text=t(key);textSize=15f;setTextColor(ui.ink);buttonTintList=ColorStateList.valueOf(ui.accent)
   isChecked=managing;isEnabled=!busy;tag="consent-$key";setPadding(0,ui.dp(8),0,ui.dp(8))
  }
  required.add(check);page.addView(check,ui.params(bottom=12))
 }
 val save=ui.SumuwwPrimaryButton(t(if(managing)"save" else "continue")){onSave()}.apply{tag="consent-continue"}
 fun update(){save.isEnabled=!busy&&required.all{it.isChecked};save.alpha=if(save.isEnabled)1f else .45f}
 required.forEach{it.setOnCheckedChangeListener{_,_->update()}};update()
 page.addView(save,ui.params(bottom=12))
 if(managing)page.addView(ui.SumuwwPrimaryButton(t("revoke"),onRevoke).apply{isEnabled=!busy;tag="consent-revoke"},ui.params(bottom=12))
 page.addView(ui.SumuwwPrimaryButton(t(if(managing)"close" else "exit"),onExit).apply{tag="consent-exit"})
 if(busy)page.addView(ui.label(t("stopping"),14f,ui.muted),ui.params(top=16))
 val scroll=ScrollView(activity).apply{isFillViewport=true;clipToPadding=true;addView(page)}
 return FrameLayout(activity).apply{
  tag="sumuww-consent-screen";clipChildren=true;clipToPadding=true
  setBackgroundColor(ui.background);addView(scroll,FrameLayout.LayoutParams(-1,-1))
  layoutDirection=if(UiLanguage.code(activity) in setOf("ar", "ur"))View.LAYOUT_DIRECTION_RTL else View.LAYOUT_DIRECTION_LTR
  setOnApplyWindowInsetsListener{view,insets->
   if(android.os.Build.VERSION.SDK_INT>=30){
    val bars=activity.windowManager.currentWindowMetrics.windowInsets.getInsetsIgnoringVisibility(android.view.WindowInsets.Type.systemBars() or android.view.WindowInsets.Type.displayCutout())
    view.setPadding(bars.left,bars.top,bars.right,bars.bottom)
   }else view.setPadding(insets.systemWindowInsetLeft,insets.systemWindowInsetTop,insets.systemWindowInsetRight,insets.systemWindowInsetBottom)
   insets
  }
  post{rootWindowInsets?.let{dispatchApplyWindowInsets(it)}}
 }
}
