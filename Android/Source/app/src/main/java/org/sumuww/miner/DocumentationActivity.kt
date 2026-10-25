package org.sumuww.miner

import android.app.Activity
import android.os.Bundle
import android.net.Uri
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import org.json.JSONObject
import java.io.ByteArrayInputStream

/** Offline bundled documents only. No JavaScript bridge or external navigation. */
class DocumentationActivity : Activity() {
    private lateinit var web: WebView
    companion object {
        private const val HOST = "sumuww-docs.invalid"
        fun assetPath(uri: Uri): String? {
            if (uri.scheme != "https" || uri.host != HOST || uri.port != -1 ||
                uri.userInfo != null || uri.query != null) return null
            val path = uri.path ?: return null
            if (!path.startsWith("/") || path.contains('\\') || path.contains('%') ||
                path.contains('\u0000') || path.split('/').any { it == "." || it == ".." }) return null
            if (!listOf(".html", ".json", ".md").any { path.endsWith(it) }) return null
            return "integration" + path
        }
        fun title(context: android.content.Context): String {
            val code = UiLanguage.code(context)
            return JSONObject(context.assets.open("integration/labels.json").bufferedReader().use { it.readText() })
                .getString(code)
        }
    }
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        title = title(this)
        actionBar?.setDisplayHomeAsUpEnabled(true)
        web = WebView(this)
        web.settings.apply {
            javaScriptEnabled = false
            allowFileAccess = false
            allowContentAccess = false
            blockNetworkLoads = true
            domStorageEnabled = false
        }
        web.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean =
                assetPath(request.url) == null
            override fun shouldInterceptRequest(view: WebView, request: WebResourceRequest): WebResourceResponse {
                val path = assetPath(request.url)
                val stream = if (path == null) null else try { assets.open(path) } catch (_: Exception) { null }
                return if (stream == null) WebResourceResponse("text/plain", "UTF-8", 404, "Not Found",
                    emptyMap(), ByteArrayInputStream(ByteArray(0)))
                else WebResourceResponse(if (path!!.endsWith(".html")) "text/html" else "text/plain", "UTF-8", stream)
            }
        }
        val layout = android.widget.LinearLayout(this).apply { orientation = android.widget.LinearLayout.VERTICAL }
        layout.addView(android.widget.Button(this).apply {
            text = "← " + title(this@DocumentationActivity)
            setOnClickListener { finish() }
        })
        layout.addView(web, android.widget.LinearLayout.LayoutParams(-1, 0, 1f))
        setContentView(layout)
        web.loadUrl("https://$HOST/docs/i18n/${UiLanguage.code(this)}/ANDROID.html")
    }
    @Deprecated("Android Activity navigation")
    override fun onBackPressed() { if (web.canGoBack()) web.goBack() else super.onBackPressed() }
    override fun onOptionsItemSelected(item: android.view.MenuItem): Boolean {
        if (item.itemId == android.R.id.home) { finish(); return true }
        return super.onOptionsItemSelected(item)
    }
    override fun onDestroy() { web.stopLoading(); web.destroy(); super.onDestroy() }
}
