package org.sumuww.miner

import android.content.Intent
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.Color
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.*
import org.junit.Test
import java.io.File

class LocaleBrandTest {
 @Test fun languageSwitchKeepsOneLauncherAndUsesUntintedArtwork() {
  val inst=InstrumentationRegistry.getInstrumentation()
  val context=inst.targetContext
  val original=UiLanguage.code(context)
  val activity=inst.startActivitySync(Intent(context,MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) as MainActivity
  val captures=File(context.getExternalFilesDir(null),"locale-brand-audit").apply{mkdirs()}
  try {
   for(code in listOf("ko","ar","en","ko","ar") + UiLanguage.languages.keys.filter{it !in setOf("ko","ar")}) {
    inst.runOnMainSync{UiLanguage.set(context,code)}
    inst.waitForIdleSync()
    val launchers=context.packageManager.queryIntentActivities(Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER).setPackage(context.packageName),0)
    assertEquals("One launcher for $code",1,launchers.size)
    assertTrue(launchers[0].activityInfo.name.endsWith(LocaleBrand.launcherName(code)))
    val resource=LocaleBrand.artwork(context)
    assertEquals(if(code=="ko")R.drawable.brand_ko else if(code=="ar")R.drawable.brand_ar else R.drawable.sumuww_icon,resource)
    val source=BitmapFactory.decodeResource(context.resources,resource,BitmapFactory.Options().apply{inScaled=false})
    assertEquals(0,Color.alpha(source.getPixel(0,0)))
    inst.runOnMainSync {
     val view=SumuwwBrandMark(activity,SumuwwThemeCalendar.resolve("gold"),false)
     view.layout(0,0,600,400)
     val result=Bitmap.createBitmap(600,400,Bitmap.Config.ARGB_8888)
     view.draw(Canvas(result))
     assertTrue((0 until result.height).any{y->(0 until result.width).any{x->Color.alpha(result.getPixel(x,y))>0}})
     if(code in setOf("ko","ar","en")) {
      for((theme,background) in listOf("light" to Color.WHITE,"dark" to Color.rgb(20,24,32))) {
       val preview=Bitmap.createBitmap(600,400,Bitmap.Config.ARGB_8888)
       preview.eraseColor(background)
       Canvas(preview).drawBitmap(result,0f,0f,null)
       File(captures,"$code-$theme.png").outputStream().use{preview.compress(Bitmap.CompressFormat.PNG,100,it)}
      }
     }
     if(code in setOf("ko","ar")) {
      val colors=SumuwwBrandMark::class.java.getDeclaredField("colors").apply{isAccessible=true}.get(view)
      assertNull("Preserve supplied colors under custom themes",colors)
     }
    }
   }
  } finally {
   inst.runOnMainSync{UiLanguage.set(context,original);activity.finish()}
  }
 }
}
