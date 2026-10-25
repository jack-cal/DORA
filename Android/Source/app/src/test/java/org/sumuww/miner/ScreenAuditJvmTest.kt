package org.sumuww.miner

import android.app.Activity
import android.graphics.Bitmap
import android.graphics.Canvas
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import org.json.JSONObject
import org.json.JSONArray
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/** Real screen widgets, with a recording dispatch boundary and synthetic values only. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk=[35], qualifiers="w360dp-h800dp-xhdpi")
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class ScreenAuditJvmTest {
    private fun views(v:View):List<View> = listOf(v) + if(v is ViewGroup) (0 until v.childCount).flatMap { views(v.getChildAt(it)) } else emptyList()
    @Test fun allRoutesRenderAndClickableControlsDispatchIn34Languages() {
        val controller=Robolectric.buildActivity(Activity::class.java).create()
        val activity=controller.get()
        val calls=mutableListOf<String>()
        val screens=SumuwwScreens(activity,{UiLanguage.text(activity,it)},{a,b,c->calls.add("$a|$b|$c")})
        activity.setContentView(screens.appRoot)
        val status=JSONObject().put("height",9349).put("peers",2)
            .put("wallet",JSONObject().put("address","sumuww1-test-fixture").put("unlocked",true).put("available_dora","1234.00000001"))
            .put("security",JSONObject().put("locked",false)).put("mining_ready",true)
        val snapshots=java.io.File("build/screen-audit").apply{mkdirs()}
        val failures=JSONArray();var actions=0;var cases=0
        for(width in listOf(640,720)) for(code in UiLanguage.languages.keys) {
            UiLanguage.set(activity,code)
            for(page in 0..15) {
                screens.render(SumuwwScreens.Model(page,status,null,0,"all",0,"00:00", "1", "sumuww1-test-recipient", "1.25000000",null,false,false,SumuwwThemeCalendar.resolve("default"),"light",UiLanguage.languages.getValue(code)))
                val root=screens.appRoot
                repeat(3){root.measure(View.MeasureSpec.makeMeasureSpec(width,View.MeasureSpec.EXACTLY),View.MeasureSpec.makeMeasureSpec(1600,View.MeasureSpec.EXACTLY));root.layout(0,0,width,1600)}
                val texts=views(root).filterIsInstance<TextView>()
                assertTrue("empty $code/$page",texts.any{it.text.isNotBlank()})
                assertFalse("encoding $code/$page",texts.any{it.text.contains('\uFFFD')})
                if(code!="ko") assertFalse("Korean fallback $code/$page",texts.any{it.text.any{c->c in '\uAC00'..'\uD7A3'}})
                for(v in views(root).filter{it.isClickable && it.isEnabled && it.visibility==View.VISIBLE}) {
                    if(v is TextView && v.layout!=null && v.height>0) {
                        val layout=v.layout
                        if(layout.lineCount>0 && layout.getLineBottom(layout.lineCount-1)>v.height-v.compoundPaddingTop-v.compoundPaddingBottom+2)
                            failures.put("$width/$code/$page: ${v.text}")
                    }
                    v.performClick();actions++
                }
                if(width==720 && page in listOf(0,1,5,15)) {
                    val bitmap=Bitmap.createBitmap(width,1600,Bitmap.Config.ARGB_8888);root.draw(Canvas(bitmap))
                    java.io.File(snapshots,"$code-$page.png").outputStream().use{bitmap.compress(Bitmap.CompressFormat.PNG,100,it)};bitmap.recycle()
                }
                cases++
            }
        }
        java.io.File(snapshots,"results.json").writeText(JSONObject().put("languages",34).put("screen_cases",cases).put("clicks",actions).put("dispatches",calls.size).put("operations",JSONArray(calls.map{it.substringBefore('|')}.distinct().sorted())).put("clipped",failures).toString(2))
        assertTrue(calls.isNotEmpty());assertEquals("Clipped captions: $failures",0,failures.length())
        controller.destroy()
    }
}
