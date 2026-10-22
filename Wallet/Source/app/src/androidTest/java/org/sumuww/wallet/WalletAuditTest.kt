package org.sumuww.wallet

import android.app.AlertDialog
import android.content.Intent
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.chaquo.python.PyObject
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import java.util.concurrent.TimeUnit

/** Full UI-to-service flows use disposable regtest data, never the saved wallet. */
@RunWith(AndroidJUnit4::class)
class WalletAuditTest {
    private val inst = InstrumentationRegistry.getInstrumentation()
    private lateinit var activity: MainActivity
    private lateinit var globals: PyObject
    private val password = "isolated-audit-password"
    private fun ui(block: () -> Unit) = inst.runOnMainSync(block)
    private fun views(v: View): List<View> = listOf(v) + if (v is ViewGroup) (0 until v.childCount).flatMap { views(v.getChildAt(it)) } else emptyList()
    private fun dialog(): AlertDialog? = MainActivity::class.java.getDeclaredField("dialog").apply { isAccessible = true }.get(activity) as? AlertDialog
    private fun waitFor(message: String, condition: () -> Boolean) {
        val end = System.currentTimeMillis() + 45000
        while (System.currentTimeMillis() < end) {
            var result = false; ui { result = condition() }; if (result) return
            Thread.sleep(100)
        }
        fail(message)
    }
    private fun texts() = views(activity.window.decorView).filterIsInstance<TextView>().map { it.text.toString() }
    private fun click(text: String) {
        ui {
            val root = dialog()?.window?.decorView ?: activity.window.decorView
            val target = views(root).filterIsInstance<Button>().firstOrNull { it.text.toString() == text }
            assertNotNull("Missing button $text", target); assertTrue(target!!.isEnabled); target.performClick()
        }
    }
    private fun exec(code: String) = WalletRuntime.executor.submit {
        Python.getInstance().getModule("builtins").callAttr("exec", code, globals)
    }.get(60, TimeUnit.SECONDS)
    @Before fun isolatedFundedWallet() {
        val context = inst.targetContext
        context.getSharedPreferences("wallet-ui", 0).edit().putString("language", "ko").putBoolean("dark", false).commit()
        WalletRuntime.executor.submit {
            if (!Python.isStarted()) Python.start(AndroidPlatform(context))
            globals = Python.getInstance().getModule("builtins").callAttr("dict")
        }.get(30, TimeUnit.SECONDS)
        exec("""
import tempfile
from pathlib import Path
import wallet_runtime as runtime
from dora.app_service import AppService
from dora.chain import Chain
from dora.address import decode_address
from dora import keystore
from mobile_interfaces import install
runtime.stop()
install()
keystore._publish_no_replace=runtime._publish_android
owned=tempfile.TemporaryDirectory(prefix='wallet-ui-audit-')
service=AppService(Path(owned.name)/'node',network='regtest',listen='127.0.0.1:0',peers=[],bootstrap=False,allow_lan=False,allow_internet=False,auto_address=False)
service.start().result(30)
runtime._service=service
runtime.call('foreground','true')
runtime._touch()
sender=service.create_seed_wallet('wallet.json','$password').result(30)
receiver=keystore.create_hd_wallet(Path(owned.name)/'recipient.json','$password',network='regtest')
receiving_address=receiver.address
with Chain(service.database,network='regtest') as chain:
    for _ in range(101): chain.accept_block(chain.make_block(decode_address(sender['address'],network='regtest')))
""".trimIndent())
        activity = inst.startActivitySync(Intent(context, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) as MainActivity
        waitFor("Owned wallet did not load") { texts().contains("↑  보내기") }
    }
    @After fun closeFixture() {
        if (::activity.isInitialized) ui { activity.finish() }
        if (::globals.isInitialized) exec("runtime.stop(); owned.cleanup()")
    }
    @Test fun draftsSurviveNavigationDialogsLanguageAndTheme() {
        click("↑  보내기")
        ui {
            val fields = views(activity.window.decorView).filterIsInstance<EditText>()
            fields[0].setText("sumuww1-draft-only"); fields[1].setText("1.25"); fields[2].setText("0.001")
        }
        click("설정"); click("어두운 화면 사용"); click("언어 · 한국어")
        ui {
            val choices = dialog()!!.listView
            val index = WalletLanguages.languages.keys.indexOf("en")
            choices.performItemClick(choices.getChildAt(index), index, choices.adapter.getItemId(index))
        }
        ui {
            val version = activity.packageManager.getPackageInfo(activity.packageName, 0).versionName
            assertTrue(texts().contains("SUMUWW Wallet $version · SMW"))
        }
        click("Wallet"); click("↑  Send")
        ui {
            val fields = views(activity.window.decorView).filterIsInstance<EditText>()
            assertEquals(listOf("sumuww1-draft-only", "1.25", "0.001"), fields.map { it.text.toString() })
            MainActivity::class.java.getDeclaredMethod("decodeQr", ByteArray::class.java).apply { isAccessible = true }.invoke(activity, byteArrayOf(1, 2, 3))
        }
        waitFor("Invalid QR result not shown") { dialog() != null }
        click("Close")
        ui { assertEquals("sumuww1-draft-only", views(activity.window.decorView).filterIsInstance<EditText>().first().text.toString()) }
    }
    @Test fun qrImageImportUsesTheActualAddressParser() {
        val destination = WalletRuntime.executor.submit<String> { globals.callAttr("get", "receiving_address").toString() }.get()
        val file = java.io.File(activity.cacheDir, "owned-audit-qr.png")
        try {
            ui {
                val bitmap = MainActivity::class.java.getDeclaredMethod("qr", String::class.java).apply { isAccessible = true }.invoke(activity, destination) as android.graphics.Bitmap
                file.outputStream().use { bitmap.compress(android.graphics.Bitmap.CompressFormat.PNG, 100, it) }; bitmap.recycle()
                MainActivity::class.java.getDeclaredMethod("onActivityResult", Int::class.javaPrimitiveType, Int::class.javaPrimitiveType, Intent::class.java).apply { isAccessible = true }
                    .invoke(activity, 4103, android.app.Activity.RESULT_OK, Intent().setData(android.net.Uri.fromFile(file)))
            }
            waitFor("QR import did not populate the send address") {
                views(activity.window.decorView).filterIsInstance<EditText>().firstOrNull()?.text.toString() == destination
            }
        } finally { file.delete() }
    }
    @Test fun confirmedTransferUpdatesOpenHistoryWithoutNavigation() {
        exec("quote=service.prepare_payment(receiver.address,'1.25','0.00001').result(30); service.submit_payment(quote['quote_id']).result(30)")
        click("내역")
        waitFor("Pending transaction missing") { texts().contains("확인 대기") }
        exec("with Chain(service.database,network='regtest') as chain: chain.accept_block(chain.make_block(decode_address(sender['address'],network='regtest')))")
        ui { MainActivity::class.java.getDeclaredMethod("readState").apply { isAccessible = true }.invoke(activity) }
        waitFor("Open history did not reflect confirmation") { texts().contains("확인 1회") && !texts().contains("확인 대기") }
    }
    @Test fun actualReviewSendAndRecipientBalance() {
        val destination = WalletRuntime.executor.submit<String> { globals.callAttr("get", "receiving_address").toString() }.get()
        click("↑  보내기")
        ui {
            val fields = views(activity.window.decorView).filterIsInstance<EditText>()
            fields[0].setText(destination); fields[1].setText("2.5"); fields[2].setText("0.00001")
        }
        click("송금 내용 확인")
        waitFor("Confirmation not shown") { dialog()?.getButton(AlertDialog.BUTTON_POSITIVE)?.text.toString() == "전송" }
        click("전송")
        waitFor("Submission result not shown") { dialog()?.window?.decorView?.let { views(it).filterIsInstance<TextView>().any { v -> v.text.contains("거래를 제출했습니다") } } == true }
        click("닫기")
        waitFor("Submitted payment missing from history") { texts().contains("확인 대기") }
        exec("""
with Chain(service.database,network='regtest') as chain:
    chain.accept_block(chain.make_block(decode_address(sender['address'],network='regtest')))
    assert chain.balance(receiver.script_pubkey)==250000000
""".trimIndent())
        waitFor("Confirmation did not update") { texts().contains("확인 1회") }
    }
}
