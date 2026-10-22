package org.sumuww.miner

import android.content.Context
import org.json.JSONObject

internal data class HelpTopic(val id: String, val title: String, val body: String)
internal data class HelpPage(val title: String, val subtitle: String, val back: String, val topics: List<HelpTopic>)

/** Explanations follow the app's actual controls; no market or pool features are advertised. */
internal object SumuwwHelp {
    private var document: JSONObject? = null

    @Synchronized
    fun page(context: Context, language: String): HelpPage {
        val root = document ?: JSONObject(context.assets.open("sumuww_help.json")
            .bufferedReader(Charsets.UTF_8).use { it.readText() }).also { document = it }
        val locale = root.optJSONObject(language) ?: root.getJSONObject("en")
        val topics = locale.getJSONArray("topics")
        return HelpPage(
            locale.getString("title"), locale.getString("subtitle"), locale.getString("back"),
            (0 until topics.length()).map { index ->
                val item = topics.getJSONObject(index)
                HelpTopic(item.getString("id"), item.getString("title"), item.getString("body"))
            }
        )
    }
}
