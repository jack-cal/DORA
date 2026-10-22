package org.sumuww.miner

import android.app.AlertDialog
import android.graphics.Bitmap
import android.graphics.Canvas
import android.text.Spanned
import android.text.style.ReplacementSpan
import android.view.View
import android.widget.CheckBox
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.*
import org.junit.Test

class VerticalMongolianTest {
 @Test fun maximumBalanceFitsWithoutLosingDigits(){
  val inst=InstrumentationRegistry.getInstrumentation();val context=inst.targetContext
  val original=UiLanguage.code(context);SumuwwConsent.accept(context)
  val activity=inst.startActivitySync(android.content.Intent(context,MainActivity::class.java).addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK)) as MainActivity
  Thread.sleep(1000);inst.waitForIdleSync()
  try{
   inst.runOnMainSync{
    inst.callActivityOnPause(activity)
    UiLanguage.set(context,"mn-Mong")
    val screens=MainActivity::class.java.getDeclaredField("screens").apply{isAccessible=true}.get(activity) as SumuwwScreens
    val model=SumuwwScreens::class.java.getDeclaredField("state").apply{isAccessible=true}.get(screens) as SumuwwScreens.Model
    val fixture=org.json.JSONObject().put("wallet",org.json.JSONObject().put("total_smw","17999999.97690000"))
    screens.render(model.copy(page=0,languageName=UiLanguage.languages.getValue("mn-Mong")))
    screens.render(model.copy(page=1,languageName=UiLanguage.languages.getValue("mn-Mong"),status=fixture,statusUnavailable=false,error=null))
   }
   inst.waitForIdleSync()
   inst.runOnMainSync{
    fun find(v:View):android.widget.TextView?{
     if(v is android.widget.TextView&&v.text.toString()=="17,999,999.9769 SMW")return v
     if(v is android.view.ViewGroup)for(i in 0 until v.childCount)find(v.getChildAt(i))?.let{return it}
     return null
    }
    val amount=find(activity.window.decorView)
    assertNotNull("Maximum balance missing",amount)
    assertTrue("Maximum balance digits clipped",amount!!.paint.measureText(amount.text.toString())<=amount.width-amount.totalPaddingLeft-amount.totalPaddingRight+1)
   }
  }finally{inst.runOnMainSync{UiLanguage.set(context,original);activity.finish()}}
 }
 @Test fun connectedVerticalTextAndNativeDialogActions() {
  val inst=InstrumentationRegistry.getInstrumentation()
  val context=inst.targetContext
  val original=UiLanguage.code(context)
  try {
   inst.runOnMainSync {
    UiLanguage.set(context,"mn-Mong")
    val label=SumuwwVerticalTextView(context).apply { text="ᠮᠣᠩᠭᠣᠯ";textSize=24f }
    label.measure(View.MeasureSpec.makeMeasureSpec(240,View.MeasureSpec.AT_MOST), View.MeasureSpec.makeMeasureSpec(0,View.MeasureSpec.UNSPECIFIED))
    label.layout(0,0,label.measuredWidth,label.measuredHeight)
    assertTrue(label.usesVerticalMongolian)
    assertTrue(label.height>label.width)
    val image=Bitmap.createBitmap(label.width,label.height,Bitmap.Config.ARGB_8888)
    label.draw(Canvas(image))
    val pixels=IntArray(image.width*image.height);image.getPixels(pixels,0,image.width,0,0,image.width,image.height)
    assertTrue("Empty vertical raster",pixels.count{it ushr 24!=0}>20)
    image.recycle()
    var clicked=false
    label.setOnClickListener{clicked=true};label.performClick();assertTrue(clicked)
    val check=CheckBox(context);SumuwwVerticalCaptions.watch(check);check.text="ᠮᠣᠩᠭᠣᠯ"
    assertTrue(check.text is Spanned)
    assertEquals(1,(check.text as Spanned).getSpans(0,check.text.length,ReplacementSpan::class.java).size)
    check.performClick();assertTrue(check.isChecked)
    label.text="1.25000000 SMW"
    assertFalse(label.usesVerticalMongolian)
   }
   SumuwwConsent.accept(context)
   val activity=inst.startActivitySync(android.content.Intent(context,MainActivity::class.java).addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK)) as MainActivity
   Thread.sleep(1000);inst.waitForIdleSync()
   var dialog:AlertDialog?=null
   var accepted=false
   try {
    inst.runOnMainSync { dialog=SumuwwVerticalCaptions.builder(activity).setTitle("ᠮᠣᠩᠭᠣᠯ").setMessage("ᠮᠣᠩᠭᠣᠯ ᠬᠡᠯᠡ").setPositiveButton("OK"){_,_->accepted=true}.show() }
    inst.waitForIdleSync()
    inst.runOnMainSync {
     val shown=dialog!!
     val message=shown.findViewById<android.widget.TextView>(android.R.id.message)
     assertTrue(message.text is Spanned)
     shown.setMessage("ᠬᠡᠯᠡ ᠮᠣᠩᠭᠣᠯ")
     assertTrue(message.text is Spanned)
     shown.getButton(AlertDialog.BUTTON_POSITIVE).performClick()
    }
    inst.waitForIdleSync()
    inst.runOnMainSync { assertTrue(accepted) }
   }finally{inst.runOnMainSync{dialog?.dismiss();activity.finish()}}
  }finally{inst.runOnMainSync{UiLanguage.set(context,original)}}
 }
}
