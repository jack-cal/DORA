package org.sumuww.miner

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RectF
import android.view.View
import org.json.JSONObject

internal data class TourStep(val id: String, val title: String, val body: String)
internal data class TourPage(
    val label: String, val back: String, val next: String, val done: String,
    val skip: String, val replay: String, val steps: List<TourStep>
)

internal object SumuwwTour {
    private var document: JSONObject? = null

    @Synchronized
    fun page(context: Context, language: String): TourPage {
        val root = document ?: JSONObject(context.assets.open("sumuww_tour.json")
            .bufferedReader(Charsets.UTF_8).use { it.readText() }).also { document = it }
        val locale = root.optJSONObject(language) ?: root.getJSONObject("en")
        val steps = locale.getJSONArray("steps")
        return TourPage(
            locale.getString("label"), locale.getString("back"), locale.getString("next"),
            locale.getString("done"), locale.getString("skip"), locale.getString("replay"),
            (0 until steps.length()).map { index ->
                val item = steps.getJSONObject(index)
                TourStep(item.getString("id"), item.getString("title"), item.getString("body"))
            }
        )
    }
}

/** Shades the real screen while leaving the selected control visible. */
internal class TourShade(context: Context, private val accent: Int) : View(context) {
    var spot = RectF()
        set(value) { field = value; invalidate() }
    private val shade = Paint().apply { color = Color.argb(247, 2, 7, 17) }
    private val outline = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = accent
        style = Paint.Style.STROKE
        strokeWidth = context.resources.displayMetrics.density * 3f
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val right = width.toFloat()
        val bottom = height.toFloat()
        if (spot.isEmpty) {
            canvas.drawRect(0f, 0f, right, bottom, shade)
            return
        }
        canvas.drawRect(0f, 0f, right, spot.top, shade)
        canvas.drawRect(0f, spot.bottom, right, bottom, shade)
        canvas.drawRect(0f, spot.top, spot.left, spot.bottom, shade)
        canvas.drawRect(spot.right, spot.top, right, spot.bottom, shade)
        val radius = context.resources.displayMetrics.density * 12f
        canvas.drawRoundRect(spot, radius, radius, outline)
    }
}
