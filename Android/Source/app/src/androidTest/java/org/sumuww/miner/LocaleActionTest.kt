package org.sumuww.miner

import android.content.Intent
import android.view.View
import android.view.ViewGroup
import android.widget.EditText
import android.widget.CheckBox
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.*
import org.junit.Test

class LocaleActionTest {
 @Test fun navigationValidationFeeAndDraftsInEveryLanguage(){
  val inst=InstrumentationRegistry.getInstrumentation();val context=inst.targetContext
  val original=UiLanguage.code(context);SumuwwConsent.accept(context)
  val activity=inst.startActivitySync(Intent(context,MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) as MainActivity
  Thread.sleep(1000);inst.waitForIdleSync()
  val type=MainActivity::class.java
  val render=type.getDeclaredMethod("render").apply{isAccessible=true}
  val page=type.getDeclaredField("page").apply{isAccessible=true}
  val error=type.getDeclaredField("error").apply{isAccessible=true}
  val recipient=type.getDeclaredField("recipient").apply{isAccessible=true}
  val quantity=type.getDeclaredField("quantity").apply{isAccessible=true}
  val screens=type.getDeclaredField("screens").apply{isAccessible=true}.get(activity) as SumuwwScreens
  fun find(v:View,caption:String):View?{
   if(v.isClickable&&v.contentDescription?.toString()==UiLanguage.text(context,caption))return v
   if(v is ViewGroup)for(i in 0 until v.childCount)find(v.getChildAt(i),caption)?.let{return it}
   return null
  }
  try{
   for(code in UiLanguage.languages.keys){
    inst.runOnMainSync{
     UiLanguage.set(context,code);page.setInt(activity,0);error.set(activity,null);render.invoke(activity)
     screens.tabs[2].performClick();assertEquals("wallet navigation $code",2,page.getInt(activity))
     find(screens.content,"보내기")!!.performClick();assertEquals("send navigation $code",5,page.getInt(activity))
     screens.content.findViewWithTag<EditText>("sendAddress").setText("owned-invalid-draft")
     screens.content.findViewWithTag<EditText>("sendAmount").setText("")
     val manual=screens.content.findViewWithTag<CheckBox>("manualFee")
     manual.performClick();assertEquals(manual.isChecked,screens.content.findViewWithTag<EditText>("sendFee").parent.let{(it as View).visibility==View.VISIBLE})
     // Empty amount is rejected locally; this cannot submit a payment.
     find(screens.content,"다음")!!.performClick();assertNotNull("validation $code",error.get(activity))
     assertEquals("owned-invalid-draft",recipient.get(activity));assertEquals("",quantity.get(activity))
     for(back in listOf("en",code)){
      UiLanguage.set(context,back);render.invoke(activity)
      assertEquals("draft after return $code", "owned-invalid-draft",screens.content.findViewWithTag<EditText>("sendAddress").text.toString())
      assertEquals("",screens.content.findViewWithTag<EditText>("sendAmount").text.toString())
     }
     page.setInt(activity,0);error.set(activity,null);render.invoke(activity)
     for(index in listOf(1,2,3,0)){
      screens.tabs[index].performClick();assertEquals("tab $code/$index",intArrayOf(0,1,2,4)[index],page.getInt(activity))
     }
    }
    inst.waitForIdleSync()
   }
  }finally{inst.runOnMainSync{UiLanguage.set(context,original);activity.finish()}}
 }
}
