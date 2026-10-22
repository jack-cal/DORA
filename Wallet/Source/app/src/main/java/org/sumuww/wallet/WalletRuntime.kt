package org.sumuww.wallet

import android.content.Context
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.json.JSONObject
import java.io.File
import java.util.concurrent.Executors

object WalletRuntime {
    val executor = Executors.newSingleThreadExecutor()
    private var started = false
    @Synchronized fun start(context: Context) {
        PrivacyRuntime.configure(context)
        AndroidInterfaces.configure(context)
        if (!Python.isStarted()) Python.start(AndroidPlatform(context.applicationContext))
        if (!started) {
            Python.getInstance().getModule("wallet_runtime").callAttr("start", File(context.filesDir, "wallet-node").absolutePath)
            started = true
        }
    }
    fun call(method: String, vararg args: String): JSONObject {
        val response = JSONObject(Python.getInstance().getModule("wallet_runtime").callAttr("call", method, *args).toString())
        if (!response.optBoolean("ok")) throw IllegalStateException(response.optString("error", "Unable to complete operation"))
        return response.optJSONObject("data") ?: JSONObject()
    }
}
