package org.sumuww.miner

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.junit.Test
import org.junit.Assert.*
import org.junit.runner.RunWith
import android.net.Uri
import org.json.JSONObject

/** Run only against the .audit application; never opens the user's profile. */
@RunWith(AndroidJUnit4::class)
class NodeContractTest {
    @Test fun documentationRendersOnPhone() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val app = instrumentation.targetContext
        assertTrue(app.packageName.endsWith(".audit"))
        val activity = instrumentation.startActivitySync(android.content.Intent(app, DocumentationActivity::class.java)
            .addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK)) as DocumentationActivity
        try {
            val field = DocumentationActivity::class.java.getDeclaredField("web").apply { isAccessible = true }
            var rendered = false
            for (attempt in 0 until 100) {
                instrumentation.runOnMainSync {
                    val web = field.get(activity) as android.webkit.WebView
                    rendered = web.progress == 100 && web.contentHeight > 100
                    assertFalse(web.settings.javaScriptEnabled)
                    assertFalse(web.settings.allowFileAccess)
                }
                if (rendered) break
                Thread.sleep(100)
            }
            assertTrue("Bundled documents must render without network access", rendered)
        } finally { instrumentation.runOnMainSync { activity.finish() } }
    }
    @Test fun offlineDocumentsAndNavigationBounds() {
        val app = InstrumentationRegistry.getInstrumentation().targetContext
        assertTrue(app.packageName.endsWith(".audit"))
        val labels = JSONObject(app.assets.open("integration/labels.json").bufferedReader().use { it.readText() })
        assertEquals(34, labels.length())
        for (language in UiLanguage.languages.keys) {
            assertTrue(labels.getString(language).isNotBlank())
            for (topic in listOf("ANDROID", "README", "EXCHANGE_INTEGRATION", "RPC_API", "NETWORK_RUNBOOK", "RELEASE_NOTES", "EXCHANGE_EXAMPLES")) {
                val page = app.assets.open("integration/docs/i18n/$language/$topic.html").bufferedReader().use { it.readText() }
                assertTrue(page.contains("<html lang=\"$language\""))
            }
        }
        assertEquals("integration/docs/index.html", DocumentationActivity.assetPath(Uri.parse("https://sumuww-docs.invalid/docs/index.html")))
        for (url in listOf("file:///data/user/0/wallet.json", "https://example.com/test.html", "https://sumuww-docs.invalid/%2e%2e/wallet.json", "https://sumuww-docs.invalid/%252e%252e/wallet.json", "https://sumuww-docs.invalid:443/a.html", "https://user@sumuww-docs.invalid/a.html")) {
            assertNull(DocumentationActivity.assetPath(Uri.parse(url)))
        }
    }
    @Test fun actualNodeContractAndReorganization() {
        val app = InstrumentationRegistry.getInstrumentation().targetContext
        assertTrue(app.packageName.endsWith(".audit"))
        if (!Python.isStarted()) Python.start(AndroidPlatform(app))
        val fixture = InstrumentationRegistry.getInstrumentation().context.assets
            .open("node_contract.py").bufferedReader().use { it.readText() }
        val python = Python.getInstance()
        val scope = python.getModule("builtins").callAttr("dict")
        scope.callAttr("__setitem__", "__name__", "node_contract_fixture")
        python.getModule("builtins").callAttr("exec", fixture, scope)
        val outcome = python.getModule("asyncio").callAttr("run", scope.callAttr("__getitem__", "demonstrate").call())
        val result = JSONObject(python.getModule("json").callAttr("dumps", outcome).toString())
        assertEquals(8, result.getInt("passed"))
        assertFalse(result.getBoolean("persistent_user_data_accessed"))
    }
}
