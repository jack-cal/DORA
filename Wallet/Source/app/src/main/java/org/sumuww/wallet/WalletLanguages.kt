package org.sumuww.wallet

import android.content.Context
import org.json.JSONObject

/** Offline catalogs; explicit saved choice, English on first launch. */
object WalletLanguages {
    private val catalogs = mutableMapOf<String, JSONObject>()
    private var names: LinkedHashMap<String, String>? = null
    private var sources: JSONObject? = null
    lateinit var languages: LinkedHashMap<String, String>
        private set

    private fun initialize(context: Context) {
        if (names != null) return
        val data = read(context, "languages")
        // Preserve the intended display order rather than JSONObject hash order.
        val order = listOf("en", "fr", "es", "ar", "zh", "pt", "ru", "de", "sw", "hi", "ko", "ja", "id", "vi", "tr", "th", "it", "bn", "ur", "pl", "nl", "fil", "ta", "zh-TW", "zh-HK", "mn-Mong", "mn", "sr", "sv", "no", "el", "fi", "da", "cs")
        languages = linkedMapOf<String, String>().apply { order.forEach { put(it, data.getString(it)) } }
        names = languages
        sources = read(context, "source_keys")
    }
    private fun read(context: Context, name: String) = JSONObject(context.assets.open("wallet_locales/$name.json").bufferedReader(Charsets.UTF_8).use { it.readText() })
    fun code(context: Context): String {
        initialize(context)
        return context.getSharedPreferences("wallet-ui", Context.MODE_PRIVATE).getString("language", "en")?.takeIf { it in languages } ?: "en"
    }
    fun set(context: Context, code: String) {
        initialize(context); require(code in languages)
        context.getSharedPreferences("wallet-ui", Context.MODE_PRIVATE).edit().putString("language", code).apply()
    }
    fun text(context: Context, korean: String, english: String): String {
        val code = code(context)
        if (code == "ko") return korean
        val key = sources?.optString(korean)?.takeIf { it.isNotBlank() } ?: english
        return catalog(context, code).optString(key, english)
    }
    private fun catalog(context: Context, code: String): JSONObject = synchronized(catalogs) { catalogs.getOrPut(code) { read(context, code) } }
    fun format(context: Context, source: String, vararg args: Any): String {
        var value = catalog(context, code(context)).getString(source)
        // Substitution is literal: addresses, amounts and identifiers are never translated.
        args.forEachIndexed { index, argument -> value = value.replace("{$index}", argument.toString()) }
        return value
    }
}
