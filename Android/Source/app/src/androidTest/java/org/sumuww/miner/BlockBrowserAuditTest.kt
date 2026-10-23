package org.sumuww.miner

import android.content.Intent
import android.graphics.Bitmap
import android.view.View
import android.view.ViewGroup
import android.widget.EditText
import android.widget.TextView
import androidx.test.platform.app.InstrumentationRegistry
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import java.io.File

class BlockBrowserAuditTest {
    private fun views(view:View):List<View> = listOf(view)+
        if(view is ViewGroup)(0 until view.childCount).flatMap{views(view.getChildAt(it))}else emptyList()
    private fun result(offset:Int=0)=JSONObject().put("offset",offset).put("height",103).put("total",104)
        .put("blocks",JSONArray().apply{for(h in (103-offset) downTo maxOf(0,54-offset))put(JSONObject()
            .put("height",h).put("hash",h.toString().padStart(64,'0')).put("timestamp",1792677600)
            .put("producer_id","ab".repeat(32)).put("origin",if(h%2==0)"local" else "other"))})
    @Test fun allLanguagesAndSeparateMiningPage(){
        val inst=InstrumentationRegistry.getInstrumentation();val context=inst.targetContext
        check(context.packageName.endsWith(".audit"))
        SumuwwConsent.revoke(context)
        val activity=inst.startActivitySync(Intent(context,MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) as MainActivity
        android.os.SystemClock.sleep(2000) // Allow the platform launch transition to finish.
        try{
            UiLanguage.languages.forEach{(code,name)->
                inst.runOnMainSync{
                    UiLanguage.set(context,code)
                    val actions=mutableListOf<Pair<String,String>>()
                    val screen=SumuwwScreens(activity,{UiLanguage.text(context,it)},{a,b,_->actions.add(a to b)})
                    activity.setContentView(screen.appRoot)
                    val status=JSONObject().put("mobile_batch",JSONObject().put("running",true).put("completed",7).put("target",100))
                    val model=SumuwwScreens.Model(1,status,null,0,"all",0,"00:00:00","100","","",null,false,false,
                        SumuwwThemeCalendar.resolve("default"),"light",name,blocks=result())
                    screen.render(model)
                    assertNull(screen.content.findViewWithTag<View>("sumuww-all-blocks-list"))
                    val stop=views(screen.content).filterIsInstance<TextView>().single{it.isClickable&&it.text.toString()==UiLanguage.text(context,"채굴 중지")}
                    stop.performClick();assertEquals("stopMining",actions.last().first)
                    screen.render(model.copy(page=4))
                    screen.content.findViewWithTag<View>("sumuww-all-blocks").performClick()
                    assertEquals("page" to "15",actions.last())
                    screen.render(model.copy(page=15))
                    assertEquals(50,screen.content.findViewWithTag<ViewGroup>("sumuww-all-blocks-list").childCount)
                    assertTrue(views(screen.topHeader).filterIsInstance<TextView>().any{it.text.toString()==UiLanguage.text(context,"전체 블록")})
                    screen.content.findViewWithTag<View>("blocks-next").performClick();assertEquals("blocksNext",actions.last().first)
                    screen.render(model.copy(page=15,blocks=result(100)))
                    assertEquals(4,screen.content.findViewWithTag<ViewGroup>("sumuww-all-blocks-list").childCount)
                    assertNull(screen.content.findViewWithTag<View>("blocks-next"))
                    screen.content.findViewWithTag<View>("blocks-previous").performClick();assertEquals("blocksPrevious",actions.last().first)
                    screen.content.findViewWithTag<EditText>("blockSearch").setText("0")
                    screen.content.findViewWithTag<View>("blocks-search").performClick();assertEquals("blockSearch" to "0",actions.last())
                    screen.content.findViewWithTag<View>("blocks-refresh").performClick();assertEquals("blocksRefresh",actions.last().first)
                }
                inst.waitForIdleSync()
                if(code in setOf("en","ko","ar","mn-Mong","de","ta")){
                    android.os.SystemClock.sleep(350) // Wait for the rendered frame, not just the view-tree update.
                    inst.waitForIdleSync()
                    val image=inst.uiAutomation.takeScreenshot()
                    File(context.getExternalFilesDir(null),"all-blocks-$code.png").outputStream().use{image.compress(Bitmap.CompressFormat.PNG,100,it)}
                    image.recycle()
                }
            }
        }finally{inst.runOnMainSync{activity.finish()}}
    }
    @Test fun packagedBackendPagesAndThreePeers(){
        val context=InstrumentationRegistry.getInstrumentation().targetContext
        check(context.packageName.endsWith(".audit"))
        if(!Python.isStarted())Python.start(AndroidPlatform(context))
        val python=Python.getInstance();val globals=python.getModule("builtins").callAttr("dict")
        globals.callAttr("__setitem__","test_cache",context.cacheDir.absolutePath)
        python.getModule("builtins").callAttr("exec","""
            import io, tempfile, unittest
            tempfile.tempdir = test_cache
            from pc_tests import test_block_browser, test_peer_retry_recovery, test_incoming_listener_recovery, test_peer_failure_accounting, test_history_prefix_reuse, test_public_reply_deadlines
            stream = io.StringIO()
            result = unittest.TextTestRunner(stream=stream,verbosity=2).run(
                unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromModule(module)
                                   for module in (test_block_browser,test_peer_retry_recovery,test_incoming_listener_recovery,test_peer_failure_accounting,test_history_prefix_reuse,test_public_reply_deadlines)]))
            if not result.wasSuccessful(): raise AssertionError(stream.getvalue())
            assert result.testsRun == 20
            report = stream.getvalue()
        """.trimIndent(),globals)
        File(context.getExternalFilesDir(null),"all-blocks-backend.txt").writeText(globals.callAttr("get","report").toString())
    }
}
