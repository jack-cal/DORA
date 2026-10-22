package org.sumuww.miner

import android.content.Context
import android.os.Build
import org.json.JSONObject

/** Paths to signed APK native binaries, not separately installed applications. */
object PrivacyRuntime {
    @Volatile private var libraryDirectory: String? = null
    @JvmStatic fun configure(context: Context) { libraryDirectory = context.applicationInfo.nativeLibraryDir }
    @JvmStatic fun paths(): String = JSONObject()
        .put("library_directory", checkNotNull(libraryDirectory) { "Privacy runtime is not initialized" })
        .put("abi", Build.SUPPORTED_ABIS.first()).toString()
}
