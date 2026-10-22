package org.sumuww.wallet

import android.app.AlertDialog
import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Paint
import android.text.SpannableString
import android.text.Spanned
import android.text.TextWatcher
import android.text.Editable
import android.text.style.ReplacementSpan
import android.view.View
import android.view.ViewGroup
import android.widget.EditText
import android.widget.TextView
import java.util.WeakHashMap

/** Native dialog/check-box captions retain their text, accessibility and actions. */
internal object SumuwwVerticalCaptions {
    private val watched = WeakHashMap<TextView, Boolean>()
    private val originalTextSize = WeakHashMap<TextView, Float>()

    fun watch(view: TextView) {
        if (view is EditText || view is SumuwwVerticalTextView) return
        if (watched.put(view, true) == null) {
            view.addOnLayoutChangeListener { _, left, _, right, _, oldLeft, _, oldRight, _ ->
                if (right-left != oldRight-oldLeft) apply(view)
            }
            view.addTextChangedListener(object : TextWatcher {
                override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
                override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {}
                override fun afterTextChanged(s: Editable?) { apply(view) }
            })
        }
        apply(view)
    }

    private fun apply(view: TextView) {
        val value = view.text ?: return
        if(value.any { it in '\u0600'..'\u06ff' || it in '\u0750'..'\u077f' }) {
            val original=originalTextSize.getOrPut(view){view.textSize}
            view.setTextSize(android.util.TypedValue.COMPLEX_UNIT_PX,maxOf(16f*view.resources.displayMetrics.scaledDensity,original*1.16f))
            val bold=view.typeface?.isBold==true
            view.typeface=SumuwwArabicTypography.face(view.context,bold)
            view.includeFontPadding=true;view.paint.isAntiAlias=true;view.paint.isSubpixelText=true
        }
        if (!value.any { it in '\u1800'..'\u18af' }) return
        val available = if (view.width > 0) view.width else view.resources.displayMetrics.widthPixels * 3 / 4
        val width = maxOf(32, available - view.totalPaddingLeft - view.totalPaddingRight)
        if (value is Spanned && value.getSpans(0, value.length, VerticalSpan::class.java).any { it.availableWidth == width }) return
        val span = VerticalSpan(view.context, value.toString(), width)
        view.text = SpannableString(value).apply { setSpan(span, 0, length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE) }
        // Framework list rows otherwise keep a fixed single-line height.
        view.layoutParams?.let { if (it.height > 0) { it.height = ViewGroup.LayoutParams.WRAP_CONTENT; view.layoutParams = it } }
        view.setSingleLine(false)
        view.maxLines = Int.MAX_VALUE
        view.ellipsize = null
    }

    private fun walk(view: View) {
        if (view is TextView) watch(view)
        if (view is ViewGroup) for (i in 0 until view.childCount) walk(view.getChildAt(i))
    }

    fun builder(context: Context): AlertDialog.Builder = object : AlertDialog.Builder(context) {
        override fun create(): AlertDialog {
            val dialog = super.create()
            val decor = dialog.window?.decorView
            decor?.addOnAttachStateChangeListener(object : View.OnAttachStateChangeListener {
                override fun onViewAttachedToWindow(v: View) {
                    walk(v)
                    v.viewTreeObserver.addOnGlobalLayoutListener { walk(v) }
                }
                override fun onViewDetachedFromWindow(v: View) {}
            })
            return dialog
        }
        override fun show(): AlertDialog = create().also { it.show() }
    }

    private class VerticalSpan(val context: Context, val value: String, val availableWidth: Int) : ReplacementSpan() {
        private var bitmap: Bitmap? = null
        private var signature: Pair<Float, Int>? = null
        private fun raster(paint: Paint): Bitmap {
            val key = paint.textSize to paint.color
            if (signature == key) return bitmap!!
            val label = SumuwwVerticalTextView(context).apply {
                text = value
                setTextSize(android.util.TypedValue.COMPLEX_UNIT_PX, paint.textSize)
                setTextColor(paint.color)
            }
            label.measure(View.MeasureSpec.makeMeasureSpec(availableWidth, View.MeasureSpec.AT_MOST),
                View.MeasureSpec.makeMeasureSpec(0, View.MeasureSpec.UNSPECIFIED))
            label.layout(0, 0, label.measuredWidth, label.measuredHeight)
            val result = Bitmap.createBitmap(maxOf(1, label.measuredWidth), maxOf(1, label.measuredHeight), Bitmap.Config.ARGB_8888)
            label.draw(Canvas(result))
            bitmap?.recycle(); bitmap = result; signature = key
            return result
        }
        override fun getSize(paint: Paint, text: CharSequence, start: Int, end: Int, fm: Paint.FontMetricsInt?): Int {
            val image = raster(paint)
            fm?.let { it.ascent = -image.height; it.top = it.ascent; it.descent = 0; it.bottom = 0 }
            return image.width
        }
        override fun draw(canvas: Canvas, text: CharSequence, start: Int, end: Int, x: Float, top: Int, y: Int, bottom: Int, paint: Paint) {
            val image = raster(paint)
            canvas.drawBitmap(image, x, (y - image.height).toFloat(), paint)
        }
    }
}
