package org.sumuww.miner

import android.app.Activity
import android.content.res.ColorStateList
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.RectF
import android.graphics.SweepGradient
import android.graphics.Shader
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.text.InputType
import android.text.TextUtils
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView

/** Presentation tokens and native View components shared by every SMW screen. */
internal class SumuwwUiComponents(val activity: Activity, val palette: SumuwwTheme.Palette, val dark: Boolean) {
    private val config = SumuwwTheme.config(palette)
    val verticalMongolian = UiLanguage.code(activity) == "mn-Mong"
    val arabic = UiLanguage.code(activity) == "ar"
    val background = if (dark) config.backgroundDark else config.backgroundLight
    val surface = if (dark) config.surfaceDark else config.surfaceLight
    val elevated = if (dark) config.elevatedDark else config.surfaceLight
    val ink = if (dark) config.textDark else config.textLight
    val muted = if (dark) config.mutedDark else config.mutedLight
    val border = if (dark) config.borderDark else config.borderLight
    val accent = SumuwwTheme.foregroundAccent(palette, dark)
    val onButton = config.onAccent
    val soft = SumuwwTheme.mix(surface, accent, if (dark) .14f else .07f)
    val positive = SumuwwTheme.readableForeground(android.graphics.Color.parseColor("#16A676"), surface)
    val negative = SumuwwTheme.readableForeground(android.graphics.Color.parseColor("#DC4659"), soft)

    fun dp(value: Int) = (value * activity.resources.displayMetrics.density + .5f).toInt()
    fun column() = LinearLayout(activity).apply { orientation = LinearLayout.VERTICAL }
    fun row() = LinearLayout(activity).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }
    fun params(width: Int = -1, height: Int = -2, top: Int = 0, bottom: Int = 0) = LinearLayout.LayoutParams(width, height).apply { topMargin = dp(top); bottomMargin = dp(bottom) }
    fun rounded(color: Int, radius: Int = 18, stroke: Int? = null) = GradientDrawable().apply { setColor(color); cornerRadius = dp(radius).toFloat(); if (stroke != null) setStroke(dp(1), stroke) }
    fun finish(kind: SumuwwFinishDrawable.Kind, radius: Int = 18) = SumuwwFinishDrawable(palette, dark, dp(radius).toFloat(), kind)
    fun gradient(radius: Int = 18) = finish(SumuwwFinishDrawable.Kind.KEY, radius)
    fun surfaceFinish(radius: Int = 18) = finish(SumuwwFinishDrawable.Kind.SURFACE, radius)

    fun label(value: String, size: Float = 14f, color: Int = ink, bold: Boolean = false) = SumuwwVerticalTextView(activity).apply {
        text = value; textSize = if(arabic)maxOf(16f,size*1.16f) else size; verticalTextSizeCapSp = if(bold)14f else 12f
        setTextColor(if(arabic && color==muted)SumuwwTheme.readableForeground(color,surface,5.5) else color)
        val arabicText=arabic && (value.isBlank() || value.any{it in '\u0600'..'\u06ff'})
        includeFontPadding = arabicText
        typeface = Typeface.create(if (bold) "sans-serif-medium" else "sans-serif", Typeface.NORMAL)
        if(arabicText) {
            typeface = SumuwwArabicTypography.face(activity,bold)
            paint.isAntiAlias=true;paint.isSubpixelText=true
        }
        verticalInlineDp = if(value.length > 100) 92f else 56f
        setLineSpacing(dp(2).toFloat(), 1f)
    }

    fun icon(resource: Int, tint: Int = accent) = ImageView(activity).apply {
        setImageResource(resource); imageTintList = ColorStateList.valueOf(tint); scaleType = ImageView.ScaleType.FIT_CENTER
    }

    fun logo() = SumuwwBrandMark(activity, palette, dark)

    fun SumuwwTopBar(title: String, back: (() -> Unit)? = null, actionIcon: Int? = null, actionName: String = "", action: (() -> Unit)? = null): LinearLayout {
        val bar = row().apply { setPadding(dp(if (back == null) 20 else 12), dp(8), dp(12), dp(8)); minimumHeight = dp(56) }
        if (back != null) bar.addView(icon(R.drawable.ic_back, ink).apply { setPadding(dp(12), dp(10), dp(12), dp(10)); contentDescription = "Back"; setOnClickListener { back() } }, params(dp(44), dp(44)))
        bar.addView(label(title, 24f, if (title == "SUMUWW" || title == "SUMUWW") accent else ink, true).apply{if(verticalMongolian)verticalTextSizeCapSp=12f}, LinearLayout.LayoutParams(0, -2, 1f))
        if (actionIcon != null) bar.addView(icon(actionIcon, ink).apply { setPadding(dp(12), dp(10), dp(12), dp(10)); contentDescription = actionName; setOnClickListener { action?.invoke() } }, params(dp(44), dp(44)))
        return bar
    }

    fun SumuwwBalanceCard(caption: String, value: String, detail: String? = null, address: String? = null, keyCard: Boolean = false, copyAddress: (() -> Unit)? = null): LinearLayout {
        val card = column().apply { setPadding(dp(if(verticalMongolian)14 else 22), dp(if(verticalMongolian)14 else 22), dp(if(verticalMongolian)14 else 22), dp(if(verticalMongolian)12 else 20)); background = if (keyCard) gradient() else finish(SumuwwFinishDrawable.Kind.SOFT); elevation=dp(1).toFloat() }
        val primaryInk = if (keyCard) config.onKeyCard else ink
        val secondaryInk = if (keyCard) config.onKeyCaption else muted
        val summary = if(verticalMongolian) row() else card
        val totals = card
        summary.addView(label(caption, 12f, secondaryInk).apply{verticalInlineDp=64f})
        totals.addView(label(value, 32f, primaryInk, true).apply {
            typeface=Typeface.create("sans-serif", Typeface.BOLD)
            maxLines = 1; ellipsize = TextUtils.TruncateAt.END
            setAutoSizeTextTypeUniformWithConfiguration(20, 32, 1, TypedValue.COMPLEX_UNIT_SP)
        }, params(top = 10, bottom = 8))
        if (!detail.isNullOrBlank()) {
            if(verticalMongolian){
                val numeric=Regex("[0-9.,+—−-]+\\s+SMW$").find(detail)
                summary.addView(label(if(numeric==null)detail else detail.substring(0,numeric.range.first).trim(),12f,secondaryInk).apply{verticalInlineDp=48f},LinearLayout.LayoutParams(0,-2,1f).apply{leftMargin=dp(12)})
                numeric?.let{summary.addView(label(it.value,16f,secondaryInk).apply{maxLines=1;setAutoSizeTextTypeUniformWithConfiguration(10,16,1,TypedValue.COMPLEX_UNIT_SP)},LinearLayout.LayoutParams(0,-2,1f))}
            }else totals.addView(label(detail,12f,secondaryInk))
        }
        if(verticalMongolian){
            card.addView(summary)
        }
        if (!address.isNullOrBlank()) {
            val trayColor = SumuwwTheme.mix(config.gradientStart, if(config.onKeyCaption==android.graphics.Color.WHITE) android.graphics.Color.BLACK else android.graphics.Color.WHITE, .09f)
            val tray=row().apply { setPadding(dp(10),0,dp(2),0); background=rounded(trayColor,10) }
            tray.addView(label(address,12f,secondaryInk).apply{maxLines=1;ellipsize=TextUtils.TruncateAt.MIDDLE},LinearLayout.LayoutParams(0,-2,1f))
            if(copyAddress!=null)tray.addView(icon(R.drawable.ic_copy,secondaryInk).apply{setPadding(dp(12),dp(12),dp(12),dp(12));contentDescription=UiLanguage.text(activity,"주소 복사");setOnClickListener{copyAddress()}},params(dp(44),dp(44)))
            else tray.setPadding(dp(10),dp(9),dp(10),dp(9))
            card.addView(tray,params(top=16))
        }
        return card
    }

    fun SumuwwActionButton(resource: Int, caption: String, click: () -> Unit): LinearLayout {
        val item = column().apply { gravity = Gravity.CENTER_HORIZONTAL; contentDescription = caption; isClickable = true; setOnClickListener { click() } }
        val circle = FrameLayout(activity).apply { background = finish(SumuwwFinishDrawable.Kind.ACTION, 24); elevation=dp(1).toFloat() }
        circle.addView(icon(resource, if(palette.id=="default")onButton else accent), FrameLayout.LayoutParams(dp(22), dp(22), Gravity.CENTER))
        item.addView(circle, params(dp(if(verticalMongolian)32 else 48), dp(if(verticalMongolian)32 else 48)))
        item.addView(label(caption, 12f, ink, true).apply { gravity = Gravity.CENTER; maxLines = 2; verticalInlineDp=40f;verticalTextSizeCapSp=if(verticalMongolian)10f else 12f }, params(top = 8))
        return item
    }

    fun SumuwwPrimaryButton(caption: String, click: () -> Unit): TextView = label(caption, 16f, onButton, true).apply {
        gravity = Gravity.CENTER; minimumHeight = dp(54); setPadding(dp(16), dp(14), dp(16), dp(14)); background = finish(SumuwwFinishDrawable.Kind.BUTTON, 27); elevation=dp(1).toFloat()
        contentDescription = caption; isClickable = true; isFocusable = true; setOnClickListener { click() }
        verticalInlineDp=44f;verticalTextSizeCapSp=12f
        if(verticalMongolian)setPadding(dp(12),dp(8),dp(12),dp(8))
    }

    fun SumuwwSettingRow(resource: Int, caption: String, value: String = "", click: () -> Unit): LinearLayout {
        val line = row().apply { minimumHeight = dp(60); setPadding(dp(4), dp(12), dp(4), dp(12)); isClickable = true; contentDescription = caption; setOnClickListener { click() } }
        line.addView(icon(resource, accent), params(dp(24), dp(24)))
        val words = (if(verticalMongolian) row() else column()).apply { setPadding(dp(16), 0, dp(12), 0) }
        val captionView=label(caption,15f,ink,true).apply{verticalInlineDp=64f}
        if(verticalMongolian)words.addView(captionView,LinearLayout.LayoutParams(0,-2,1f)) else words.addView(captionView)
        if (value.isNotBlank()) {
            val detail=label(value,12f,muted).apply{verticalInlineDp=64f}
            if(verticalMongolian)words.addView(detail,LinearLayout.LayoutParams(0,-2,1f)) else words.addView(detail,params(top=4))
        }
        line.addView(words, LinearLayout.LayoutParams(0, -2, 1f))
        line.addView(icon(R.drawable.ic_back, muted).apply { rotation = 180f }, params(dp(17), dp(17)))
        return line
    }

    fun divider() = View(activity).apply { setBackgroundColor(border); layoutParams = params(height = dp(1)) }
    fun section(value: String) = label(value, 18f, ink, true).apply { verticalSection=true;verticalInlineDp=48f;if(verticalMongolian)verticalTextSizeCapSp=12f;setPadding(0, dp(if(verticalMongolian)10 else 24), 0, dp(if(verticalMongolian)6 else 12)) }

    fun SumuwwField(caption: String, hint: String, value: String = "", number: Boolean = false, tagName: String): Pair<LinearLayout, EditText> {
        val group = column()
        if(verticalMongolian)group.orientation=LinearLayout.HORIZONTAL
        val captionView=label(caption,14f,ink,true).apply{verticalInlineDp=56f}
        group.addView(captionView, if(verticalMongolian)params(width=dp(76),top=12,bottom=8) else params(top=20,bottom=8))
        val verticalHint = hint.any { it in '\u1800'..'\u18af' }
        val field = EditText(activity).apply {
            tag = tagName; this.hint = if (verticalHint) "" else hint; setText(value); textSize = 16f; setTextColor(ink); setHintTextColor(muted)
            contentDescription = "$caption. $hint"
            setPadding(dp(16), dp(12), dp(16), dp(12)); minimumHeight = dp(56); background = rounded(surface, 12, border)
            inputType = if (number) InputType.TYPE_CLASS_NUMBER or InputType.TYPE_NUMBER_FLAG_DECIMAL else InputType.TYPE_CLASS_TEXT
            setSingleLine(true)
        }
        group.addView(field,if(verticalMongolian)LinearLayout.LayoutParams(0,-2,1f).apply{gravity=Gravity.CENTER_VERTICAL;leftMargin=dp(12)} else params())
        return group to field
    }

    fun SumuwwAssetRow(name: String, balance: String, detail: String): LinearLayout {
        val asset = row().apply { setPadding(dp(16), dp(16), dp(16), dp(16)); background = surfaceFinish(16) }
        asset.addView(logo(), params(dp(if(LocaleBrand.isLocalized(activity))64 else 42), dp(if(LocaleBrand.isLocalized(activity))40 else 32)))
        val captions = column().apply { setPadding(dp(12), 0, dp(8), 0) }
        captions.addView(label(name, 16f, ink, true)); captions.addView(label(detail, 12f, muted), params(top = 4))
        asset.addView(captions, LinearLayout.LayoutParams(0, -2, 1f))
        asset.addView(label(balance, 18f, ink, true).apply { maxLines = 1; ellipsize = TextUtils.TruncateAt.END; setAutoSizeTextTypeUniformWithConfiguration(12,18,1,TypedValue.COMPLEX_UNIT_SP) }, LinearLayout.LayoutParams(0, -2, 1f))
        return asset
    }

    fun SumuwwAddressCard(caption: String, address: String, body: String): LinearLayout {
        val card = column().apply { gravity = Gravity.CENTER; setPadding(dp(20), dp(32), dp(20), dp(32)); background = surfaceFinish(18) }
        card.addView(label(caption, 18f, ink, true).apply { gravity = Gravity.CENTER })
        card.addView(label(address, 15f, ink, true).apply { gravity = Gravity.CENTER; setTextIsSelectable(true); setPadding(dp(12), dp(14), dp(12), dp(14)); background = rounded(soft, 12) }, params(top = 20, bottom = 20))
        card.addView(label(body, 13f, muted).apply { gravity = Gravity.CENTER })
        return card
    }

    fun SumuwwTransactionRow(title: String, amount: String, detail: String, kind: String, click: () -> Unit): LinearLayout {
        val color = when (kind) { "send" -> negative; "receive" -> positive; else -> accent }
        val line = row().apply { minimumHeight = dp(72); setPadding(0, dp(14), 0, dp(14)); isClickable = true; setOnClickListener { click() } }
        val iconBox = FrameLayout(activity).apply { background = rounded(SumuwwTheme.mix(surface, color, .13f), 22) }
        iconBox.addView(icon(if (kind == "send") R.drawable.action_send else if (kind == "receive") R.drawable.action_receive else R.drawable.nav_mining, color), FrameLayout.LayoutParams(dp(20), dp(20), Gravity.CENTER))
        line.addView(iconBox, params(dp(40), dp(40)))
        val captions = column().apply { setPadding(dp(12), 0, dp(8), 0) }
        captions.addView(label(title, 14f, ink, true)); captions.addView(label(detail, 12f, muted), params(top = 5))
        line.addView(captions, LinearLayout.LayoutParams(0, -2, 1f))
        line.addView(label(amount, 14f, color, true).apply { maxLines = 1; ellipsize = TextUtils.TruncateAt.END }, LinearLayout.LayoutParams(0, -2, 1.2f))
        return line
    }

    fun SumuwwMiningProgress(progress: Float) = SumuwwProgressRing(activity, palette, dark, progress, verticalMongolian)

    fun SumuwwThemePreview(theme: SumuwwTheme.Palette, selected: Boolean, caption: String, click: () -> Unit): LinearLayout {
        val themeConfig = SumuwwTheme.config(theme)
        val tile = column().apply { tag = "sumuww-theme-${theme.id}"; contentDescription = caption; minimumHeight = dp(84); setPadding(dp(10), dp(10), dp(10), dp(10)); background = rounded(surface, 16, if (selected) SumuwwTheme.foregroundAccent(theme, dark) else border); setOnClickListener { click() } }
        val preview = row()
        listOf(false, true).forEach { isDark ->
            val half = column().apply { setPadding(dp(7), dp(7), dp(7), dp(7)); background = rounded(SumuwwTheme.background(theme, isDark), 10) }
            half.addView(View(activity).apply { background = SumuwwFinishDrawable(theme,isDark,dp(6).toFloat(),SumuwwFinishDrawable.Kind.KEY) }, params(height = dp(26)))
            preview.addView(half, LinearLayout.LayoutParams(0, dp(44), 1f))
        }
        tile.addView(preview)
        tile.addView(label((if (selected) "✓  " else "") + caption, 13f, ink, true).apply { gravity = Gravity.CENTER }, params(top = 8))
        return tile
    }
}

internal class SumuwwProgressRing(activity: Activity, palette: SumuwwTheme.Palette, private val dark: Boolean, progress: Float, private val rectangular: Boolean = false) : View(activity) {
    var progress: Float = progress
        set(value) {
            val bounded = value.coerceIn(0f, 1f)
            if (field == bounded) return
            field = bounded
            invalidate()
        }
    private val surface = SumuwwTheme.surface(palette, dark)
    private val accent = SumuwwTheme.foregroundAccent(palette, dark)
    private val trackColors = SumuwwTheme.ringTrackColors(palette, dark)
    private val progressColors = SumuwwTheme.ringProgressColors(palette, dark)
    private val brush = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.STROKE; strokeCap = Paint.Cap.ROUND }
    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        if (rectangular) {
            val density = resources.displayMetrics.density
            val inset = 5f * density
            val bounds = RectF(inset, inset, width - inset, height - inset)
            val path = android.graphics.Path().apply { addRoundRect(bounds, 12f*density, 12f*density, android.graphics.Path.Direction.CW) }
            brush.shader = null
            brush.strokeWidth = 3f*density
            brush.color = SumuwwTheme.mix(surface, accent, if(dark) .24f else .16f)
            canvas.drawPath(path, brush)
            val measure = android.graphics.PathMeasure(path, false)
            val completed = android.graphics.Path()
            measure.getSegment(0f, measure.length * progress.coerceIn(0f,1f), completed, true)
            brush.color = accent
            canvas.drawPath(completed, brush)
            return
        }
        val stroke = 10f * resources.displayMetrics.density
        val size = minOf(width, height).toFloat(); val cx = width / 2f; val cy = height / 2f; val radius = size / 2f - stroke * 1.5f
        val bounds = RectF(cx - radius, cy - radius, cx + radius, cy + radius)
        brush.strokeWidth = stroke+9f*resources.displayMetrics.density; brush.color = SumuwwTheme.mix(surface,accent,if(dark).12f else .08f); canvas.drawCircle(cx,cy,radius,brush)
        brush.strokeWidth = stroke
        brush.shader = SweepGradient(cx,cy,trackColors,floatArrayOf(0f,.13f,.27f,.42f,.53f,.67f,.85f,1f))
        canvas.drawCircle(cx, cy, radius, brush)
        brush.shader=null;brush.strokeWidth=resources.displayMetrics.density;brush.color=SumuwwTheme.mix(surface,android.graphics.Color.WHITE,if(dark).12f else .8f);canvas.drawCircle(cx,cy,radius-stroke*.45f,brush)
        brush.strokeWidth=stroke;brush.shader=SweepGradient(cx,cy,progressColors,null)
        canvas.drawArc(bounds, -90f, 360f * progress.coerceIn(0f, 1f), false, brush);brush.shader=null
    }
}
