package org.sumuww.wallet

import android.app.AlertDialog
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.drawable.BitmapDrawable
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.ImageView
import android.widget.TextView
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.google.zxing.BinaryBitmap
import com.google.zxing.MultiFormatReader
import com.google.zxing.RGBLuminanceSource
import com.google.zxing.common.HybridBinarizer
import com.chaquo.python.Kwarg
import com.chaquo.python.Python
import org.junit.Assert.*
import org.junit.Test
import org.junit.Before
import org.junit.After
import org.junit.runner.RunWith
import java.io.File

@RunWith(AndroidJUnit4::class)
class WalletUiTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private lateinit var activity: MainActivity
    private lateinit var fixture: com.chaquo.python.PyObject
    @Before fun disposableWalletService() {
        val context = instrumentation.targetContext
        WalletRuntime.executor.submit {
            if (!Python.isStarted()) Python.start(com.chaquo.python.android.AndroidPlatform(context))
            fixture = Python.getInstance().getModule("builtins").callAttr("dict")
            Python.getInstance().getModule("builtins").callAttr("exec", """
import tempfile
from pathlib import Path
import wallet_runtime as runtime
from sumuww.app_service import AppService
from sumuww import keystore
from mobile_interfaces import install
runtime.stop()
install()
keystore._publish_no_replace=runtime._publish_android
owned=tempfile.TemporaryDirectory(prefix='wallet-creation-ui-')
service=AppService(Path(owned.name)/'node',network='dora',listen='127.0.0.1:0',peers=[],bootstrap=False,allow_lan=False,allow_internet=False,auto_address=False)
service.start().result(30)
runtime._service=service
""".trimIndent(), fixture)
        }.get()
    }
    @After fun closeDisposableService() {
        if (::activity.isInitialized) ui { activity.finish() }
        if (::fixture.isInitialized) WalletRuntime.executor.submit {
            Python.getInstance().getModule("builtins").callAttr("exec", "runtime.stop(); owned.cleanup()", fixture)
        }.get()
    }
    private fun ui(block: () -> Unit) = instrumentation.runOnMainSync(block)
    private fun children(view: View): List<View> = listOf(view) + if (view is ViewGroup) (0 until view.childCount).flatMap { children(view.getChildAt(it)) } else emptyList()
    private fun dialog(): AlertDialog? {
        val field = MainActivity::class.java.getDeclaredField("dialog"); field.isAccessible = true
        return field.get(activity) as? AlertDialog
    }
    private fun waitFor(message: String, condition: () -> Boolean) {
        val end = System.currentTimeMillis() + 45000
        while (System.currentTimeMillis() < end) {
            var result = false; ui { result = condition() }; if (result) return
            Thread.sleep(200)
        }
        fail(message)
    }
    private fun click(text: String) {
        ui {
            val root = dialog()?.window?.decorView ?: activity.window.decorView
            val buttons = children(root).filterIsInstance<Button>()
            val button = buttons.firstOrNull { it.text.toString() == text }
            assertNotNull("Missing button: $text; buttons: ${buttons.map { it.text }}", button)
            button!!
            assertTrue(button.isEnabled); button.performClick()
        }
        if (text == "닫기") waitFor("Dialog did not close") { dialog() == null }
    }
    private fun capture(name: String) {
        ui {
            val root = activity.window.decorView
            val bitmap = Bitmap.createBitmap(root.width, root.height, Bitmap.Config.ARGB_8888)
            root.draw(Canvas(bitmap))
            val folder = File(activity.getExternalFilesDir(null), "verification").apply { mkdirs() }
            File(folder, name).outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
        }
    }
    @Test fun creationReceiveQrAndLock() {
        instrumentation.targetContext.getSharedPreferences("wallet-ui", 0).edit().putString("language", "ko").commit()
        activity = instrumentation.startActivitySync(Intent(instrumentation.targetContext, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) as MainActivity
        waitFor("Onboarding did not appear") { children(activity.window.decorView).filterIsInstance<Button>().any { it.text.toString() == "새 지갑 만들기" } }
        capture("01-onboarding.png")
        click("새 지갑 만들기")
        ui {
            val fields = children(dialog()!!.window!!.decorView).filterIsInstance<EditText>()
            assertEquals(2, fields.size)
            assertTrue(fields.first().hint.toString().contains("12"))
            fields.forEach { it.setText("12345678901") }
        }
        click("계속")
        ui { assertTrue(dialog()?.isShowing == true) }
        assertTrue(WalletRuntime.executor.submit<Boolean> { !WalletRuntime.call("status").optBoolean("wallet_exists") }.get())
        ui {
            children(dialog()!!.window!!.decorView).filterIsInstance<EditText>().forEach { it.setText("twelvechars!") }
        }
        click("계속")
        waitFor("Recovery words not shown") { dialog()?.getButton(AlertDialog.BUTTON_NEGATIVE)?.text?.toString() == "닫기" && dialog()?.window?.decorView?.let { children(it).filterIsInstance<TextView>().any { view -> view.text.contains("복구 단어") } } == true }
        click("닫기")
        waitFor("Wallet home did not appear") { children(activity.window.decorView).filterIsInstance<Button>().any { it.text.toString() == "↓  받기" } }
        capture("02-wallet.png")
        click("↓  받기")
        var receivingAddress = ""
        ui {
            val views = children(dialog()!!.window!!.decorView)
            val address = views.filterIsInstance<TextView>().first { it.text.startsWith("sumuww1") }.text.toString()
            receivingAddress = address
            val image = views.filterIsInstance<ImageView>().first { it.contentDescription == "SUMUWW address QR" }
            val bitmap = (image.drawable as BitmapDrawable).bitmap
            val pixels = IntArray(bitmap.width * bitmap.height)
            bitmap.getPixels(pixels, 0, bitmap.width, 0, 0, bitmap.width, bitmap.height)
            val decoded = MultiFormatReader().decode(BinaryBitmap(HybridBinarizer(RGBLuminanceSource(bitmap.width, bitmap.height, pixels)))).text
            assertEquals(address, decoded)
        }
        click("닫기")
        WalletRuntime.executor.submit {
            val words = WalletRuntime.call("phrase", "twelvechars!").getString("words")
            val path = File(activity.cacheDir, "recovery-verification.json")
            try {
                val recovered = Python.getInstance().getModule("dora.keystore").callAttr("recover_hd_wallet", path.absolutePath,
                    "emulator-recovery-password", words, Kwarg("network", "dora"))
                assertEquals(receivingAddress, recovered.get("address").toString())
            } finally { path.delete() }
        }.get()
        click("↑  보내기")
        capture("03-send.png")
        click("설정")
        capture("04-settings.png")
        click("지갑")
        click("잠금")
        waitFor("Lock failed") { children(activity.window.decorView).filterIsInstance<Button>().any { it.text.toString() == "지갑 잠금 해제" } }
        click("지갑 잠금 해제")
        ui { children(dialog()!!.window!!.decorView).filterIsInstance<EditText>().single().setText("twelvechars!") }
        click("확인")
        waitFor("Unlock failed") { dialog() == null && children(activity.window.decorView).filterIsInstance<Button>().any { it.text.toString() == "잠금" } }
        ui { activity.finish() }
        Thread.sleep(500)
        val snapshot = WalletRuntime.executor.submit<org.json.JSONObject> { WalletRuntime.call("status") }.get()
        assertFalse(snapshot.getJSONObject("wallet").getBoolean("unlocked"))
    }
}
