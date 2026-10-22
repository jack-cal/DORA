package org.sumuww.miner

import android.content.Intent
import android.graphics.Bitmap
import android.graphics.Canvas
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import java.io.File

class ArabicReadabilityTest {
 @Test fun readableArabicAndDetailedLogosFitSmallAndLargeScreens() {
  val inst=InstrumentationRegistry.getInstrumentation();val context=inst.targetContext
  val original=UiLanguage.code(context)
  val activity=inst.startActivitySync(Intent(context,MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) as MainActivity
  val folder=File(context.getExternalFilesDir(null),"arabic-readability-audit").apply{mkdirs()}
  try {
   inst.runOnMainSync {
    UiLanguage.set(context,"ar")
    for(widthDp in listOf(320,420))for(dark in listOf(false,true)) {
     val screens=SumuwwScreens(activity,{UiLanguage.text(context,it)},{_,_,_->})
     for(page in 0..14) {
      screens.render(SumuwwScreens.Model(page=page,status=null,history=null,historyOffset=0,historyFilter="all",cpu=1,
       elapsed="00:00:00",targetDraft="10000",sendAddress="",sendAmount="",error=null,tour=false,dark=dark,
       palette=SumuwwThemeCalendar.resolve("default"),themeMode=if(dark)"dark" else "light",languageName=UiLanguage.languages.getValue("ar")))
      val root=screens.appRoot
      val density=context.resources.displayMetrics.density
      val width=(widthDp*density).toInt();val height=(900*density).toInt()
      root.measure(View.MeasureSpec.makeMeasureSpec(width,View.MeasureSpec.EXACTLY),View.MeasureSpec.makeMeasureSpec(height,View.MeasureSpec.EXACTLY))
      root.layout(0,0,width,height)
      var arabicLabels=0
      fun check(v:View) {
       if(v.visibility!=View.VISIBLE)return
       if(v is TextView&&v.text.any{it in '\u0600'..'\u06ff'}) {
        arabicLabels++
        assertTrue("Small Arabic $widthDp/$page: ${v.text}",v.textSize/context.resources.displayMetrics.scaledDensity>=15.9f)
        v.layout?.let { layout ->
         assertTrue("Arabic clipped vertically $widthDp/$page: ${v.text}",layout.height<=v.height-v.totalPaddingTop-v.totalPaddingBottom+1)
         for(line in 0 until layout.lineCount)assertEquals("Arabic truncated $widthDp/$page: ${v.text}",0,layout.getEllipsisCount(line))
        }
       }
       if(v is SumuwwBrandMark&&page==1)assertTrue("Detailed mining logo too small",v.width>=176*density-1)
       if(v is ViewGroup)for(i in 0 until v.childCount)check(v.getChildAt(i))
      }
      check(root);assertTrue("Missing Arabic screen $page",arabicLabels>0)
      if(page in listOf(1,4,9,14)) {
       val bitmap=Bitmap.createBitmap(width,height,Bitmap.Config.ARGB_8888);root.draw(Canvas(bitmap))
       File(folder,"ar-$widthDp-${if(dark)"dark" else "light"}-$page.png").outputStream().use{bitmap.compress(Bitmap.CompressFormat.PNG,100,it)}
       bitmap.recycle()
      }
     }
    }
   }
  } finally {inst.runOnMainSync{UiLanguage.set(context,original);activity.finish()}}
 }
}
