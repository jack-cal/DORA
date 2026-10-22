package org.sumuww.miner

import android.content.Context
import android.graphics.Color
import android.graphics.drawable.BitmapDrawable

/** A theme changes presentation only; the SMW protocol and wallet never read these values. */
object SumuwwTheme {
    data class Palette(val id: String, val label: String, val primary: Int, val secondary: Int, val decoration: String? = null, val controlColor: Int = primary)
    data class ThemeConfig(
        val primary: Int, val secondary: Int, val accent: Int, val onAccent: Int,
        val backgroundLight: Int, val surfaceLight: Int, val backgroundDark: Int, val surfaceDark: Int,
        val elevatedDark: Int, val textLight: Int, val textDark: Int, val mutedLight: Int, val mutedDark: Int,
        val borderLight: Int, val borderDark: Int, val gradientStart: Int, val gradientEnd: Int, val onKeyCard: Int, val onKeyCaption: Int,
        val decorativeAsset: String?
    )
    private fun color(value: String) = Color.parseColor(value)
    private val configurations = java.util.concurrent.ConcurrentHashMap<Palette, ThemeConfig>()
    val palettes = listOf(
        Palette("default", "기본 · SMW", color("#2768F7"), color("#6657E8"), "wave"),
        Palette("gold", "골드", color("#C9993A"), color("#E8C875")),
        Palette("silver", "실버", color("#777D86"), color("#D8DDE3")),
        Palette("blue", "블루", color("#146EF5"), color("#55A8FF")),
        Palette("green", "그린", color("#12945B"), color("#43D18A")),
        Palette("mint", "민트", color("#16B89C"), color("#65E6CE")),
        Palette("cyan", "시얀", color("#00A8C7"), color("#4DE4F5")),
        Palette("navy", "네이비", color("#174AA6"), color("#315FE5")),
        Palette("purple", "퍼플", color("#7437D8"), color("#B35EF4")),
        Palette("pink", "핑크", color("#DD3477"), color("#FF70A6")),
        Palette("red", "레드", color("#DF3038"), color("#FF5C63")),
        Palette("orange", "오렌지", color("#E76A18"), color("#FF9A42")),
        Palette("lavender", "라벤더", color("#8064E8"), color("#B49AFF")),
        Palette("spring", "봄", color("#9CAB75"), color("#DED89D"), "spring"),
        Palette("summer", "여름", color("#15A9D6"), color("#44D7ED"), "summer"),
        Palette("autumn", "가을", color("#C77833"), color("#A64D22"), "autumn"),
        Palette("winter", "겨울", color("#4776A7"), color("#B9DAF5"), "winter"),
        Palette("christmas", "크리스마스", color("#0C5E43"), color("#C82D37"), "christmas")
    )
    val manualPalettes get() = palettes.filter { it.id != "christmas" }
    fun selected(id: String?): Palette = palettes.firstOrNull { it.id == id } ?: if (id == "cherry") palettes.first { it.id == "pink" } else palettes.first()
    fun luminance(color: Int): Double {
        fun channel(value: Int): Double { val s=value/255.0; return if(s<=.04045)s/12.92 else Math.pow((s+.055)/1.055,2.4) }
        return .2126*channel(Color.red(color))+.7152*channel(Color.green(color))+.0722*channel(Color.blue(color))
    }
    fun contrast(first: Int, second: Int): Double {
        val a = luminance(first); val b = luminance(second)
        return (maxOf(a,b)+.05)/(minOf(a,b)+.05)
    }
    fun foregroundAccent(palette: Palette, dark: Boolean): Int {
        return readableForeground(palette.controlColor, surface(palette, dark))
    }
    fun readableForeground(value: Int, background: Int, minimum: Double = 4.5): Int {
        val target = if (luminance(background) < .179) Color.WHITE else Color.BLACK
        var result = value
        var fraction = 0f
        while (contrast(result, background) < minimum && fraction < 1f) {
            fraction += .02f; result = mix(value, target, fraction)
        }
        return result
    }
    private fun readableGradient(values: IntArray, background: Int, minimum: Double): IntArray {
        // Complementary colors can lose contrast between otherwise readable endpoints.
        var endpointMinimum = minimum + .2
        repeat(24) {
            val colors = values.map { readableForeground(it, background, endpointMinimum) }.toIntArray()
            val readable = colors.toList().zipWithNext().all { (first, second) ->
                (0..40).all { contrast(mix(first, second, it / 40f), background) >= minimum }
            }
            if (readable) return colors
            endpointMinimum += .2
        }
        val foreground = if (luminance(background) < .179) Color.WHITE else Color.BLACK
        return IntArray(values.size) { foreground }
    }
    fun brandColors(palette: Palette, dark: Boolean): IntArray {
        val background=surface(palette,dark)
        val body=readableForeground(palette.primary,background,3.4)
        val depth=readableForeground(mix(palette.primary,Color.BLACK,if(dark).12f else .55f),background,3.4)
        val end=if(dark)readableForeground(palette.secondary,background,3.4) else depth
        // The small polished highlight is brighter than the readable silhouette body.
        return intArrayOf(body,mix(palette.primary,Color.WHITE,.62f),body,depth,end)
    }
    fun ringTrackColors(palette: Palette, dark: Boolean): IntArray {
        val base = surface(palette, dark)
        val accent = foregroundAccent(palette, dark)
        val values = listOf(accent to .32f, palette.secondary to .80f, accent to .36f,
            accent to .72f, palette.secondary to .90f, accent to .30f, accent to .68f, accent to .32f)
        val colors = values.map { (color, fraction) -> mix(base, color, fraction) }.toIntArray()
        return if (dark) readableGradient(colors, base, 3.0) else colors
    }
    fun ringProgressColors(palette: Palette, dark: Boolean): IntArray {
        val base = surface(palette, dark)
        val accent = foregroundAccent(palette, dark)
        return readableGradient(intArrayOf(accent, palette.secondary, accent), base, 3.0)
    }
    fun config(palette: Palette): ThemeConfig = configurations.computeIfAbsent(palette) { buildConfig(it) }
    private fun buildConfig(palette: Palette): ThemeConfig {
        val light = when (palette.id) {
            "spring" -> "#F8F5EB"; "summer" -> "#F2FBFD"; "autumn" -> "#F7EFE4"
            "winter" -> "#EEF7FF"; "christmas" -> "#F7FAF8"; else -> "#F8FAFC"
        }
        val dark = when (palette.id) {
            "spring" -> "#101410"; "summer" -> "#071A26"; "autumn" -> "#17120F"
            "winter" -> "#0A1727"; "christmas" -> "#09140F"; else -> "#090D11"
        }
        val darkSurface = when (palette.id) {
            "spring" -> "#171D17"; "summer" -> "#0D222F"; "autumn" -> "#211B17"
            "winter" -> "#121F31"; "christmas" -> "#111D16"; else -> "#11171D"
        }
        // The reference has a bright color field, with depth confined to narrow reflections.
        fun readableFill(value: Int, minimum: Double = 4.5): Int {
            var fill = value
            var shade = 0f
            while (contrast(Color.WHITE, fill) < minimum && shade < 1f) {
                shade += .025f; fill = mix(value, Color.BLACK, shade)
            }
            return fill
        }
        val button = readableFill(palette.controlColor)
        val start = readableFill(mix(palette.primary, palette.secondary, .10f), 3.2)
        val end = readableFill(mix(palette.primary, palette.secondary, .58f), 3.2)
        val caption = if (contrast(Color.WHITE, start) >= 4.55) Color.WHITE else readableForeground(color("#302539"), start, 5.3)
        return ThemeConfig(palette.primary, palette.secondary, button, Color.WHITE,
            color(light), Color.WHITE, color(dark), color(darkSurface), mix(color(darkSurface), Color.WHITE, .025f),
            color("#111827"), color("#F8FAFC"), color("#6B7280"), color("#8C98A5"), color("#E8ECF2"), color("#232D37"),
            start, end, Color.WHITE, caption, palette.decoration)
    }
    private fun onColor(value: Int) = if (luminance(value) > .179) Color.BLACK else Color.WHITE
    fun mix(first: Int, second: Int, fraction: Float): Int {
        val t = fraction.coerceIn(0f, 1f)
        return Color.rgb((Color.red(first) * (1 - t) + Color.red(second) * t).toInt(),
            (Color.green(first) * (1 - t) + Color.green(second) * t).toInt(),
            (Color.blue(first) * (1 - t) + Color.blue(second) * t).toInt())
    }
    fun background(palette: Palette, dark: Boolean) = config(palette).let { if (dark) it.backgroundDark else it.backgroundLight }
    fun surface(palette: Palette, dark: Boolean) = config(palette).let { if (dark) it.surfaceDark else it.surfaceLight }
    fun soft(palette: Palette, dark: Boolean) = mix(surface(palette, dark), foregroundAccent(palette, dark), if (dark) .14f else .07f)
    fun border(palette: Palette, dark: Boolean) = config(palette).let { if (dark) it.borderDark else it.borderLight }
    @Suppress("DEPRECATION")
    fun logo(context: Context, palette: Palette): BitmapDrawable = context.resources.getDrawable(LocaleBrand.artwork(context), context.theme) as BitmapDrawable
}
