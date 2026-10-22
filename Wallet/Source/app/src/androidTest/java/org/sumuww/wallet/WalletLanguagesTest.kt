package org.sumuww.wallet

import android.content.Intent
import android.graphics.Bitmap
import android.graphics.Canvas
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.TextView
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.chaquo.python.Python
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.util.Locale

@RunWith(AndroidJUnit4::class)
class WalletLanguagesTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private fun views(view: View): List<View> = listOf(view) + if (view is ViewGroup) (0 until view.childCount).flatMap { views(view.getChildAt(it)) } else emptyList()
    @Test fun englishDefaultAllLanguagesAndSavedChoice() {
        val context = instrumentation.targetContext
        val originalLocale = Locale.getDefault()
        val prefs = context.getSharedPreferences("wallet-ui", 0)
        val previous = prefs.getString("language", null)
        var activity: MainActivity? = null
        val fixture = WalletRuntime.executor.submit<com.chaquo.python.PyObject> {
            if (!Python.isStarted()) Python.start(com.chaquo.python.android.AndroidPlatform(context))
            val scope = Python.getInstance().getModule("builtins").callAttr("dict")
            Python.getInstance().getModule("builtins").callAttr("exec", """
import tempfile,hashlib
from pathlib import Path
import wallet_runtime as runtime
from sumuww.app_service import AppService
from sumuww import keystore
from mobile_interfaces import install
runtime.stop(); install(); keystore._publish_no_replace=runtime._publish_android
owned=tempfile.TemporaryDirectory(prefix='wallet-language-ui-')
service=AppService(Path(owned.name)/'node',network='dora',listen='127.0.0.1:0',peers=[],bootstrap=False,allow_lan=False,allow_internet=False,auto_address=False)
service.start().result(30);runtime._service=service
service.create_seed_wallet('wallet.json','disposable-language-password').result(30)
before=hashlib.sha256((service.directory/'wallet.json').read_bytes()).hexdigest()
""".trimIndent(), scope)
            scope
        }.get()
        try {
            Locale.setDefault(Locale.KOREAN)
            prefs.edit().remove("language").commit()
            assertEquals("en", WalletLanguages.code(context))
            assertEquals(34, WalletLanguages.languages.size)
            activity = instrumentation.startActivitySync(Intent(context, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) as MainActivity
            val current = activity!!
            val render = MainActivity::class.java.getDeclaredMethod("render").apply { isAccessible = true }
            val page = MainActivity::class.java.getDeclaredField("page").apply { isAccessible = true }
            val base = JSONObject(context.assets.open("wallet_locales/en.json").bufferedReader().use { it.readText() })
            for (code in WalletLanguages.languages.keys) {
                val catalog = JSONObject(context.assets.open("wallet_locales/$code.json").bufferedReader().use { it.readText() })
                assertEquals(code, base.keys().asSequence().toSet(), catalog.keys().asSequence().toSet())
                for (key in base.keys()) assertTrue("$code: $key", catalog.getString(key).isNotBlank())
                instrumentation.runOnMainSync {
                    WalletLanguages.set(context, code)
                    for (name in listOf("wallet", "send", "history", "settings")) {
                        page.set(current, name); render.invoke(current)
                        val labels = views(current.window.decorView).filterIsInstance<TextView>().map { it.text.toString() }
                        assertTrue("$code/$name: navigation", labels.contains(catalog.getString("Wallet")))
                        assertFalse("$code/$name: replacement character", labels.any { it.contains('\uFFFD') })
                        assertEquals(if (code in setOf("ar", "ur")) View.LAYOUT_DIRECTION_RTL else View.LAYOUT_DIRECTION_LTR, current.window.decorView.layoutDirection)
                    }
                    assertEquals(code, WalletLanguages.code(context))
                    if (code in setOf("en", "ko", "ar", "ja", "hi", "mn-Mong")) {
                        val root = current.window.decorView
                        if (root.width > 0 && root.height > 0) {
                            val bitmap = Bitmap.createBitmap(root.width, root.height, Bitmap.Config.ARGB_8888)
                            root.draw(Canvas(bitmap))
                            val folder = File(current.getExternalFilesDir(null), "language-verification").apply { mkdirs() }
                            File(folder, "$code.png").outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
                            bitmap.recycle()
                        }
                    }
                }
            }
            instrumentation.runOnMainSync { WalletLanguages.set(context, "es"); current.finish() }
            activity = instrumentation.startActivitySync(Intent(context, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) as MainActivity
            assertEquals("es", WalletLanguages.code(context))
            WalletRuntime.executor.submit {
                Python.getInstance().getModule("builtins").callAttr("exec", "assert hashlib.sha256((service.directory/'wallet.json').read_bytes()).hexdigest()==before", fixture)
            }.get()
        } finally {
            activity?.let { instrumentation.runOnMainSync { it.finish() } }
            Locale.setDefault(originalLocale)
            if (previous == null) prefs.edit().remove("language").commit() else prefs.edit().putString("language", previous).commit()
            WalletRuntime.executor.submit {
                Python.getInstance().getModule("builtins").callAttr("exec", "runtime.stop();owned.cleanup()", fixture)
            }.get()
        }
    }
}
