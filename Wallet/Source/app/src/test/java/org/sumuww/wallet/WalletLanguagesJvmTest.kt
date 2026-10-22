package org.sumuww.wallet

import android.app.AlertDialog
import android.graphics.Bitmap
import android.graphics.Canvas
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.TextView
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import org.robolectric.shadows.ShadowAlertDialog
import java.util.Locale

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], qualifiers = "w360dp-h800dp-xhdpi")
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class WalletLanguagesJvmTest {
    private fun views(view: View): List<View> = listOf(view) + if (view is ViewGroup) (0 until view.childCount).flatMap { views(view.getChildAt(it)) } else emptyList()
    @Test fun renderWalletSendAndSettingsInAll34LanguagesWithoutChangingDisplayedValues() {
        val context = RuntimeEnvironment.getApplication()
        WalletLanguages.set(context, "en")
        val activity = Robolectric.buildActivity(MainActivity::class.java).create().get()
        val stateField = MainActivity::class.java.getDeclaredField("state").apply { isAccessible = true }
        val loading = MainActivity::class.java.getDeclaredField("historyLoading").apply { isAccessible = true }
        loading.set(activity, true) // This UI fixture does not query or start a node.
        val snapshot = JSONObject().put("wallet_exists", true).put("wallet", JSONObject()
            .put("address", "sumuww1-language-rendering-fixture").put("unlocked", true)
            .put("available_dora", "1234.00000001").put("pending_dora", "0.00000002").put("immature_dora", "50.00000000"))
            .put("node", JSONObject().put("peers", 14).put("height", 9100).put("sync_state", "synced"))
        stateField.set(activity, snapshot)
        val before = snapshot.toString()
        val page = MainActivity::class.java.getDeclaredField("page").apply { isAccessible = true }
        val render = MainActivity::class.java.getDeclaredMethod("render").apply { isAccessible = true }
        val output = java.io.File("build/language-screenshots").apply { mkdirs() }
        for (code in WalletLanguages.languages.keys) {
            WalletLanguages.set(activity, code)
            for (name in listOf("wallet", "send", "settings")) {
                page.set(activity, name); render.invoke(activity)
                val root = activity.window.decorView
                root.measure(View.MeasureSpec.makeMeasureSpec(720, View.MeasureSpec.EXACTLY), View.MeasureSpec.makeMeasureSpec(1600, View.MeasureSpec.EXACTLY))
                root.layout(0, 0, 720, 1600)
                val bitmap = Bitmap.createBitmap(720, 1600, Bitmap.Config.ARGB_8888)
                root.draw(Canvas(bitmap))
                java.io.File(output, "$code-$name.png").outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
                bitmap.recycle()
                assertEquals(before, snapshot.toString())
                if (name == "wallet") assertTrue(views(root).filterIsInstance<TextView>().any { it.text.toString() == "1234.00000001" })
            }
        }
    }
    @Test fun defaultsToEnglishOnKoreanDeviceAndRestoresExplicitChoice() {
        val context = RuntimeEnvironment.getApplication()
        context.getSharedPreferences("wallet-ui", 0).edit().clear().commit()
        val previous = Locale.getDefault()
        try {
            Locale.setDefault(Locale.KOREAN)
            val controller = Robolectric.buildActivity(MainActivity::class.java).create()
            val activity = controller.get()
            assertEquals("en", WalletLanguages.code(activity))
            val buttons = views(activity.window.decorView).filterIsInstance<Button>()
            assertTrue(buttons.any { it.text.toString() == "Wallet" })
            assertFalse(buttons.any { it.text.toString() == "지갑" })
            WalletLanguages.set(activity, "es")
            val next = Robolectric.buildActivity(MainActivity::class.java).create().get()
            assertEquals("es", WalletLanguages.code(next))
            val expected = JSONObject(context.assets.open("wallet_locales/es.json").bufferedReader().use { it.readText() }).getString("Wallet")
            assertTrue(views(next.window.decorView).filterIsInstance<Button>().any { it.text.toString() == expected })
        } finally { Locale.setDefault(previous) }
    }
    @Test fun all34CatalogsRenderAndLanguageMenuUsesSelectedCode() {
        val context = RuntimeEnvironment.getApplication()
        WalletLanguages.set(context, "en")
        val activity = Robolectric.buildActivity(MainActivity::class.java).create().get()
        val render = MainActivity::class.java.getDeclaredMethod("render").apply { isAccessible = true }
        val page = MainActivity::class.java.getDeclaredField("page").apply { isAccessible = true }
        val english = JSONObject(context.assets.open("wallet_locales/en.json").bufferedReader().use { it.readText() })
        assertEquals(34, WalletLanguages.languages.size)
        for (code in WalletLanguages.languages.keys) {
            val catalog = JSONObject(context.assets.open("wallet_locales/$code.json").bufferedReader().use { it.readText() })
            assertEquals(code, english.keys().asSequence().toSet(), catalog.keys().asSequence().toSet())
            WalletLanguages.set(activity, code)
            for (name in listOf("wallet", "send", "history", "settings")) {
                page.set(activity, name); render.invoke(activity)
                val labels = views(activity.window.decorView).filterIsInstance<TextView>().map { it.text.toString() }
                assertTrue("$code/$name", labels.contains(catalog.getString("Wallet")))
                assertFalse(labels.any { it.contains('\uFFFD') })
            }
            assertEquals(if (code in setOf("ar", "ur")) View.LAYOUT_DIRECTION_RTL else View.LAYOUT_DIRECTION_LTR, activity.window.decorView.layoutDirection)
            assertTrue(WalletLanguages.format(activity, "{0} confirmations", 12345).contains("12345"))
        }
        WalletLanguages.set(activity, "en"); page.set(activity, "settings"); render.invoke(activity)
        views(activity.window.decorView).filterIsInstance<Button>().first { it.text.toString().startsWith("Language · ") }.performClick()
        val dialog = ShadowAlertDialog.getLatestAlertDialog()
        assertEquals(34, dialog.listView.adapter.count)
        val index = WalletLanguages.languages.keys.indexOf("ja")
        dialog.listView.performItemClick(dialog.listView.getChildAt(index), index, index.toLong())
        assertEquals("ja", WalletLanguages.code(activity))
    }
}
