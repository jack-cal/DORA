package org.sumuww.miner

import android.content.ComponentName
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build

/** Language artwork changes presentation only; wallet and node state stay intact. */
internal object LocaleBrand {
    fun artwork(language: String): Int = when (language) {
        "ko" -> R.drawable.brand_ko
        "ar" -> R.drawable.brand_ar
        else -> R.drawable.sumuww_icon
    }
    fun artwork(context: Context): Int = artwork(UiLanguage.code(context))
    fun isLocalized(context: Context) = UiLanguage.code(context) in setOf("ko", "ar")
    fun launcherName(language: String): String = when (language) {
        "ko" -> "LauncherKorean"
        "ar" -> "LauncherArabic"
        else -> "LauncherDefault"
    }
    val launcherNames = listOf("LauncherDefault", "LauncherKorean", "LauncherArabic")

    fun syncLauncher(context: Context, language: String = UiLanguage.code(context)) {
        val manager = context.packageManager
        val selected = launcherName(language)
        val changes = launcherNames.mapNotNull { name ->
            val component = ComponentName(context.packageName, "${context.packageName}.$name")
            val state = manager.getComponentEnabledSetting(component)
            val enabled = state == PackageManager.COMPONENT_ENABLED_STATE_ENABLED ||
                (state == PackageManager.COMPONENT_ENABLED_STATE_DEFAULT && name == "LauncherDefault")
            val desired = name == selected
            if (enabled == desired) null else component to if (desired)
                PackageManager.COMPONENT_ENABLED_STATE_ENABLED else PackageManager.COMPONENT_ENABLED_STATE_DISABLED
        }
        if (changes.isEmpty()) return
        try {
            if (Build.VERSION.SDK_INT >= 33) {
                manager.setComponentEnabledSettings(changes.map { (component, state) ->
                    PackageManager.ComponentEnabledSetting(component, state, PackageManager.DONT_KILL_APP)
                })
            } else {
                // Enable the new alias before disabling the old one: never leave zero launchers.
                changes.sortedByDescending { it.second == PackageManager.COMPONENT_ENABLED_STATE_ENABLED }
                    .forEach { (component, state) -> manager.setComponentEnabledSetting(component, state, PackageManager.DONT_KILL_APP) }
            }
        } catch (error: RuntimeException) {
            android.util.Log.w("SUMUWWBrand", "Launcher icon refresh unavailable", error)
        }
    }
}
