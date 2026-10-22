package org.sumuww.wallet

import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.TextView
import org.json.JSONObject
import org.json.JSONArray
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], qualifiers = "w360dp-h800dp-xhdpi")
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class ReleaseRecheckJvmTest {
    private fun views(v:View):List<View> = listOf(v) + if(v is ViewGroup) (0 until v.childCount).flatMap { views(v.getChildAt(it)) } else emptyList()
    @Test fun allLanguagesKeepCompleteButtonCaptionsAtPhoneWidths() {
        val context=RuntimeEnvironment.getApplication()
        WalletLanguages.set(context,"en")
        val activity=Robolectric.buildActivity(MainActivity::class.java).create().get()
        val snapshot=JSONObject().put("wallet_exists",true).put("wallet",JSONObject().put("unlocked",true).put("address","sumuww1-layout-fixture").put("available_dora","1234.00000001").put("pending_dora","0.00000002").put("immature_dora","50.00000000")).put("node",JSONObject().put("peers",14).put("height",9100).put("sync_state","ready").put("mining_ready",true))
        MainActivity::class.java.getDeclaredField("state").apply { isAccessible=true }.set(activity,snapshot)
        val page=MainActivity::class.java.getDeclaredField("page").apply { isAccessible=true }
        val render=MainActivity::class.java.getDeclaredMethod("render").apply { isAccessible=true }
        val failures=JSONArray()
        for(width in listOf(720,640)) for(code in WalletLanguages.languages.keys) {
            WalletLanguages.set(activity,code)
            for(name in listOf("wallet","send","settings")) {
                page.set(activity,name);render.invoke(activity)
                val root=activity.window.decorView
                repeat(4) {
                    root.measure(View.MeasureSpec.makeMeasureSpec(width,View.MeasureSpec.EXACTLY),View.MeasureSpec.makeMeasureSpec(1600,View.MeasureSpec.EXACTLY))
                    root.layout(0,0,width,1600)
                }
                for(button in views(root).filterIsInstance<Button>()) {
                    val layout=button.layout ?: continue
                    val available=button.height-button.compoundPaddingTop-button.compoundPaddingBottom
                    if(layout.lineCount>0 && layout.getLineBottom(layout.lineCount-1)>available+2) {
                        failures.put(JSONObject().put("language",code).put("page",name).put("width",width).put("caption",button.text.toString()).put("available",available).put("required",layout.getLineBottom(layout.lineCount-1)))
                    }
                }
            }
        }
        java.io.File("build/recheck-button-clipping.json").writeText(failures.toString(2))
        assertEquals("Clipped buttons: ${failures.toString().take(1000)}",0,failures.length())
    }
}
