package org.sumuww.wallet

import androidx.test.platform.app.InstrumentationRegistry
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.io.File
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class WalletV4Test {
    @Test fun packagedV4ValidationAndRealTcpProofs() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        if (!Python.isStarted()) Python.start(AndroidPlatform(context))
        val report = JSONObject(Python.getInstance().getModule("sumuww.boundary_selftest").callAttr("run_json").toString())
        File(context.getExternalFilesDir(null), "wallet-v4-validation.json").writeText(report.toString(2))
        assertTrue(report.toString(), report.getBoolean("passed"))
        assertEquals(9000, report.getInt("activation_height"))
        assertTrue(report.getJSONArray("checks").toString().contains("unsigned_selected_block_rejected"))
    }
}
